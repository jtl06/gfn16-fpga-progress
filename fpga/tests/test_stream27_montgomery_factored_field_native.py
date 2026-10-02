import json
import re
import unittest
from fpga.reference import stream27_montgomery_factored_field_native as s

class FactoredFieldRoles(unittest.TestCase):
    def test_normal_closed_snapshot_calendar_and_numeric_donor(self):
        for aw in (5,8):
            for field in range(3):
                manifest,files=s.role(aw,16,field)
                self.assertEqual(manifest['test_role'],'normal')
                self.assertEqual(manifest['build']['parameters'],dict(AW=aw,P=16,CONTEXTS=1))
                self.assertIn('stream27_shared_reference_ntt_v1.h',files[s.CPP].decode())
                self.assertIn('ref_self_check();',files[s.CPP].decode())
                self.assertTrue(all(re.fullmatch('[a-z][a-z0-9-]*',item['name']) for item in manifest['steps']))
                r=manifest['rtl_readiness'];snapshot=r['source_snapshot']
                self.assertEqual(r['candidate_source_sha256'],s.sha(s.canonical(snapshot)))
                self.assertTrue(all(manifest['sources'][name]==pin for name,pin in snapshot.items()))
                footer=manifest['steps'][0]['expected_stdout']
                self.assertIn(f'aw={aw} p=16 field={field}',footer)
                self.assertIn(f'physical_words={9*(1<<aw)} ',footer)
                self.assertFalse(manifest['l3_binding']['leaf']['calendar_changed'])
                self.assertFalse(manifest['l3_binding']['leaf']['whole_P16_GO'])
    def test_parent_correction_mode_and_frozen_instance_delta(self):
        self.assertEqual(s.sha((s.ROOT/s.PARENT).read_bytes()),'daa45b2d5c614f8ea2b791f993cc22c5cc1f5e215f307242785542b109e29865')
        bundle=s.field_bundle(5,16,0)
        self.assertNotIn('CORR_SERIAL_BFS',bundle['parameters'])
        self.assertEqual(bundle['geometry']['n'],32)
        self.assertEqual(bundle['montgomery_factored']['R'],1<<32)

if __name__=='__main__':unittest.main()
