import unittest
from fpga.reference import stream27_context_storage_combo_boundary_continuous as m


class CombinedContinuous(unittest.TestCase):
    def test_prefix_and_original_calendar(self):
        self.assertEqual([r[:100] for r in m.bits()], m.bits(100))
        self.assertEqual(m.config()['interval'], 8459)
        self.assertEqual(m.config()['threads'], 1)
        self.assertEqual(m.config()['joint_first_edges'], [204, 4433])
        self.assertEqual(m.config()['doubles'], 1022)

    def test_only_header_compiled_delta(self):
        role, files = m.role()
        self.assertEqual(role['r84']['continuous']['compiled_source_delta'], [m.HEADER])
        self.assertEqual(role['context_storage_combo_boundary']['own_long']['own_calendar']['frames'], 2000)
        self.assertEqual(role['context_storage_combo_boundary']['own_long']['own_calendar']['lease_peak'], 3)
        pilot = (m.PILOT_SOURCE / m.HEADER).read_bytes()
        self.assertEqual(files[m.HEADER], m.header(pilot))
        with self.assertRaises(ValueError):
            m.header(pilot.replace(b'INTERVAL=8459', b'INTERVAL=8460'))

    def test_bounded_estimate_not_native(self):
        result = m.predict(300., 500.)
        self.assertEqual(result['continuous_command_seconds_estimate'], 5250.)
        self.assertEqual(result['overall_seconds_estimate'], 6200.)
        self.assertTrue(result['fits_finite_shape'])
        self.assertFalse(m.predict(700., 900.)['fits_finite_shape'])


