"""Bounded scalar checks only; no transform, HDL, or vendor execution."""
import itertools
import random
import unittest

from fpga.reference.lazy28_range_model_v1 import (
    FIELDS, LOW27, R, butterfly, mont28x27, oracle,
)


class Lazy28RangeTests(unittest.TestCase):
    def test_integer_bounds_all_fields(self):
        for p in FIELDS:
            self.assertLess(p, 1 << 27)
            self.assertGreater(2*p-1, LOW27)
            self.assertLess(2*p, 1 << 28)
            self.assertLess(4*p, 1 << 29)
            self.assertLess((2*p-1)*(p-1), p*R)
            self.assertLess((2*p-1)*(p-1), 1 << 55)
            self.assertLess((R-1)*p, 1 << 59)
            self.assertEqual(p*(2-p) % R, 1)

    def test_edges_and_deterministic_random(self):
        rng = random.Random(0x1A2B28)
        for p in FIELDS:
            edges = (0, 1, p-1, p, p+1, LOW27, LOW27+1, 2*p-1)
            roots = (0, 1, p-1, R % p)
            cases = list(itertools.product(edges, edges, roots))
            cases += [(rng.randrange(2*p), rng.randrange(2*p),
                       rng.randrange(p)) for _ in range(2048)]
            for u, v, w in cases:
                self.assertEqual(mont28x27(v, w, p), v*w*pow(R, -1, p) % p)
                for form in ("CT", "GS"):
                    actual = butterfly(u, v, w, p, form)
                    self.assertTrue(all(0 <= x < 2*p for x in actual))
                    self.assertEqual(tuple(x % p for x in actual),
                                     oracle(u, v, w, p, form))

    def test_frozen_27_bit_slice_is_a_real_counterexample(self):
        for p in FIELDS:
            lhs, rhs = 1 << 27, R % p
            self.assertLess(lhs, 2*p)
            correct = mont28x27(lhs, rhs, p)
            truncated = mont28x27(lhs & LOW27, rhs, p)
            self.assertEqual(correct, lhs % p)
            self.assertNotEqual(correct, truncated)

    def test_missing_ct_input_correction_breaks_range(self):
        for p in FIELDS:
            u, v, w = 2*p-1, p-1, R % p
            wrong = u + mont28x27(v, w, p)
            self.assertGreaterEqual(wrong, 2*p)
            self.assertLess(butterfly(u, v, w, p, "CT")[0], 2*p)

    def test_missing_gs_difference_fold_breaks_multiplier_contract(self):
        for p in FIELDS:
            u, v = 2*p-1, 0
            with self.assertRaises(ValueError):
                mont28x27(u+2*p-v, 1, p)
            self.assertTrue(all(x < 2*p for x in butterfly(u, v, 1, p, "GS")))

    def test_invalid_ranges_rejected(self):
        for p in FIELDS:
            for lhs, rhs in ((-1, 0), (2*p, 0), (0, p), (0, -1)):
                with self.assertRaises(ValueError):
                    mont28x27(lhs, rhs, p)
        with self.assertRaises(ValueError):
            butterfly(0, 0, 0, FIELDS[0], "unknown")


if __name__ == "__main__":
    unittest.main()
