import unittest
from fpga.reference import track_a7_stage_trace_v2 as a
from fpga.tests.test_track_a7_stage_trace_v1 import events


class A7CompleteOrderTotals(unittest.TestCase):
    def test_all_orders_have_totals_and_tail_witness_is_actual_last_writer(self):
        result=a.analyze(256,events())
        names=set(result['transitions'][0]['orders'])
        self.assertEqual(set(result['totals_per_square']['1']),names)
        witness=a.missing_interlock_witness()
        self.assertEqual((witness['bank'],witness['row'],witness['read_edge'],witness['required_after']),(1,0,2,8))
        self.assertFalse(result['threshold_met'])


if __name__=='__main__':unittest.main()
