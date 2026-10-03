import unittest

from fpga.reference import stream27_c2_storage_combo_record_ledger_v1 as ledger


def synthetic_footer():
    # Synthetic scalar fixture, NEVER presented as completed native evidence.
    return dict(aw=16, p=16, contexts=2, bases=[604832956, 999999937], squares=8,
        reads=393216, signed96=True, context_alone_bit_identical=True, independent_reference=True,
        interval=8459, pair_launch_cycles=8459, launches=[[204, 8663], [4433, 12892]],
        warm_edges=[21221, 25450], done_edges=[680685, 1340148], joint_cycles=1405684,
        setup_edges=[99, 199], single_first=[104, 104], single_cycles=[746121, 746121],
        peer_live_reads=65536)


class ComboLedgerTests(unittest.TestCase):
    def test_own_source_no_parent_native_PASS(self):
        bundle = ledger.source()
        self.assertEqual(len(bundle['files']), 53)
        result = ledger.ledger()
        self.assertEqual(result['publication_edges'], [680685, 1340148])
        self.assertEqual(result['evidence_scope'], 'SOURCE_CALENDAR_ONLY')
        self.assertFalse(result['parent_native_PASS_inherited'])
        self.assertFalse(result['promotion_allowed'])

    def test_actual_own_full_gate_and_calendar_source_join(self):
        result = ledger.check_native()
        self.assertEqual(result['evidence_scope'], 'OWN_ADMITTED_NATIVE_CALENDAR_AND_FULL53_SOURCE_JOIN')
        self.assertEqual(result['gate_id'], 's4-p16-c2-combo-full-normal-q1-v1')
        self.assertEqual(result['publication_edges'], [680685, 1340148])
        self.assertFalse(result['promotion_allowed'])

    def test_conditional_pair_not_audited_or_measured_full_PRP(self):
        value = ledger.sample('14')
        self.assertEqual(value['pair_completion_cycles'], 16173357856)
        self.assertEqual(value['amortized_seconds_per_test'], '113.213504992')
        self.assertFalse(value['audited_period_used'])
        self.assertFalse(value['measured_full_sample_PRP'])

    def test_scalar_footer_scope_and_all_measured_edges(self):
        result = ledger.footer_events(synthetic_footer())
        self.assertEqual(result['canonical_allocation_edges'], [21223, 680686])
        self.assertEqual(result['evidence_scope'], 'SCALAR_FOOTER_ONLY_NOT_DEPENDENCY_ADMISSION')
        for key, value in [('interval', 8460), ('done_edges', [680687, 1340150]),
                           ('bases', [604832956, 604832956]), ('independent_reference', False),
                           ('reads', 131072), ('launches', [[204, 8664], [4434, 12894]])]:
            wrong = synthetic_footer()
            wrong[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                ledger.footer_events(wrong)

    def test_special_and_unequal_calendars_do_not_assume_twofold_latency(self):
        ordinary = ledger.ledger()
        special = ledger.ledger(special=(True, True))
        self.assertEqual(special['pair_completion_cycles'] - ordinary['pair_completion_cycles'], 2*65536)
        unequal = ledger.ledger((100, 1))
        self.assertEqual(unequal['publication_order'], [1, 0])
        self.assertEqual(unequal['per_context_interval'], 8459)


if __name__ == '__main__':
    unittest.main()
