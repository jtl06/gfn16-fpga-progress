import hashlib
import unittest

from fpga.reference.track_a4_blockcarry_lane_vectors_v1 import corpus
from fpga.reference import track_a4_blockcarry_model as model


class A4LaneCorpusTests(unittest.TestCase):
    def test_completed_frames_match_frozen_split_model(self):
        for aw in (5, 8):
            text, meta = corpus(aw)
            rows = [line.split() for line in text.splitlines()[1:]]
            coeffs, digits, boundary = [], [], None
            active_base = None
            completed = 0
            for row in rows:
                rst, begin, valid = map(int, row[:3])
                if not rst:
                    active_base = None
                    continue
                if begin and int(row[10]) and not int(row[12]):
                    active_base = int(row[5])
                    coeffs, digits, boundary = [], [], None
                if int(row[12]):
                    active_base = None
                    continue
                if valid and active_base is not None:
                    word = int(row[8], 16)
                    coeffs.append(word-(1 << 96) if word >> 95 else word)
                if int(row[14]):
                    self.assertEqual(int(row[16]), len(digits))
                    digits.append(int(row[15]))
                if int(row[17]):
                    high = int(row[19])
                    boundary = (int(row[18]), high-(1 << 32) if high >> 31 else high)
                if int(row[11]):
                    self.assertIsNotNone(active_base)
                    self.assertEqual(len(coeffs), (1 << aw)//16)
                    result, _ = model.arithmetic.proposal.carry_split(coeffs*16, active_base, 16)
                    self.assertEqual(digits, list(result.digits[:len(coeffs)]))
                    self.assertEqual(boundary, (result.c0[1], result.c1[1]))
                    completed += 1
                    active_base = None
            self.assertEqual(completed, meta["completed"])
            self.assertEqual(meta["sha256"], hashlib.sha256(text.encode()).hexdigest())

    def test_edge_timing_and_sticky_quarantine(self):
        for aw in (5, 8):
            text, meta = corpus(aw)
            rows = [line.split() for line in text.splitlines()[1:]]
            expected, boundary_due, done_due = {}, None, None
            failed = False
            for edge, row in enumerate(rows):
                rst, valid = int(row[0]), int(row[2])
                if not rst:
                    expected.clear()
                    boundary_due = done_due = None
                    failed = False
                if int(row[12]):
                    failed = True
                    expected.clear()
                    boundary_due = done_due = None
                if failed:
                    self.assertTrue(int(row[12]))
                    self.assertEqual([int(row[j]) for j in (10, 11, 14, 17)], [0, 0, 0, 0])
                elif rst and valid:
                    expected[edge+25] = int(row[9])
                    if int(row[4]):
                        boundary_due, done_due = edge+28, edge+29
                self.assertEqual(bool(int(row[14])), edge in expected)
                if int(row[14]):
                    self.assertEqual(int(row[16]), expected.pop(edge))
                self.assertEqual(bool(int(row[17])), edge == boundary_due)
                self.assertEqual(bool(int(row[11])), edge == done_due)
            self.assertEqual(meta["errors"], 12)
            self.assertEqual(meta["resets"], 44)

    def test_local_numeric_scope_is_explicit(self):
        for aw in (4, 6, 16):
            with self.assertRaises(ValueError):
                corpus(aw)


if __name__ == "__main__":
    unittest.main()
