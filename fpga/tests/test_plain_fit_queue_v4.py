"""Exact USD60 integration/packaged closure and restart guards; no RPC."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_plain_fit_queue_v3 as invocation

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('plain_queue_v4_tests', FPGA/'tools/plain_fit_queue_v4.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
HOST = 'gfn16-azure-f16'


class RestartTests(invocation.InvocationTests):
    def setUp(self):
        self.module_patch = patch.object(invocation, 'q', q)
        self.module_patch.start()

    def tearDown(self):
        self.module_patch.stop()

    def test_exact_typed_validation_only_frozen_v2_untouched(self):
        original = (FPGA/'tools/plain_fit_queue_v3.py').read_text()
        self.assertEqual(q.digest(original.encode()), '540715a6f0a30b1d697a304d04c48546760b5bb6f759b6e93f49b82a88181ede')
        expected = original.replace(
            '"""Finite, fixed-slot r54 plain-fit controller. No lifecycle or security API.',
            '"""Additive r54 controller v4: exact approved Azure USD60/day integration.')
        expected = expected.replace('plain_fit_v2.py', 'plain_fit_v3.py').replace('host_hours_azure_v3.py', 'host_hours_azure_v4.py')
        expected = expected.replace('6ae141be72ccfdc77b2035d9b7347e5f555b37e94b4d7a7476ccfb3530d9883e', q.PINS['cloud/plain_fit_v3.py'])
        expected = expected.replace('d133b301ff0dc193774090f991ffa8bc6ee51f06fd318d21ff89673b1632a20c', q.PINS['cloud/host_hours_azure_v4.py'])
        expected = expected.replace('PINS = {', "PINS = {\n 'cloud/azure-daily-cap-user-approval-20261001-v1.json':'890077f5928e430d0ab77cb373497372c197c8c337b4ce477dcfe332769e29b4',\n 'cloud/host_hours_azure_v3.py':'d133b301ff0dc193774090f991ffa8bc6ee51f06fd318d21ff89673b1632a20c',")
        self.assertEqual((FPGA/'tools/plain_fit_queue_v4.py').read_text(), expected+'\n')
        self.assertEqual(q.HORIZON, 21780)
        self.assertEqual(q.HOSTS[HOST]['deadline'], 1791153913)
        self.assertEqual(q.HOSTS[HOST]['memory'], 24<<30)
        self.assertEqual(q.HOSTS['gfn16-aws-m8i']['workers'], 6)


class PacketTests(unittest.TestCase):
    def fixture(self):
        project = FPGA/'results/throughput-20260929/a10-field-physical-probe-v1/project-workers4'
        variant = q.variant_descriptor(project, HOST, exemption='component_sizing_probe')
        job = dict(id='daily60-test', priority=1, project_name='daily60-test-project', unit='gfn16-daily60-test.service', scope='component_probe', allowed_slots={HOST:['d']}, variants={HOST:variant}, after=[], requires=[])
        topology = json.loads((FPGA/'artifacts/plain-f16-launch-v1/fit-plain-tools-v1/topology.json').read_text())
        quote = json.loads((FPGA/'results/throughput-20260929/azure-sim-resize-r49-v1/provider-inputs-v1.json').read_text())
        observed = datetime.fromisoformat(quote['observed_at_utc'].replace('Z','+00:00'))
        meter = q.module('daily60_real_meter', 'cloud/host_hours_azure_v4.py')
        return job, topology, quote, observed, meter

    def test_actual_source_packet_binds_new_runner_meter_approval_and_closure(self):
        job, topology, quote, observed, meter = self.fixture()
        original_module = q.module
        def modules(name, relative):
            return meter if relative == 'cloud/host_hours_azure_v4.py' else original_module(name, relative)
        with tempfile.TemporaryDirectory(prefix='daily60-source-test-', dir=FPGA/'artifacts') as directory:
            destination = Path(directory).resolve()/'prepared'
            with patch.object(q, 'module', side_effect=modules), patch.object(q, 'stamp', return_value=observed+timedelta(seconds=1)), patch.object(meter, 'provider_inputs', return_value=deepcopy(quote)):
                handle, helpers, archive = q.prepare(job, HOST, 'd', destination, topology, observed-timedelta(seconds=1))
            request = json.loads(Path(handle['request']['path']).read_text())
            admitted = json.loads((destination/'host-hours.json').read_text())
            self.assertEqual(request['host_hours_budget']['schema'], 'azure-host-hours-budget-v4')
            self.assertEqual(request['host_hours_budget']['daily_cap_authority'], dict(path=meter.DAILY_AUTHORITY_PATH, sha256=meter.DAILY_AUTHORITY_SHA))
            self.assertEqual(admitted['rolling24h_cap_usd'], 60)
            self.assertEqual(datetime.fromisoformat(admitted['observed_at_utc']), observed+timedelta(seconds=1))
            self.assertEqual(admitted['per_job_charge_usd'], 0)
            self.assertEqual(helpers['plain_fit_v3.py'], q.PINS['cloud/plain_fit_v3.py'])
            self.assertNotIn('plain_fit_v2.py', helpers)
            for relative in ('cloud/host_hours_azure_v4.py', meter.V3_PATH, 'cloud/host_hours_azure_v2.py', meter.DAILY_AUTHORITY_PATH):
                self.assertEqual(helpers['fpga/'+relative], admitted['source_evidence_sha256'][relative])
            self.assertEqual(q.digest(archive.read_bytes()), handle['package_sha256'])
            self.assertFalse(admitted['host_or_source_admission_conferred'])

    def test_all_declared_source_pins_exact_and_wrong_meter_refused(self):
        for relative, pin in q.PINS.items():
            q.regular(FPGA/relative, pin)
        pins = dict(q.PINS, **{'cloud/host_hours_azure_v4.py':'0'*64})
        with patch.object(q, 'PINS', pins), self.assertRaisesRegex(ValueError, 'SHA drift'):
            q.module('wrong_daily_meter', 'cloud/host_hours_azure_v4.py')

    def test_old_journal_is_not_silently_rebound_to_new_controller(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            journal = invocation.q.Journal(root, 'a'*64)
            journal.append('unresolved', 'fixture', reason='retained old intent')
            rows = journal.rows
            rows[0]['controller_sha256'] = q.digest((FPGA/'tools/plain_fit_queue_v3.py').read_bytes())
            row = dict(rows[0]); row.pop('sha256'); rows[0]['sha256'] = q.digest(q.canonical(row))
            (root/'events.jsonl').write_bytes(q.canonical(rows[0])+b'\n')
            with self.assertRaisesRegex(ValueError, 'controller drift'):
                q.Journal(root, 'a'*64)


if __name__ == '__main__':
    unittest.main()
