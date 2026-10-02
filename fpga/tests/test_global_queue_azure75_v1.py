"""Narrow actual-packet75 intake checks; no remote/native calls."""
import copy
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fpga.tools import global_queue_v1 as q
from fpga.tools import native_class_package_azure75_v1 as package
from fpga.tools import native_profile_variants_v14 as identity
from fpga.tools import native_stage_azure75_v1 as stage

DATA=q.FPGA/'results/throughput-20260929/azure75-native-intake-v1'


def metadata(directory):
    native=json.loads((directory/'ticket.json').read_text())
    manifest=json.loads((directory/'manifest.json').read_text())
    profile=native['profile'];cap=8 if '-static8g' in profile else 4
    return dict(archive=str(directory/'package.tar.gz'),sha256=q.sha(directory/'package.tar.gz'),
        ticket_sha256=q.sha(directory/'ticket.json'),manifest_sha256=q.sha(directory/'manifest.json'),
        worker_id=native['id'],profile=profile,native_root=native['native_root'],max_seconds=3700,
        runner='tools/native_class_package_azure75_v1.py',
        runner_sha256=manifest['sources']['tools/native_class_package_azure75_v1.py'],
        stager=str(q.FPGA/'tools/native_stage_azure75_v1.py'),stager_sha256=q.sha(q.FPGA/'tools/native_stage_azure75_v1.py'),
        stager_dependencies=[dict(path=str(q.FPGA/'tools'/name),sha256=q.sha(q.FPGA/'tools'/name))
            for name in ('native_package_v3.py','native_package_v2.py')],
        tool_identity='azure-burst16-verilator5032-gcc13-python312-v1',
        resources=dict(cores=2,threads=1,ram_gib=cap,scratch_gib=4),refreshable=True)


class Azure75Tests(unittest.TestCase):
    def test_two_actual_closed4_and8_packets_safe_stage_identity(self):
        for name in ('pilot24','reset-aw5-fresh'):
            directory=DATA/name/'packet';native=json.loads((directory/'ticket.json').read_text())
            _,ticket,manifest,profile=stage.worker().inspect_archive(directory/'package.tar.gz',
                q.sha(directory/'package.tar.gz'),q.sha(directory/'ticket.json'))
            self.assertEqual(ticket['max_seconds'],3700)
            self.assertEqual(ticket['budget']['max_seconds'],3715)
            self.assertEqual(ticket['budget']['schema'],'azure-host-hours-budget-v5')
            value=identity.functional_fingerprint(manifest,ticket['budget'],directory/'capture/source/fpga')
            self.assertEqual(value['sha256'],json.loads((DATA/name/'refresh-receipt.json').read_text())['functional_sha256'])
            self.assertFalse(value['fresh_budget_admission_conferred'])

    def test_exact_authority_freshness_credit_and_unchanged_full_runtime(self):
        directory=DATA/'reset-aw5-fresh/packet'
        native=json.loads((directory/'ticket.json').read_text())
        manifest=json.loads((directory/'manifest.json').read_text())
        selected=package.worker(native['budget']).load('native_class_burst8_v1.py').profile(native['profile'])
        receipt=package.binding(native['budget'],selected,manifest)
        self.assertEqual(receipt['rolling24h_cap_usd'],75)
        self.assertEqual(receipt['max_seconds'],3715)
        for change in ({'max_seconds':10815},{'checker_sha256':'0'*64},{'daily_cap_authority':{}}):
            altered=dict(native['budget'],**change)
            with self.assertRaises((ValueError,KeyError)):
                package.meter().validate_budget(altered,'gfn16-azure-sim-f32',3715)
        provider=json.loads((DATA/'provider-fresh-v1.json').read_text())
        stamp=datetime.fromisoformat(provider['observed_at_utc'])
        from datetime import timedelta
        with self.assertRaises(ValueError):
            package.meter().validate_budget(native['budget'],'gfn16-azure-sim-f32',3715,now=stamp+timedelta(seconds=901))

    def test_real_same_id_update_preserves_source_dependency_and_created(self):
        original=q.registry()['anext-field-reset-aw5-q1-v1']
        fresh=copy.deepcopy(original);fresh['packages']=q.packages(fresh)+[metadata(DATA/'reset-aw5-fresh/packet')]
        fresh.pop('package',None);fresh.pop('package_variants',None)
        q.validate(fresh)
        self.assertEqual(q.expected_identity(original),q.expected_identity(fresh))
        with tempfile.TemporaryDirectory() as temporary,patch.object(q,'QUEUE',Path(temporary)):
            for state in ('pending','running','done'):(q.QUEUE/state).mkdir()
            q.atomic(q.QUEUE/'pending'/(original['id']+'.json'),original)
            q.atomic(q.QUEUE/'loop-state.json',dict(status='running',consumer_contract=q.CONSUMER_CONTRACT))
            input_path=q.QUEUE/'update-input.json';q.atomic(input_path,fresh)
            result=q.update_pending(input_path)
            self.assertEqual(result['status'],'pending_updated')
            observed=json.loads((q.QUEUE/'pending'/(original['id']+'.json')).read_text())
            for key in ('id','owner','created','after'):
                self.assertEqual(observed.get(key),original.get(key))

    def test_current_consumer_and_strict_resource_family(self):
        original=q.registry()['anext-field-reset-aw5-q1-v1']
        fresh=copy.deepcopy(original);fresh['packages']=q.packages(fresh)+[metadata(DATA/'reset-aw5-fresh/packet')]
        fresh.pop('package',None);fresh.pop('package_variants',None)
        with tempfile.TemporaryDirectory() as temporary,patch.object(q,'QUEUE',Path(temporary)):
            with self.assertRaisesRegex(ValueError,'actual running consumer registry adoption'):
                q.require_consumer_adoption(fresh)
        changed=copy.deepcopy(fresh);changed['packages'][-1]['resources']['threads']=2
        with self.assertRaises(ValueError):q.validate(changed)


if __name__=='__main__':unittest.main()
