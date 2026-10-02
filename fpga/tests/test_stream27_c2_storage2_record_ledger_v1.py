import unittest
from fpga.reference import stream27_c2_storage2_record_ledger_v1 as ledger


class LedgerTests(unittest.TestCase):
    def test_pinned_full_source_and_native_joint_solo_events(self):
        result = ledger.check_native()
        self.assertEqual(result['warm_edges'], [21221, 25450])
        self.assertEqual(result['publication_edges'], [680685, 1340148])
        self.assertEqual(result['canonical_allocation_edges'], [21223, 680686])

    def test_equal_pair_projection_includes_both_serial_finalizations(self):
        result = ledger.sample('14')
        self.assertEqual(result['pair_completion_cycles'], 16173357856)
        self.assertEqual(result['conditional_pair_seconds'], '226.427009984')
        self.assertEqual(result['amortized_seconds_per_test'], '113.213504992')
        self.assertFalse(result['audited_period_used'])
        self.assertFalse(result['promotion_allowed'])
        self.assertEqual(result['publication_edges'][1] - result['publication_edges'][0],
                         ledger.ROWS + 10*ledger.N + 7)

    def test_unequal_counts_do_not_force_A_priority_or_reduce_remaining_interval(self):
        result = ledger.ledger((100, 1))
        self.assertEqual(result['publication_order'], [1, 0])
        self.assertEqual(result['first_edges'], [204, 4433])
        self.assertEqual(result['per_context_interval'], 8459)
        self.assertEqual(result['launch_gaps'], [4229, 4230])
        self.assertGreaterEqual(result['canonical_allocation_edges'][0], result['publication_edges'][1]+1)

    def test_each_special_adds_one_N_service_not_every_warm_iteration(self):
        ordinary = ledger.ledger((2, 2))
        a = ledger.ledger((2, 2), special=(True, False))
        b = ledger.ledger((2, 2), special=(False, True))
        both = ledger.ledger((2, 2), special=(True, True))
        self.assertEqual(a['pair_completion_cycles'] - ordinary['pair_completion_cycles'], ledger.N)
        self.assertEqual(b['pair_completion_cycles'] - ordinary['pair_completion_cycles'], ledger.N)
        self.assertEqual(both['pair_completion_cycles'] - ordinary['pair_completion_cycles'], 2*ledger.N)
        self.assertEqual(both['warm_edges'], ordinary['warm_edges'])

    def test_full32_counts_and_no_clock_or_empty_job_inference(self):
        result = ledger.ledger((65537, 1000))
        self.assertEqual(result['counts'], [65537, 1000])
        self.assertFalse(result['hardware_clock_claim'])
        for bad in ((0, 1), (True, 2), (1, 2**32)):
            with self.assertRaises(ValueError):
                ledger.ledger(bad)
        with self.assertRaises(ValueError):
            ledger.ledger(enabled=(False, False))
        for period in ('NaN', 0, -1):
            with self.assertRaises(ValueError):
                ledger.sample(period)


if __name__ == '__main__':
    unittest.main()
