import unittest
from fpga.reference.stream27_shared_field_v2 import prepare
from fpga.reference.stream27_shared_warm_small_native_v1 import compile_bench
from fpga.reference.stream_ntt_model import FIELDS


class SmallNativeSource(unittest.TestCase):
    def test_all_fields_p16_schoolbook_and_explicit_calendar(self):
        for field in range(3):
            b=prepare(32,16,field);cpp,header=compile_bench(b,field)
            self.assertIn('N=32,P=16',header)
            self.assertIn('PRIME='+str(FIELDS[field][0]),header)
            self.assertIn('FIRST=78,SINK=79,INTERVAL=126,CORRECTION=126',header)
            self.assertIn('for(unsigned a=0;a<N;++a)for(unsigned b=0;b<N;++b)',cpp)
            self.assertIn('S4_SHARED_AW5_F'+str(field)+'_PASS',cpp)
            self.assertEqual(b['parameters'],dict(AW=5,P=16,CONTEXTS=1,FIELD=field))


if __name__=='__main__':unittest.main()
