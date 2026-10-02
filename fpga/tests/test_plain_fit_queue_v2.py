"""Azure capture-clock ordering regression. No provider/native calls."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

FPGA=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
q=load('plain_queue_v2_clock',FPGA/'tools/plain_fit_queue_v2.py')
legacy=load('plain_queue_v1_frozen',FPGA/'tools/plain_fit_queue_v1.py')
HOST='gfn16-azure-f16'


class ClockTests(unittest.TestCase):
    def fixture(self):
        project=FPGA/'results/throughput-20260929/a10-field-physical-probe-v1/project-workers4'
        variant=q.variant_descriptor(project,HOST,exemption='component_sizing_probe')
        job=dict(id='clock-test',priority=1,project_name='clock-test-project',unit='gfn16-clock-test.service',scope='component_probe',
                 allowed_slots={HOST:['d']},variants={HOST:variant},after=[],requires=[])
        topology=json.loads((FPGA/'artifacts/plain-f16-launch-v1/fit-plain-tools-v1/topology.json').read_text())
        quote=json.loads((FPGA/'results/throughput-20260929/azure-sim-resize-r49-v1/provider-inputs-v1.json').read_text())
        observed=datetime.fromisoformat(quote['observed_at_utc'].replace('Z','+00:00'))
        meter=q.module('v2_clock_real_meter','cloud/host_hours_azure_v3.py')
        return job,topology,quote,observed,meter

    def run_prepare(self,when,original_now):
        job,topology,quote,observed,meter=self.fixture(); real_module=q.module
        def modules(name,relative): return meter if relative=='cloud/host_hours_azure_v3.py' else real_module(name,relative)
        with tempfile.TemporaryDirectory(prefix='queue-clock-test-',dir=FPGA/'artifacts') as directory:
            destination=Path(directory).resolve()/'prepared'
            with patch.object(q,'module',side_effect=modules),patch.object(q,'stamp',return_value=when(observed)),patch.object(meter,'provider_inputs',return_value=deepcopy(quote)):
                handle,helpers,archive=q.prepare(job,HOST,'d',destination,topology,original_now(observed))
            admission=json.loads((destination/'host-hours.json').read_text())
            request=json.loads(Path(handle['request']['path']).read_text())
            self.assertEqual(q.digest(archive.read_bytes()),handle['package_sha256'])
            self.assertEqual(request['host_hours_budget']['transition']['sha256'],q.TRANSITION_SHA)
            return admission,request

    def test_exact_one_clock_fix_preserves_frozen_v1_source(self):
        original=(FPGA/'tools/plain_fit_queue_v1.py').read_text(); successor=(FPGA/'tools/plain_fit_queue_v2.py').read_text()
        old="admitted=meter.validate_budget(budget,host,HORIZON,now=now,source_sha256=context['manifest_sha256']); request['host_hours_budget']=budget"
        new=old.replace('now=now','now=stamp()')
        self.assertEqual(original.count(old),1); self.assertEqual(successor,original.replace(old,new))
        self.assertEqual(q.digest(original.encode()),'d17344287b45c41dcd9e581503cbf942af4d5f8f3418fcc7881679cfd5f31f80')

    def test_prepare_validates_after_authenticated_capture_not_tick_time(self):
        admission,request=self.run_prepare(lambda observed:observed+timedelta(seconds=1),lambda observed:observed-timedelta(seconds=1))
        quote_at=datetime.fromisoformat(json.loads((FPGA/'results/throughput-20260929/azure-sim-resize-r49-v1/provider-inputs-v1.json').read_text())['observed_at_utc'].replace('Z','+00:00'))
        self.assertEqual(datetime.fromisoformat(admission['observed_at_utc']),quote_at+timedelta(seconds=1))
        self.assertEqual(admission['per_job_charge_usd'],0); self.assertEqual(request['host_hours_budget']['max_seconds'],21780)

    def test_actual_future_quote_still_refused_no_skew_allowance(self):
        with self.assertRaisesRegex(ValueError,'stale or future'):
            self.run_prepare(lambda observed:observed-timedelta(microseconds=1),lambda observed:observed-timedelta(seconds=2))

    def test_actual_stale_quote_still_refused_no_freshness_relaxation(self):
        with self.assertRaisesRegex(ValueError,'stale or future'):
            self.run_prepare(lambda observed:observed+timedelta(seconds=901),lambda observed:observed-timedelta(seconds=2))


if __name__=='__main__': unittest.main()
