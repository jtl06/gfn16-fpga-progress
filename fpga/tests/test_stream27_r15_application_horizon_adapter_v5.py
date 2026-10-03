import unittest
from fpga.reference import stream27_r15_application_horizon_adapter_v5 as own


class R15AppHorizonTests(unittest.TestCase):
    def test_wait_is_in_actual_core_edges_only(self):
        m,f,b=own.role();cpp=f[m['build']['cpp_source']].decode()
        self.assertIn('next%12==6',cpp)
        self.assertIn('i<432ull*N',cpp)
        self.assertNotIn('i<36ull*N',cpp)
        self.assertEqual(m['r15_application_horizon_v5']['actual_core_edges_per_N'],36)
        self.assertEqual((m['build']['parameters']['EPOCH_SEED0'],m['build']['parameters']['EPOCH_SEED1']),(0,0))
        for n,t in b['files'].items():self.assertEqual(f['rtl/'+n],t.encode())


if __name__=='__main__':unittest.main()
