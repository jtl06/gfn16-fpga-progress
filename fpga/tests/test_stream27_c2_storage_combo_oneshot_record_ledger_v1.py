import unittest

from fpga.reference import stream27_c2_storage_combo_oneshot_record_ledger_v1 as own


class OneShotRecordLedgerTests(unittest.TestCase):
    def test_source_join_and_unchanged_accepted_calendar(self):
        b=own.source()
        self.assertEqual(len(b['files']),55)
        self.assertEqual(b['context_storage_combo_oneshot']['added_state_bits'],2)

    def test_finite_and_sample_event_arithmetic(self):
        v=own.ledger()
        self.assertEqual(v['warm_edges'],[21221,25450])
        self.assertEqual(v['publication_edges'],[680685,1340148])
        self.assertFalse(v['inherited_native_or_clock'])
        s=own.sample()
        self.assertEqual(s['pair_completion_cycles'],16173357856)
        self.assertEqual(s['old_source_alias_edges_in_horizon'],
                         [8436,4294975732,8589943028,12884910324])
        self.assertEqual(s['fixed_cold_accept_edges'],[8436])
        self.assertFalse(s['promotion_allowed'])
        self.assertNotIn('assumed_period_ns',s)

    def test_own_clock_is_not_inherited(self):
        v=own.sample('16')
        self.assertEqual(v['conditional_pair_seconds'],'258.773725696')
        self.assertFalse(v['audited_period_used'])
        self.assertTrue(v['own_full_long_clock_review_pending'])


if __name__ == '__main__':
    unittest.main()
