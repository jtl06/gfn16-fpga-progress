import copy
import json
import unittest
from fpga.reference import a10_writeback_fit_consume_v1 as fit


class F3PhysicalConsumption(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=fit.consume()
        cls.ledger=json.loads((fit.OUTPUT/'path-ledger-v2.json').read_text())
        cls.sta=(fit.DOSSIER/'evidence/project/output_files/probe.sta.rpt').read_text()

    def test_exact_closed_terminal_cost_and_context(self):
        r=self.result
        self.assertEqual((r['source_files'],r['collected_files'],r['archived_regular_files']),(9,40,41))
        self.assertEqual(r['slack_delta_ns'],dict(setup=.274,hold=.158,minimum_pulse_width=-.002))
        self.assertEqual(r['resource_delta'],dict(needed_ALM=7051,raw_placed_ALM=7196,LAB=1718,
            final_registers=5295,place_registers=5378,M20K=0,DSP=0,RAM_bits=0))
        self.assertFalse(r['comparison_is_perfectly_host_worker_matched'])
        self.assertFalse(r['hold_repair_causally_proven']);self.assertFalse(r['audited_clock'])

    def test_actual_remaining_cone_and_positive_internal_hold(self):
        r=self.result
        self.assertTrue(r['classifications']['no_butterfly_output_in_retained_setup_top10'])
        self.assertEqual(r['worst_setup']['native_data_statistics']['IC']['total_delay_ns'],6.695)
        self.assertEqual(r['worst_setup']['native_logic_levels'],10)
        self.assertEqual(r['classifications']['hold_classes'],dict(row_tag=8,prefix_pipe=2))
        self.assertEqual((r['hold_equation']['arrival_ns'],r['hold_equation']['required_ns']),(2.744,2.726))
        self.assertTrue(r['hold_equation']['missing_IC_statistic_is_not_measured_zero'])

    def test_negative_rejects_wrong_setup_source_and_exception(self):
        for key,value in (('source','child|child|arithmetic[0].butterfly|y0[0]'),('native_sdc_exception','False Path')):
            ledger=copy.deepcopy(self.ledger);ledger['setup']['paths'][0][key]=value
            with self.assertRaisesRegex(ValueError,'REAL_RUNTIME_SIZE_TO_RAM'):fit.cones(ledger)

    def test_negative_rejects_hold_as_period_or_IO(self):
        ledger=copy.deepcopy(self.ledger);ledger['hold']['paths'][0]['relationship_ns']=8
        with self.assertRaisesRegex(ValueError,'INTERNAL_MIN_DELAY'):fit.cones(ledger)
        ledger=copy.deepcopy(self.ledger);ledger['hold']['paths'][0]['source']='virtual_read_data[0]'
        with self.assertRaisesRegex(ValueError,'HOLD_REAL_PIPELINE'):fit.cones(ledger)

    def test_negative_rejects_raw_hold_equation_tamper(self):
        altered=self.sta.replace('; Data Arrival Time               ; 2.744','; Data Arrival Time               ; 2.726',1)
        self.assertNotEqual(altered,self.sta)
        with self.assertRaisesRegex(ValueError,'HOLD_RAW_EQUATION'):
            fit.hold_equation(altered,self.ledger,fit.upper.parser().v1)


if __name__=='__main__':unittest.main()
