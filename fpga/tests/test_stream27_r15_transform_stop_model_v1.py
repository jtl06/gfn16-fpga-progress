import unittest
from dataclasses import replace

from fpga.reference import stream27_r15_transform_stop_model_v1 as model


class StopLocalityModel(unittest.TestCase):
    def test_exact_six_source_contracts_and_no_emission(self):
        result = model.audit_source()
        self.assertEqual(len(result['roots']), 6)
        self.assertFalse(result['RTL_generated'])
        self.assertFalse(result['current_source_mutation'])

    def test_default_off_and_exact_type(self):
        self.assertEqual(model.flag(), 0)
        for bad in (True, False, 2, -1, 0.0):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                model.flag(bad)
        sample = model.Signals(True, False, False, False, True, True, True, True)
        self.assertEqual(model.observe(sample), model.observe(sample, 0))

    def test_exhaustive_relational_boolean_envelope(self):
        result = model.envelope_proof()
        self.assertEqual(result['pre_aggregate_samples'], 128)
        self.assertEqual(result['post_aggregate_pairs'], 8192)
        self.assertTrue(result['sticky_first_origin_equivalent'])
        self.assertFalse(result['complete_RTL_or_native_proof'])

    def test_origin_then_post_NBA_mask_same_and_sticky(self):
        first = model.Signals(False, False, False, True, True, True, True, True, payload=17)
        old, new = model.observe(first, 0), model.observe(first, 1)
        self.assertEqual(old, new)
        self.assertTrue(old['pending'])
        self.assertTrue(old['slot'])  # Do not silently tighten the first-origin edge.
        self.assertTrue(old['next_aggregate'])
        after = replace(first, aggregate=True, comb_fault=False, payload=99)
        self.assertEqual(model.observe(after, 0), model.observe(after, 1))
        self.assertIsNone(model.observe(after, 1)['effective_payload'])
        self.assertTrue(model.observe(after, 1)['pending'])
        self.assertTrue(model.observe(after, 1)['error'])

    def test_external_quarantine_retains_origin_deferral_and_public_mask(self):
        s = model.Signals(False, True, False, True, True, True, True, True)
        self.assertEqual(model.observe(s, 0), model.observe(s, 1))
        self.assertFalse(model.observe(s, 1)['next_aggregate'])
        self.assertFalse(model.observe(s, 1)['slot'])

    def test_raw_ports_not_claimed_equal_after_aggregate(self):
        old = model.Signals(True, False, False, False, True, False, True, True, payload=1)
        new = replace(old, private_slot=False, private_start=True, generation_matches=False, payload=2)
        self.assertNotEqual(old.payload, new.payload)
        self.assertEqual(model.observe(old, 0), model.observe(new, 1))

    def test_arbitrary_post_aggregate_payload_is_real_scope_counterexample(self):
        for p in (104857601, 69206017, 67239937):
            witness = model.stage0_range_witness(p)
            self.assertFalse(witness['old_native_range_fatal'])
            self.assertTrue(witness['proposed_native_range_fatal'])
            self.assertFalse(witness['unrestricted_native_trace_equivalence'])
            self.assertFalse(witness['actual_whole_caller_reachability_proven'])
            self.assertFalse(witness['hardware_publication_corruption_proven'])

    def test_revised_raw_admission_retains_old_for_arbitrary_payload(self):
        result = model.revised_boundary_proof()
        self.assertEqual(result['samples'], 864)
        self.assertTrue(result['old_and_revised_raw_range_assertion_decisions_equal'])
        self.assertFalse(model.revised_boundary_accept(aggregate=True, quarantine=False,
                                                       local_error=False, row_slot=True))

    def test_bounded_origin_lemma_does_not_trust_unqualified_postfault_data(self):
        result = model.bounded_origin_interval_proof()
        self.assertTrue(result['pre_A1_accepted_origin_or_reset_qualified_zero_required'])
        self.assertFalse(result['blanket_trusted_post_fault_input_assumption'])
        self.assertFalse(result['arbitrary_RAM_corruption_bound_or_numeric_equality_proven'])
        self.assertTrue(result['wrong_pairing_can_change_arithmetic'])

    def test_reset_masks_unrelated_private_delay_history_with_gaps(self):
        rows = model.reset_history_proof()
        self.assertEqual(len(rows), 9)
        self.assertTrue(all(x['masked_head_equal'] and not x['payload_reset'] for x in rows))

    def test_missing_reset_fill_mask_sensitivity(self):
        a, b = model.ResetMaskedRing(4, 'old'), model.ResetMaskedRing(4, 'new')
        self.assertIsNone(a.head)
        self.assertIsNone(b.head)
        self.assertNotEqual(a.prefetched, b.prefetched)
        a.filled = b.filled = 4
        self.assertNotEqual(a.head, b.head)  # A raw-head visibility mutant breaks the lemma.

    def test_whole_assessment_stays_model_only_and_blocks_RTL(self):
        result = model.assess()
        self.assertTrue(result['model_only'])
        self.assertFalse(result['RTL_emission_allowed'])
        self.assertFalse(result['native_submission_allowed'])
        self.assertFalse(result['current_reviews_inherited'])


if __name__ == '__main__':
    unittest.main()
