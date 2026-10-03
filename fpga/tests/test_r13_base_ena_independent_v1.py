"""Reviewer-only scalar/source controls; do not execute an author's proof/model."""
import importlib.util
from pathlib import Path
import unittest

P = Path(__file__).resolve().parents[1] / 'tools/replay_r13_base_ena_independent_v1.py'
spec = importlib.util.spec_from_file_location('review_base_ena',P)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class ReviewerControls(unittest.TestCase):
    def test_independent_binary_guard_and_dead_payload(self):
        result = review.independent_guard_proof()
        self.assertEqual(result['binary_cases'],24576)
        self.assertEqual(result['dead_payload_successor_cases'],5120)
        self.assertEqual(result['negative_controls_detected'],3)
        self.assertEqual(result['host_profile_selection_cases'],288)

    def test_priority_is_not_cached_payload_authority(self):
        self.assertEqual(review.reject('IDLE',0,(0,1,0,1,0,0,1,0,1,0)),1)
        self.assertEqual(review.reject('IDLE',0,(0,1,0,0,0,0,0,1,1,0)),5)
        self.assertEqual(review.reject('IDLE',0,(0,1,0,0,1,0,0,1,1,0)),3)
        self.assertEqual(review.reject('IDLE',0,(0,1,0,0,1,1,0,1,1,0)),4)

    def test_literal_guard_tamper_rejected(self):
        text = ('module ' + review.NEW + ' #\n' + review.CAPTURE +
                '                        address<=0;pass_index<=0;carry<=0;all_zero<=1;all_max<=1;state<=READ_WORD;')
        with self.assertRaises(AssertionError):
            review.reverse_split(text.replace('state==IDLE && !error && begin_canonical','begin_canonical'))

    def test_actual_integrated_source_profile(self):
        result = review.integration()
        self.assertEqual(result['parent_sha256'],review.PARENT)
        self.assertEqual(result['current_sha256'],review.FOLD)


if __name__ == '__main__':
    unittest.main()
