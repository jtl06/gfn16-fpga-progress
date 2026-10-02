import unittest
from fpga.reference import stream27_warm_contexts_native as native
class WarmNativeTests(unittest.TestCase):
    def test_real_core_and_cold_only_normal(self):
        m,files=native.role();self.assertEqual(len(m['build']['sv_sources']),47)
        self.assertEqual(m['build']['parameters'],dict(AW=5,P=8,CONTEXTS=2));self.assertEqual(len(m['steps']),1)
        cpp=files[native.CPP];self.assertIn(b'f.ordinal==0&&tick>=f.start',cpp);self.assertIn(b'f.ordinal==0&&tick==f.correction',cpp)
        self.assertIn(b'S4_WARM_INTERNAL_ADMISSION',cpp);self.assertIn(b'S4_WARM_FINAL_CONTEXT_OWNER56',cpp)
        self.assertIn(b'a_finishes_while_b_active',cpp);self.assertFalse(m['warm_contexts']['full_N_numeric_locally_performed'])
    def test_frozen_arithmetic_reference_reuse_is_include_only(self):
        m,files=native.role();self.assertEqual(files['lineage/'+native.arithmetic.CPP].replace(b's4_threefield_contexts_config_v1.h',b's4_warm_contexts_config_v1.h',1),files[native.arithmetic.CPP])
        self.assertIn(b'canonical_host=0',m['steps'][0]['expected_stdout'].encode())
if __name__=='__main__':unittest.main()
