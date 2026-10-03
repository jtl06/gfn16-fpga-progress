import unittest
from fpga.reference import stream27_r15_compute_full_wrap_native as p


class Wrap(unittest.TestCase):
    def test_monitor_and_driver_source_only(self):
        m,f,b=p.role()
        self.assertEqual(len(b['files']),60)
        self.assertEqual(len(m['build']['sv_sources']),61)
        self.assertEqual(m['build']['parameters']['LEAN_BUILD'],1)
        cpp=f[p.CPP].decode()
        self.assertIn('d.cycles=(k<<32)',cpp)
        self.assertIn('age==20000',cpp)
        self.assertIn('cold_accepts==2',cpp)
        self.assertIn('R15_COMPUTE_FULL_WRAP_PASS',cpp)
        self.assertFalse(m['r15_full_wrap']['expected_bank_oracle'])
        self.assertTrue(all(f['rtl/'+n]==t.encode() for n,t in b['files'].items()))


if __name__=='__main__':unittest.main()
