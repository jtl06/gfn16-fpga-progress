import unittest

from fpga.reference import stream27_c2_storage_combo_boundary_record_ledger_v1 as ledger


class R2LedgerTests(unittest.TestCase):
    def test_own_source_exact_final_service_and_calendar(self):
        b = ledger.source()
        self.assertEqual(len(b['files']), 54)
        self.assertEqual(b['geometry']['correction_cache_latency'], 78)
        value = ledger.ledger()
        self.assertEqual(value['publication_edges'], [680685, 1340148])
        self.assertFalse(value['parent_native_PASS_inherited'])
        self.assertFalse(value['promotion_allowed'])

    def test_actual_own_full_gate_and_footer_join(self):
        value = ledger.check_native()
        self.assertEqual(value['gate_id'], 's4-p16-c2-combo-r2-full-normal-q1-v1')
        self.assertEqual(value['evidence_scope'], 'OWN_ADMITTED_NATIVE_CALENDAR_AND_FULL54_SOURCE_JOIN')
        self.assertEqual(value['report_sha256'], '6b1fb2a702fcccee34c86cd7e6bf8900de7e24861cd3cee26e554635f306299b')
        self.assertEqual(value['publication_edges'], [680685, 1340148])
        self.assertFalse(value['promotion_allowed'])

    def test_period_stays_conditional_not_clock_adoption(self):
        value = ledger.sample('16')
        self.assertEqual(value['pair_completion_cycles'], 16173357856)
        self.assertEqual(value['amortized_seconds_per_test'], '129.386862848')
        self.assertFalse(value['audited_period_used'])
        self.assertFalse(value['measured_full_sample_PRP'])

    def test_special_one_time_per_context_only(self):
        ordinary = ledger.ledger()
        special = ledger.ledger(special=(True, True))
        self.assertEqual(special['pair_completion_cycles']-ordinary['pair_completion_cycles'], 2*65536)
        self.assertEqual(ledger.ledger((100, 1))['publication_order'], [1, 0])


if __name__ == '__main__':
    unittest.main()
