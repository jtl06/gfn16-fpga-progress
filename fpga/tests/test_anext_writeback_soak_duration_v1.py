"""Scalar/source tests only: no model or large integer generation."""
import unittest
from fpga.reference import anext_writeback_soak_duration_v1 as duration

class F3MeasuredPilotForecast(unittest.TestCase):
    def test_explicit_F3_identity_and_namespace(self):
        self.assertIn('anext-writeback-qualification-continuous-role-v1', str(duration.base.ROLE))
        self.assertIn('anext-writeback-qualification-pilot-role-v1', str(duration.base.PILOT_ROLE))
        self.assertEqual(duration.base.ROLE_SHA, 'f8c142ff564d11f620b1c124651f5d9d2492b1c21ba6e349dffb49f0036bdc48')
        self.assertIs(duration.prepare.__globals__, duration.base.__dict__)
        self.assertIn('anext_writeback_soak_duration_v1.py', duration.base.__file__)
        self.assertEqual(duration.base.normalise.__module__, 'fpga.reference.anext_writeback_soak_output_v1')
        self.assertEqual(duration.base.schedule.__module__, 'fpga.reference.anext_writeback_contract_v2')

    def test_exact_F3_counts_and_units(self):
        value = duration.predict(400.0, 2194717, 17.0)
        self.assertEqual(value['continuous_model_ticks'], 21947089)
        self.assertEqual(value['margin'], 1.75)
        self.assertIn('NOT', value['tick_basis'])
        self.assertIn('10 initial loads', value['conservative_host_work'])
        self.assertAlmostEqual(value['continuous_command_seconds_estimate'], 400.0/2194717*21947089*1.75)
        self.assertEqual(value['full_reference_replay_seconds_estimate'], 44)

    def test_point_upper_counts_and_bad_measurements_reject(self):
        for seconds, count, reference in ((400, 2191417, 17), (400, 2194718, 17),
            (0, 2194717, 17), (400, True, 17), (400, 2194717, 0),
            (float('inf'), 2194717, 17), (400, 2194717, float('nan')),
            (True, 2194717, 17)):
            with self.subTest(seconds=seconds, count=count), self.assertRaises(ValueError):
                duration.predict(seconds, count, reference)

if __name__ == '__main__':
    unittest.main()
