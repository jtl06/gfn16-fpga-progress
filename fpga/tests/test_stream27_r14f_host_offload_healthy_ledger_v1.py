"""Scalar metadata only; no chip model, host C or numerical oracle run."""
import unittest

from fpga.reference.stream27_r14f_host_offload_healthy_ledger_v1 import BASE, calendar, load


class R14FHealthyLedgerTests(unittest.TestCase):
    def test_raw_calendar_not_canonical_publication(self):
        self.assertEqual(calendar(2)['warm_edges'], [21224, 25454])
        self.assertEqual(calendar(2)['raw_done_edges'], [21226, 25456])
        self.assertEqual(calendar(100)['pair_raw_completion_cycles'], 854634)
        self.assertEqual(calendar(1000)['pair_raw_completion_cycles'], 8469534)
        self.assertEqual(calendar(1911814)['pair_raw_completion_cycles'], 16175866788)
        self.assertFalse(calendar(1911814)['canonical_copy_or_publication_cost_used'])

    def test_count32_scope(self):
        for count in (False, True, 0, -1, 1.0, 1 << 32):
            with self.subTest(count=count), self.assertRaises(ValueError):
                calendar(count)
        self.assertEqual(calendar(1)['last_launch_edges'], [204, 4434])

    def test_actual_finite_scope_and_model_only_sample(self):
        value = load(BASE / 'healthy-source-native2-100-ledger-v1.json')
        self.assertEqual(set(value['native_calendars']), {'100'})
        self.assertFalse(value['native2_absolute_edges_logged'])
        self.assertTrue(value['sample']['conditional_source_model_only'])
        self.assertFalse(value['sample']['measured_full_sample'])
        self.assertTrue(value['canonical_FIELD100_R13_copy_publication_ledger_not_used'])
        self.assertTrue(value['old_R14_or_R13_numeric_runtime_clock_not_inherited'])
        self.assertFalse(value['promotion_allowed'])
        self.assertIsNone(value['selected_period_ns'])
        self.assertIsNone(value['projected_pair_seconds'])
        self.assertEqual(value['own_compiled_parameters']['HOST_OFFLOAD'], 1)
        for flag in ('INVERSE_INGRESS_REG', 'TERM_JOIN_TRANSPORT_REG', 'FORWARD_INGRESS_REG'):
            self.assertNotIn(flag, value['own_compiled_parameters'])


if __name__ == '__main__':
    unittest.main()
