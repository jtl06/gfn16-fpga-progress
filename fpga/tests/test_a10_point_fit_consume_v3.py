import unittest
from fpga.reference import a10_point_fit_consume_v3 as fit


class MatchedPointFit(unittest.TestCase):
    def test_actual_closed_fit_source_cone_and_area_delta(self):
        result = fit.consume()
        self.assertEqual(result['status'], 'SOURCE_BOUND_NATIVE_COMPLETE_TIMING_FAIL')
        self.assertEqual((result['collected_files'],result['archived_regular_files']), (40,41))
        self.assertEqual(result['slacks'], dict(setup=-2.522,hold=.017,minimum_pulse_width=3.337))
        self.assertEqual(result['resources']['final_registers'], 59357)
        self.assertEqual(result['resources']['place_registers'], 57929)
        self.assertEqual(result['matched_delta']['final_registers'], 2033)
        self.assertTrue(all('pairing_d[' in source for source in result['observed_setup_sources']))
        self.assertFalse(result['audited_clock']); self.assertFalse(result['promotion_allowed'])

    def test_native_delay_split_and_DSP_requirement_retained(self):
        worst = fit.consume()['worst']
        self.assertEqual(worst['data_delay_ns'], 7.565)
        self.assertEqual(worst['native_data_statistics']['IC']['total_delay_ns'], 4.738)
        self.assertEqual(worst['native_data_statistics']['Cell']['total_delay_ns'], 2.570)
        self.assertEqual(worst['native_data_statistics']['uTco']['total_delay_ns'], .257)
        self.assertTrue(any(row['type'] == 'uTsu' and row['incremental_ns'] == -2.770
                            for row in worst['native_required_constraints']))


if __name__ == '__main__':
    unittest.main()
