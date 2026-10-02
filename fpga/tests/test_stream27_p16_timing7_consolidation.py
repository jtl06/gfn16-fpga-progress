"""Read-only metadata/scalar; no candidate/native/numerical reference execution."""
import unittest
from fpga.reference import stream27_p16_timing7_consolidation as c


class Timing7Subset(unittest.TestCase):
    def test_own_exact_ledger(self):
        d=c.scalar_ledger()
        self.assertEqual(d['cold_ordinary_completion'],668026)
        self.assertEqual(d['warm_interval'],8460)
        self.assertEqual(d['cold_primary_cycles'],16174606006)
        self.assertEqual(d['cached_alternate_cycles'],16174605907)
        self.assertEqual(d['special_alternate_cycles']-d['cold_primary_cycles'],65536)
        self.assertIsNone(d['selected_period_ns']);self.assertIsNone(d['projected_seconds'])

    def test_original_calendar_not_inherited(self):
        common=c.common();old=common.source_cycles(65536,dict(warm_interval=8459,carry_done=12557),1911814)['host_done']
        self.assertEqual(c.scalar_ledger()['cold_primary_cycles']-old,1911814)

    def test_completed_source_subset_only(self):
        d=c.completed_subset()
        self.assertEqual(len(d['receipt_index']),7)
        self.assertEqual(len(d['source_binding']['standalone64']),64)
        self.assertTrue(d['source_binding']['exact_fitted64_subset_of_paired75'])
        self.assertEqual(d['direct_traces'][1]['directly_observed_interval'],8460)
        self.assertIsNone(d['pending1000']['numerical_pass'])
        self.assertIsNone(d['final_clock']['selected_period_ns'])
        self.assertFalse(d['promotion_allowed'])


if __name__=='__main__':unittest.main()
