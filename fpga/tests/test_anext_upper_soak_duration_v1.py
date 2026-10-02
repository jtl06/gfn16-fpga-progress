import unittest
from fpga.reference.anext_upper_soak_duration_v1 import predict
class BackendCycleForecast(unittest.TestCase):
    def test_units_counts_and_margin(self):
        x=predict(400.0,2191417,17.0)
        self.assertEqual(x['continuous_model_ticks'],21914089)
        self.assertEqual(x['margin'],1.75)
        self.assertLess(x['continuous_command_seconds_estimate'],7000)
        self.assertIn('NOT',x['tick_basis'])
        self.assertEqual(x['full_reference_replay_seconds_estimate'],44)
    def test_wrong_counter_or_nonpositive_measurement(self):
        for seconds,count,reference in ((400,2191418,17),(0,2191417,17),(400,True,17),(400,2191417,0),(float('inf'),2191417,17),(400,2191417,float('nan'))):
            with self.assertRaises(ValueError):predict(seconds,count,reference)
if __name__=='__main__':unittest.main()
