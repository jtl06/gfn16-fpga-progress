import unittest
from fpga.reference import stream27_r14_host_offload_continuous_v1 as m
class Tests(unittest.TestCase):
    def test_finite_forecast(self):
        self.assertTrue(m.predict(100,200)['fits_finite_shape'])
        self.assertFalse(m.predict(1000,1100)['fits_finite_shape'])
        for a,b in ((0,1),(2,1),(float('nan'),2)):
            with self.assertRaises(ValueError):m.predict(a,b)
    def test_exact_count_only_source(self):
        manifest,files=m.role()
        self.assertEqual(len(manifest['build']['sv_sources']),66)
        self.assertEqual(manifest['r14_own_long']['allowed_compiled_delta'],[m.own.HEADER])
        self.assertTrue(manifest['r14_own_long']['forecast_pending'])
        self.assertIn('COUNT=1000,INTERVAL=8464',files[m.own.HEADER].decode())
if __name__=='__main__':unittest.main()
