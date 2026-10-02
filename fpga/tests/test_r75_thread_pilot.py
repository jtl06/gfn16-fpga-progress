"""Captured source identity and actual fixed-physical packet boundaries only."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fpga.tools import global_queue_v1 as q
from fpga.tools import native_profile_variants_v14 as identity
from fpga.tools import native_threaded_wide_package_v3 as package
from fpga.tools import native_threaded_wide_stage_v3 as stage

ROOT=q.FPGA
DATA=ROOT/'artifacts/r75-p8-thread-pilot'


def packet(count):
    folder=DATA/f'threads{count}-v4/packet'
    m=json.loads((folder/'manifest.json').read_text());t=json.loads((folder/'ticket.json').read_text())
    p=dict(archive=str(folder/'package.tar.gz'),sha256=q.sha(folder/'package.tar.gz'),
        ticket_sha256=q.sha(folder/'ticket.json'),manifest_sha256=q.sha(folder/'manifest.json'),
        worker_id=t['id'],profile=t['profile'],native_root=t['native_root'],max_seconds=3700,
        runner='tools/native_threaded_wide_package_v3.py',runner_sha256=m['sources']['tools/native_threaded_wide_package_v3.py'],
        stager=str(ROOT/'tools/native_threaded_wide_stage_v3.py'),stager_sha256=q.sha(ROOT/'tools/native_threaded_wide_stage_v3.py'),
        stager_dependencies=[dict(path=str(ROOT/'tools'/name),sha256=q.sha(ROOT/'tools'/name)) for name in
            ('native_threaded_wide_stage_v1.py','native_package_v3.py','native_package_v2.py')],
        placement=t['placement'],fixed_execution=t['fixed_execution'])
    ticket=dict(schema='gfn16-global-ticket-v1',id=f'r75-p8-threads{count}-q1-v1',owner='dispatcher',
        created='2026-10-01T22:00:00Z',priority='P3',kind='sim',needs='verilator',
        tool_identity='azure-burst16-verilator5032-gcc13-python312-v1',
        resources=dict(cores=8,threads=count,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,
        est_minutes=30,promotion_bound=False,after=[],package=p,allowed_hosts=['gfn16-azure-sim-f32'])
    return folder,m,t,ticket


class R75PilotTests(unittest.TestCase):
    def test_actual_packets_same_source_case_distinct_runtime_identity(self):
        hashes=[]
        for count in (1,8):
            folder,m,t,ticket=packet(count)
            _,_,captured,placement=stage.worker().inspect_archive(folder/'package.tar.gz',ticket['package']['sha256'],ticket['package']['ticket_sha256'])
            self.assertEqual(placement['cpus'],list(range(8,16)))
            self.assertEqual(placement['memory_bytes'],8<<30)
            q.validate(ticket)
            hashes.append(identity.functional_fingerprint(m,t['budget'],folder/'capture/source/fpga')['sha256'])
            original=json.loads((ROOT/package.runtime().P8_ROLE).read_text())
            self.assertEqual(m['steps'],original['steps'])
            self.assertTrue(all(m['sources'][k]==v for k,v in original['sources'].items()))
        self.assertNotEqual(*hashes)

    def test_actual_fixed_union_has_no_overlap_or_extra_physical_inventory(self):
        host=q.load_host(ROOT/'queue/hosts/azure-f32-q2.json')
        self.assertEqual(len(host['lanes']),8)
        views={v['id']:v for v in host['fixed_placements']}
        self.assertEqual(views['burst16-wide815-v1']['cpus'],list(range(8,16)))
        lane=views['burst16-wide815-v1'];observation=dict(free_lanes=[v['id'] for v in host['lanes']])
        self.assertTrue(q.placement_free(host,lane,observation,[]))
        for member in lane['lane_ids']:
            job=dict(dispatch=dict(host=host['name'],lane=member))
            self.assertFalse(q.placement_free(host,lane,observation,[job]))
        self.assertTrue(q.placement_free(host,lane,observation,[dict(dispatch=dict(host=host['name'],lane='azure-burst16-static01-v1'))]))

    def test_runtime_resource_source_count_and_actual_namespace(self):
        folder,m,t,ticket=packet(8);path=folder/'capture/source/fpga/tools/native_threaded_wide_v3.py'
        spec=importlib.util.spec_from_file_location('_r75_actual_capture',path);runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
        selected=runtime.profile(t['profile']);self.assertEqual(len(set(map(tuple,selected['runtime_allocation']['physical_cores']))),8)
        self.assertEqual(len(selected['constituent_pair_locks']),4)
        parent=runtime.parent(t['profile']);self.assertIs(parent.execute.__globals__,parent.__dict__)
        self.assertTrue(callable(parent.MeasuredPopen))
        for kind in ('source','step','count','macro'):
            changed=copy.deepcopy(m)
            if kind=='source':changed['sources'][changed['build']['cpp_source']]='0'*64
            elif kind=='step':changed['steps'][0]['argv']=['{exe}','99']
            elif kind=='count':changed['wide_thread_pilot']['thread_count']=4
            else:changed['build']['cflags'].remove('-DGFN16_RUNTIME_THREADS=8')
            with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError)):
                identity.functional_fingerprint(changed,t['budget'],folder/'capture/source/fpga')

    def test_live_long_uses_captured_helper_not_mutable_workspace(self):
        folder=ROOT/'artifacts/s4-p8-canon1-continuous1000-burst01-packet-v2'
        m=json.loads((folder/'manifest.json').read_text());t=json.loads((folder/'ticket.json').read_text())
        baseline='5a0c17530f6cb4d4e9d3e29607a3c8f2a906ac4d0feec858b45d19102e6f64c8'
        original=identity.load;calls=[]
        def load(path,pin):
            calls.append(path)
            if path==ROOT/'tools/native_long_class_v2.py':raise AssertionError('mutable workspace runtime import')
            return original(path,pin)
        with patch.object(identity,'load',side_effect=load):
            self.assertEqual(identity.functional_fingerprint(m,t['budget'],folder/'capture/source/fpga')['sha256'],baseline)
        self.assertIn(folder/'capture/source/fpga/tools/native_long_class_v2.py',calls)
        old=ROOT/'results/throughput-20260929/threaded-wide-package-v3/packet2-fresh-v2'
        m=json.loads((old/'capture/approved-manifest.json').read_text());t=json.loads((old/'ticket.json').read_text())
        self.assertEqual(identity.functional_fingerprint(m,t['budget'],old/'capture/source/fpga')['sha256'],
            '27665cb8e0fda6464c3d3a67918f967546b6bdef08219e66f4beabfcc8d4c531')

    def test_running_dependency_and_tool_drift_wait_without_cancellation(self):
        upstream=dict(id='upstream',package=dict())
        child=dict(after=[dict(id='upstream',functional_sha256='a'*64)])
        with patch.object(q,'expected_identity',side_effect=q.ConsumerUnavailableError('adoption')):
            self.assertEqual(q.dependency_state(child,{'upstream':upstream}),(False,'waiting native contract PASS: upstream'))
            upstream['result']=dict(status='PASS_expected_contracts')
            self.assertTrue(q.dependency_state(child,{'upstream':upstream})[1].startswith('waiting consumer infrastructure:'))

    def test_real_public_submit_chain_has_only_actual_data_dependency(self):
        with tempfile.TemporaryDirectory() as temporary,patch.object(q,'QUEUE',Path(temporary)):
            for state in ('pending','running','done'):(q.QUEUE/state).mkdir()
            q.atomic(q.QUEUE/'loop-state.json',dict(status='running',consumer_contract=q.CONSUMER_CONTRACT))
            for count in (1,8):
                _,_,_,ticket=packet(count)
                if count==8:
                    ticket.update(after=['r75-p8-threads1-q1-v1'],placement_from='r75-p8-threads1-q1-v1')
                path=q.QUEUE/f'input{count}.json';q.atomic(path,ticket)
                result=q.submit(path)
                accepted=json.loads((q.QUEUE/'pending'/(result['id']+'.json')).read_text())
                wanted=(True,'eligible') if count==1 else (False,'waiting native contract PASS: r75-p8-threads1-q1-v1')
                self.assertEqual(q.dependency_state(accepted),wanted)
                with self.assertRaisesRegex(ValueError,'unique queue id'):q.submit(path)


if __name__=='__main__':unittest.main()
