import copy
import json
import unittest
from fpga.reference import a10_upper_fit_consume_v2 as fit


class UpperPhysicalConsumption(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = fit.consume()
        cls.ledger = json.loads((fit.OUTPUT/'path-ledger-v2.json').read_text())
        cls.sta = (fit.DOSSIER/'evidence/project/output_files/probe.sta.rpt').read_text()
        cls.report = (fit.DOSSIER/'evidence/project/output_files/probe.fit.rpt').read_text()
        cls.tables = fit.parser().v1

    def test_exact_closed_native_failure_and_matched_delta(self):
        result = self.result
        self.assertEqual(result['status'], 'SOURCE_BOUND_NATIVE_COMPLETE_SETUP_AND_HOLD_FAIL')
        self.assertEqual((result['source_files'], result['collected_files'], result['archived_regular_files']), (9,40,41))
        self.assertEqual(result['slack_delta_ns'], dict(setup=1.505, hold=-.157, minimum_pulse_width=.015))
        self.assertEqual(result['matched_resource_delta'], dict(needed_ALM=65, raw_placed_ALM=419, LAB=-78,
            final_registers=1589, place_registers=1536, M20K=0, DSP=0, RAM_bits=0))
        self.assertFalse(result['audited_clock']); self.assertFalse(result['promotion_allowed'])

    def test_real_hold_min_delay_equation_and_existing_repair(self):
        hold = self.result['hold_diagnosis']
        self.assertEqual(hold['classes'], dict(row_tag=4,prefix_pipe=5,dif_pipe=1))
        self.assertEqual((hold['launch_clock_ns'], hold['latch_clock_after_pessimism_ns']), (4.942,5.124))
        self.assertEqual((hold['arrival_ns'], hold['required_ns'], hold['hold_requirement_ns']), (5.460,5.600,.476))
        self.assertEqual(hold['worst_pair_estimated_added_delay_ns'], .355)
        self.assertFalse(hold['period_reduction_alone_repairs_hold'])

    def test_measured_setup_route_cone_not_DSP_endpoint_guess(self):
        worst = self.result['worst_setup']
        self.assertEqual(worst['native_logic_levels'], 3)
        self.assertEqual(worst['native_data_statistics']['IC']['total_delay_ns'], 8.278)
        self.assertEqual(worst['native_data_statistics']['IC']['native_percent'], 91)
        self.assertEqual(worst['native_required_constraints'][0]['incremental_ns'], .292)
        self.assertEqual(self.result['source_cycle_delta'], 0)

    def test_negative_rejects_virtual_IO_relabel(self):
        ledger = copy.deepcopy(self.ledger); ledger['hold']['paths'][0]['source'] = 'host_read_data[7]'
        with self.assertRaisesRegex(ValueError, 'HOLD_NOT_INTERNAL_PIPELINE'):
            fit.hold_evidence(self.sta, ledger, self.report, self.tables)

    def test_negative_rejects_period_or_exception_change(self):
        for key, value in (('relationship_ns',8), ('native_sdc_exception','False Path')):
            ledger = copy.deepcopy(self.ledger); ledger['hold']['paths'][0][key] = value
            with self.assertRaisesRegex(ValueError, 'INTERNAL_HOLD_RELATIONSHIP'):
                fit.hold_evidence(self.sta, ledger, self.report, self.tables)

    def test_negative_rejects_slack_reinterpretation(self):
        altered = self.sta.replace('; Data Arrival Time               ; 5.460', '; Data Arrival Time               ; 5.600', 1)
        self.assertNotEqual(altered, self.sta)
        with self.assertRaisesRegex(ValueError, 'HOLD_RAW_EQUATION'):
            fit.hold_evidence(altered, self.ledger, self.report, self.tables)


if __name__ == '__main__':
    unittest.main()
