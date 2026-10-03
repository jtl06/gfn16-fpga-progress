"""Read-only metadata checks; no native or numerical oracle execution."""
import unittest

from fpga.reference.stream27_protected_relay13_targeted_overlay import (
    AUTHOR, AUTHOR_SHA, BASE, INDEX, INDEX_SHA, LEDGER_SHA, load, sha)


class TargetedOverlayTest(unittest.TestCase):
    def test_frozen_inputs_unchanged(self):
        self.assertEqual(sha(INDEX), INDEX_SHA)
        self.assertEqual(sha(AUTHOR), AUTHOR_SHA)

    def test_overlay_preserves_review_and_clock_boundary(self):
        result = load(BASE / 'numerical-index-targeted-author-overlay-v1.json')
        self.assertEqual(result['immutable_generic_index']['sha256'], INDEX_SHA)
        self.assertEqual(result['targeted_author_handoff']['sha256'], AUTHOR_SHA)
        self.assertEqual(result['own_healthy_source_native_ledger']['sha256'], LEDGER_SHA)
        self.assertTrue(result['prior_index_pending_flags_preserved'])
        self.assertTrue(result['targeted_source_review_pending'])
        self.assertFalse(result['independent_review'])
        self.assertFalse(result['promotion_allowed'])
        self.assertIsNone(result['selected_period_ns'])
        self.assertIsNone(result['projected_pair_seconds'])

    def test_exact_targeted_scope_and_negative(self):
        result = load(BASE / 'numerical-index-targeted-author-overlay-v1.json')
        scope = result['targeted_scope']
        self.assertEqual((scope['origin_cases'], scope['reset_cases'],
                          scope['recovery_signed96_words'], scope['sticky_quiet_edges']),
                         (32, 16, 49152, 768))
        self.assertFalse(scope['reset_payload_zero_claim'])
        normal, faults = result['targeted_author_jobs']
        self.assertEqual(normal['compiled_sv_count'], 65)
        self.assertEqual(normal['compiled_sources'], faults['compiled_sources'])
        self.assertEqual(normal['compiled_parameters'], faults['compiled_parameters'])
        self.assertEqual(faults['steps'][1]['actual_returncode'], 1)
        self.assertEqual(faults['steps'][1]['expected_returncode'], 1)


if __name__ == '__main__':
    unittest.main()
