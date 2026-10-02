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
spec = importlib.util.spec_from_file_location('plain_queue_v5_tests', FPGA/'tools/plain_fit_queue_v5.py')
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
        original = (FPGA/'tools/plain_fit_queue_v4.py').read_text()
        self.assertEqual(q.digest(original.encode()), '41ffe1d8f08d792a96f775c75f9057055370a5efc2a26a31f43e0a7dc19579c6')
        expected = original.replace(
            '"""Additive r54 controller v4: exact approved Azure USD60/day integration.',
            '"""Additive r54 controller v5: approved Azure USD60/day and AWS USD50/day.')
        expected = expected.replace('plain_fit_v3.py', 'plain_fit_v4.py').replace('host_hours_admit_v1.py', 'host_hours_admit_v2.py')
        expected = expected.replace('520dce549b44d5efcef340ce37f65338c9c161bd9e88affd7200574837ec65a0', q.PINS['cloud/plain_fit_v4.py'])
        expected = expected.replace('6fd1904025f4d76557497dba2eac2a5514b419a799c8616b177bc696f051379a', q.PINS['cloud/host_hours_admit_v2.py'])
        expected = expected.replace('PINS = {', "PINS = {\n 'cloud/aws-daily-cap-user-approval-20261001-v2.json':'9f9b9d1474ac1d637ecd2e88c8d943ff3e26aaa35d26cec538dee72a6f42e13b',\n 'cloud/host_hours_admit_v1.py':'6fd1904025f4d76557497dba2eac2a5514b419a799c8616b177bc696f051379a',")
        self.assertEqual((FPGA/'tools/plain_fit_queue_v5.py').read_text(), expected+'\n')
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
            self.assertEqual(helpers['plain_fit_v4.py'], q.PINS['cloud/plain_fit_v4.py'])
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


    def test_aws50_package_full_meter_authority_closure_without_rpc(self):
        # This tiny project is a packaging fixture, not an admitted native DUT.
        # Existing actual six-worker project validation is tested in runner v4.
        host='gfn16-aws-m8i'; context=dict(manifest_sha256='a'*64,source_sha256={},control_sha256={})
        with tempfile.TemporaryDirectory(prefix='aws50-package-test-',dir=FPGA/'artifacts') as directory:
            base=Path(directory).resolve(); source=base/'fixture'; source.mkdir()
            (source/'fixture.txt').write_text('pure fixture only\n')
            variant=dict(path=str(source),project=context,files={},exemption='component_sizing_probe')
            job=dict(id='aws50-test',project_name='aws50-test-project',unit='gfn16-aws50-test.service',scope='component_probe',variants={host:variant})
            topology=dict(hostname=host,observed_at='2026-10-01T17:40:00Z',cpus=[],slots=q.HOSTS[host]['slots'])
            with patch.object(q,'source_variant',return_value=context), patch.object(q.subprocess,'run',side_effect=AssertionError('no RPC/native process permitted')):
                handle,helpers,archive=q.prepare(job,host,'b',base/'prepared',topology,datetime(2026,10,1,17,40,tzinfo=timezone.utc))
            admitted=json.loads((base/'prepared/host-hours.json').read_text())
            self.assertEqual(admitted['rolling24h_cap_usd'],50)
            self.assertEqual(admitted['per_job_charge_usd'],0)
            self.assertEqual(admitted['hourly_rate_usd'],1.5)
            self.assertEqual(helpers['plain_fit_v4.py'],q.PINS['cloud/plain_fit_v4.py'])
            self.assertNotIn('plain_fit_v3.py',helpers)
            for path,pin in admitted['source_evidence_sha256'].items():
                relative=str(Path(path).relative_to(FPGA))
                self.assertEqual(helpers['fpga/'+relative],pin)
            self.assertEqual(helpers['fpga/cloud/host_hours_admit_v2.py'],q.PINS['cloud/host_hours_admit_v2.py'])
            self.assertEqual(helpers['fpga/cloud/host_hours_admit_v1.py'],q.PINS['cloud/host_hours_admit_v1.py'])
            self.assertEqual(helpers['fpga/cloud/aws-daily-cap-user-approval-20261001-v2.json'],q.PINS['cloud/aws-daily-cap-user-approval-20261001-v2.json'])
            self.assertEqual(q.digest(archive.read_bytes()),handle['package_sha256'])


if __name__ == '__main__':
    unittest.main()

