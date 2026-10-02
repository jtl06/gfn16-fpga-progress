"""Memory-only Azure24 intake/admission; no native/transport execution."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fpga.tools import global_queue_v1 as q


class Burst24QueueTests(unittest.TestCase):
    def setUp(self):
        self.host=q.load_host(q.FPGA/'queue/hosts/azure-f32-q2.json')
        self.host['observed_mem_available_bytes']=64*(1<<30)
        self.update=json.loads((q.FPGA/'results/throughput-20260929/azure-burst24-anext-point-v1/global-pending-update-v1.json').read_text())

    def ticket(self,ram=24,identifier='own'):
        value=copy.deepcopy(self.update)
        value['id']=identifier;value.pop('after',None);value.pop('packages',None);value.pop('package_variants',None)
        value['resources']=dict(cores=2,threads=1,ram_gib=ram,scratch_gib=4)
        value['package']=dict(profile='azure-burst16-static24g01-v1' if ram==24 else 'azure-burst16-static8g01-v1',
                              resources=value['resources'],max_seconds=3700,tool_identity=self.host['tool_identity'])
        value['dispatch']=dict(host=self.host['name'])
        return value

    def test_same_eight_lanes_immutable_old_caps_and_exact_pins(self):
        self.assertEqual([l['cpus'] for l in self.host['lanes']],[[i,i+1] for i in range(0,16,2)])
        self.assertTrue(all(len(l['profiles'])==3 and l['ram_gib']==24 for l in self.host['lanes']))
        self.assertEqual(self.host['aggregate_native_memory_cap_gib'],48)
        self.assertEqual(self.host['memory_host_floor_gib'],8)
        self.assertEqual(set(self.host['lanes'][0]['profile_ram_gib'].values()),{4,8,24})
        self.assertEqual(self.host['memory_envelope_pins']['azure-burst16-static24g01-v1'],
                         '83e6b6ccb3de25fa266e9da52262e6461498f9cd0ea2a462cfafcd8d991e3e59')

    def test_preclaim_headroom_and_aggregate_boundaries(self):
        own=self.ticket();other=self.ticket(24,'other')
        for available,other_cap,accepted in ((56,24,True),(55,24,False),(36,4,True),(35,4,False),(64,28,False)):
            self.host['observed_mem_available_bytes']=available*(1<<30)
            other['package']['resources']['ram_gib']=other_cap
            with patch.object(q,'rows',return_value=[other]),patch.object(q,'role_host_compatible',return_value=True):
                self.assertEqual(q.eligible(own,self.host,self.host['lanes'][0])[0],accepted)
        # Azure24 does not inherit the unrelated GCP56GiB initial rule.
        self.host['observed_mem_available_bytes']=36*(1<<30)
        other['package']['resources']['ram_gib']=4
        with patch.object(q,'rows',return_value=[other]),patch.object(q,'role_host_compatible',return_value=True):
            self.assertTrue(q.eligible(own,self.host,self.host['lanes'][0])[0])

    def test_larger_lane_capacity_cannot_relabel_smaller_package_cap(self):
        own=self.ticket();own['minimum_ram_gib']=4
        for declared_cap in (4,8):
            own['package']['resources']['ram_gib']=declared_cap
            self.assertEqual(q.matching_packages(own,self.host,self.host['lanes'][0]),[])

    def test_prelaunch_rechecks_and_records_selected_envelope(self):
        own=self.ticket();other=self.ticket(4,'other')
        with patch.object(q,'rows',return_value=[own,other]),patch.object(q,'ssh',return_value={}),\
             patch.object(q,'output',return_value=json.dumps(dict(mem_available_bytes=36*(1<<30)))):
            q.memory_admit(own,self.host,Path('/unused-mock-output'))
        receipt=own['dispatch']['memory_check']
        self.assertEqual(receipt['required_bytes'],36*(1<<30))
        self.assertEqual(receipt['own_cap_gib'],24)
        self.assertEqual(receipt['other_global_reservation_gib'],4)
        self.assertEqual(receipt['source_profile_sha256'],self.host['memory_envelope_pins'][own['package']['profile']])
        with patch.object(q,'rows',return_value=[other]),patch.object(q,'ssh',return_value={}),\
             patch.object(q,'output',return_value=json.dumps(dict(mem_available_bytes=35*(1<<30)))):
            with self.assertRaisesRegex(ValueError,'fresh own cap'):q.memory_admit(own,self.host,Path('/unused-mock-output'))

    def test_actual_update_intake_isolated_and_idempotent(self):
        q.validate(self.update)
        known=q.registry()
        # Reconstruct the original saved unclaimed two-GCP input, not the
        # current actual claimed/running record: this test never rehosts it.
        prior=copy.deepcopy(self.update)
        prior['packages']=[p for p in q.packages(prior) if p['profile'].startswith('gcp-')]
        prior.pop('package_variants',None);prior.pop('package',None)
        known[self.update['id']]=prior
        with tempfile.TemporaryDirectory() as directory,patch.object(q,'QUEUE',Path(directory)),patch.object(q,'registry',return_value=known):
            target=Path(directory)/'pending'/f"{prior['id']}.json"
            q.atomic(target,prior)
            inputs=Path(directory)/'input.json';q.atomic(inputs,self.update)
            result=q.update_pending(inputs)
            self.assertEqual(result['status'],'pending_updated')
            saved=json.loads(target.read_text())
            self.assertEqual(saved['created'],prior['created'])
            self.assertEqual(q.expected_identity(saved),q.expected_identity(prior))
            self.assertEqual(len(q.packages(saved)),4)
            with self.assertRaisesRegex(ValueError,'unique queue id'):q.submit(inputs)


if __name__=='__main__':unittest.main()
