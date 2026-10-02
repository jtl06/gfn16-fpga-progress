"""Integration regression for the actual resized-host observation schema."""
from pathlib import Path
import copy
import json
import unittest
from unittest.mock import patch
from fpga.tools import global_queue_v1 as queue

ROOT=Path(__file__).resolve().parents[1]


class AdmittedPlacementTests(unittest.TestCase):
    def test_actual_resized_tool_paths_and_eight_pairs(self):
        host=queue.load_host(ROOT/'queue/hosts/azure-f32-q2.json')
        self.assertEqual(host['python'],'/home/azureuser/gfn16-worker/native-tools-v3/python-env/bin/python3')
        self.assertEqual(set(host['tool_paths']),set(host['tool_hashes']))
        self.assertEqual(host['tool_paths']['compiler'],'/usr/bin/x86_64-linux-gnu-g++-13')
        self.assertEqual([cpu for lane in host['lanes'] for cpu in lane['cpus']],list(range(16)))
        self.assertTrue(all(lane['ram_gib']==24 for lane in host['lanes']))
        self.assertTrue(all(lane['profiles'][0].startswith('azure-burst16-static') for lane in host['lanes']))
        self.assertTrue(all(len(lane['profiles'])==3 and '-static8g' in lane['profiles'][1]
                            and '-static24g' in lane['profiles'][2] for lane in host['lanes']))
        self.assertEqual(host['aggregate_native_memory_cap_gib'],48)

    def ticket(self,ram=8,host='gfn16-azure-sim-f32',id='own'):
        profile='azure-burst16-static8g01-v1' if ram==8 else 'azure-burst16-static01-v1'
        return dict(id=id,resources=dict(ram_gib=ram),package=dict(profile=profile),dispatch=dict(host=host))

    def run_memory(self,ticket,host,others,available):
        with patch.object(queue,'rows',return_value=others),patch.object(queue,'ssh',return_value={}) as ssh,\
             patch.object(queue,'output',return_value=json.dumps({'mem_available_bytes':available*(1<<30)})):
            queue.memory_admit(ticket,host,Path('/unused-mock-output'))
            return ssh.call_count

    def test_all_burst_caps_and_eight_gib_floor(self):
        host=queue.load_host(ROOT/'queue/hosts/azure-f32-q2.json')
        own=self.ticket();other=self.ticket(ram=40,id='other')
        self.assertEqual(self.run_memory(own,host,[own,other],56),1)
        self.assertEqual(own['dispatch']['memory_check']['other_global_reservation_gib'],40)
        self.assertEqual(own['dispatch']['memory_check']['required_bytes'],56*(1<<30))
        for ram,others in [(8,44),(4,48)]:
            with self.assertRaisesRegex(ValueError,'exceed48'):
                self.run_memory(self.ticket(ram),host,[self.ticket(ram=others,id='other')],64)
        # Legacy4GiB packages retain4GiB, but are included in the shared cap.
        old=self.ticket(4)
        self.run_memory(old,host,[self.ticket(ram=44,id='other')],56)
        self.assertEqual(old['dispatch']['memory_check']['own_cap_gib'],4)
        with self.assertRaisesRegex(ValueError,'fresh own cap'):
            self.run_memory(self.ticket(),host,[other],55)

    def test_gcp24_preexisting_rule_unchanged(self):
        host=queue.load_host(ROOT/'queue/hosts/gcp-c4d-q1.json')
        own=dict(id='gcp-own',resources=dict(ram_gib=24),package=dict(profile='gcp-c4d-static24g01-v1'),dispatch=dict(host=host['name']))
        self.run_memory(own,host,[],56)
        self.assertEqual(own['dispatch']['memory_check']['required_bytes'],56*(1<<30))
        with self.assertRaises(ValueError):self.run_memory(copy.deepcopy(own),host,[],55)

    def test_wrong_burst_floor_or_foreign_profile_rejected(self):
        host=queue.load_host(ROOT/'queue/hosts/azure-f32-q2.json')
        host['memory_host_floor_gib']=4
        with self.assertRaises(ValueError):self.run_memory(self.ticket(),host,[],64)
        host['memory_host_floor_gib']=8
        own=self.ticket();own['package']['profile']='gcp-c4d-static01-v1'
        with self.assertRaises(ValueError):self.run_memory(own,host,[],64)

    def test_full_burst_reservations_wait_before_claim(self):
        host=queue.load_host(ROOT/'queue/hosts/azure-f32-q2.json');host['enabled']=True
        host['observed_mem_available_bytes']=64*(1<<30)
        ticket=self.ticket();ticket.update(needs='verilator',tool_identity=host['tool_identity'],promotion_bound=False)
        ticket['resources'].update(cores=2,threads=1,scratch_gib=4)
        ticket['package']['max_seconds']=3700
        with patch.object(queue,'dependency_state',return_value=(True,'ready')),\
             patch.object(queue,'role_host_compatible',return_value=True),\
             patch.object(queue,'rows',return_value=[self.ticket(ram=48,id='other')]):
            admitted,reason=queue.eligible(ticket,host,host['lanes'][0])
        self.assertFalse(admitted)
        self.assertIn('aggregate',reason)


if __name__=='__main__':unittest.main()
