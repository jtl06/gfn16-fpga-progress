"""Pinned existing-evidence math tests; no new native experiment."""
import unittest
from unittest.mock import patch
from fpga.synthesis import rootfused85_projection as p


class ProjectionTests(unittest.TestCase):
    def test_existing_matched_evidence_and_exact_integer_formula(self):
        x=p.estimate()
        self.assertEqual(x['exponent_bits'],1911814)
        self.assertEqual(x['cached_chain_total_cycles'],63022957253)
        self.assertEqual(x['cached_chain_total_cycles'],41708+(1911814-1)*32965)
        self.assertEqual(x['clock_hz'],85000000)
        self.assertAlmostEqual(x['projected_compute_seconds'],741.4465559176471)
        self.assertEqual(len(x['source_sha256']),16)

    def test_independent_clock_review_pin_required(self):
        bad=dict(p.PINS);bad[p.AUDIT+'independent-review-v1.json']='0'*64
        with patch.object(p,'PINS',bad),self.assertRaisesRegex(ValueError,'input drift'):p.estimate()

    def test_native_cycle_gate_pin_required(self):
        bad=dict(p.PINS);bad[p.NATIVE]='0'*64
        with patch.object(p,'PINS',bad),self.assertRaisesRegex(ValueError,'input drift'):p.estimate()

    def test_no_candidate_clock_or_full_prp_claim(self):
        x=p.estimate()
        self.assertNotIn('crtmont',x['target'])
        self.assertEqual((x['cold_sample_count'],x['warm_sample_count']),(1,4))
        self.assertIn('not_full_prp',x['status'])
        self.assertTrue(any('not a clock qualification' in line for line in x['limitations']))


if __name__=='__main__':unittest.main()
