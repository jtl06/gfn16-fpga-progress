"""Bounded oracle and exact generic field-step validator; no HDL/worker use."""
import platform
import unittest
from unittest.mock import patch
from fpga.reference import root_lookahead_field_v2 as f
from fpga.reference import merged_negacyclic27_model as math


class FieldIntegrationTests(unittest.TestCase):
    def test_small_direct_polynomial_and_frozen_domain_phases(self):
        for aw in (1,2,3,4,5,6,7,8):
            for field in range(3):
                text,receipt=f.corpus(aw,field)
                self.assertEqual(receipt['readbacks'],20*(1<<aw))
                self.assertEqual(len(text.splitlines()),2+4*6)

    def test_phase_roundtrip(self):
        for field in math.FIELDS:
            a=[(13*i*i+7)%field.p for i in range(32)]
            forward=f.cyclic(a,pow(math.psi_for(32,field),2,field.p),field.p)
            inverse=f.cyclic(forward,pow(math.psi_for(32,field),-2,field.p),field.p,inverse=True)
            self.assertEqual(inverse,[32*x%field.p for x in a])

    def test_local_full_numeric_generation_rejects_before_work(self):
        with patch.object(platform,'system',return_value='Darwin'):
            with self.assertRaisesRegex(ValueError,'admitted aethia'):
                f.corpus(16,0)

    def test_footer_and_scope_negatives(self):
        text,receipt=f.corpus(5,0)
        config=dict(aw=5,p=104857601,runtime_threads=1)
        good='F2_FIELD_PASS aw=5 p=104857601 cases=4 operations=20 readbacks=640 aborts=10 faults=11 phase_cycles=20,50,8,51,20 threads=1\n'
        output=f.validate(good,'',0,config,{'vectors':text})
        self.assertEqual(output['paired_parent_candidate_cycle_delta'],0)
        for bad in (good.replace('faults=11','faults=10'),good.replace('threads=1','threads=2'),
                    good.replace('cycles=20','cycles=0'),good.replace('aw=5','aw=16'),good+'trailing\n'):
            with self.assertRaises(ValueError):f.validate(bad,'',0,config,{'vectors':text})
        for code,stderr in ((1,''),(0,'unexpected\n')):
            with self.assertRaises(ValueError):f.validate(good,stderr,code,config,{'vectors':text})

    def test_build_identity_and_thread_geometry(self):
        spec=f.integration_build(16,2,2)
        self.assertEqual(spec['parameters']['P'],67239937)
        self.assertEqual(spec['runtime_threads'],2)
        self.assertTrue(spec['no_launcher_clone'])
        with self.assertRaises(ValueError):f.integration_build(5,0,2)
        with self.assertRaises(ValueError):f.integration_build(16,0,4)


if __name__=='__main__':unittest.main()
