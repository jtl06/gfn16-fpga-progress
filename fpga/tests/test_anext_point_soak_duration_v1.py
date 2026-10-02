import unittest
from fpga.reference import anext_point_soak_duration_v1 as duration


class PointMeasuredPilotForecast(unittest.TestCase):
    def test_explicit_point_roles_and_function_namespace(self):
        self.assertIn('anext-point-qualification-continuous-role-v1', str(duration.base.ROLE))
        self.assertIn('anext-point-qualification-pilot-role-v1', str(duration.base.PILOT_ROLE))
        self.assertEqual(duration.base.ROLE_SHA, 'fe6a0dda35ed7311643f2c9dc9a34f40a9b9017129ca7d0ab2228a7101a23fc0')
        self.assertIs(duration.prepare.__globals__, duration.base.__dict__)
        self.assertIn('anext_point_soak_duration_v1.py', duration.prepare.__globals__['__file__'])
        self.assertEqual(duration.base.normalise.__module__, 'fpga.reference.anext_point_soak_output_v1')

    def test_backend_basis_margin_and_host_work(self):
        value = duration.predict(400.0, 2191417, 17.0)
        self.assertEqual(value['continuous_model_ticks'], 21914089)
        self.assertEqual(value['margin'], 1.75)
        self.assertIn('NOT', value['tick_basis'])
        self.assertIn('10 initial loads', value['conservative_host_work'])
        self.assertEqual(value['full_reference_replay_seconds_estimate'], 44)

    def test_wrong_counts_or_nonfinite_measurement(self):
        for seconds, count, reference in ((400, 2191418, 17), (0, 2191417, 17),
            (400, True, 17), (400, 2191417, 0), (float('inf'), 2191417, 17),
            (400, 2191417, float('nan')), (True, 2191417, 17)):
            with self.subTest(seconds=seconds, count=count), self.assertRaises(ValueError):
                duration.predict(seconds, count, reference)


if __name__ == '__main__':
    unittest.main()
