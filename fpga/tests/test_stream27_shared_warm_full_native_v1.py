import unittest

from fpga.reference.stream27_shared_field_v1 import prepare
from fpga.reference.stream27_shared_warm_full_native_v1 import compile_bench


class FullWarmSource(unittest.TestCase):
    def test_real_full_size_uses_same_generator_and_separate_native_reference(self):
        b=prepare(65536,16,0,allow_full_constants=True)
        cpp,header=compile_bench(b,0)
        self.assertIn('genefer_stream27_shared_warm_aw16_p16_f0_v1',header)
        self.assertIn('N=65536,P=16',header)
        self.assertIn('FIRST=8415,SINK=8416,INTERVAL=8459,CORRECTION=12557',header)
        self.assertIn('ref_self_check();Counts counts;',cpp)
        self.assertIn('ref_negacyclic_square(expanded)',cpp)
        self.assertNotIn('for(unsigned a=0;a<N;++a)for(unsigned b=0;b<N;++b)',cpp)
        self.assertIn('INTERVAL+16,CORRECTION+16',cpp)
        self.assertEqual(b['parameters'],dict(AW=16,P=16,CONTEXTS=1,FIELD=0))
        self.assertFalse(b['full_N_numeric_NTT_performed'])


if __name__=='__main__':unittest.main()
