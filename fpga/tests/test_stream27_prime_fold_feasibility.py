import unittest

from fpga.reference.stream27_prime_fold_feasibility import PRIMES, R, analyze, fold, folded_montgomery, range_schedule


class PrimeFoldTests(unittest.TestCase):
    def test_current_cell_and_fold_against_independent_r32_oracle(self):
        result = analyze()
        self.assertGreater(result["checks"], 60000)
        self.assertEqual([f["scaled_montgomery_sufficient_fold_count"] for f in result["fields"]], [60, 10, 6])

    def test_fold_preserves_integer_residue_including_negative_values(self):
        for p, _, _ in PRIMES:
            for value in (0, 1, -1, p, -p, (1 << 81) - 1, -(1 << 81)):
                self.assertEqual(fold(value, p) % p, value % p)

    def test_ordinary_reduction_is_not_montgomery(self):
        for p, _, _ in PRIMES:
            self.assertNotEqual(1, pow(R, -1, p))
            self.assertEqual(folded_montgomery(1, 1, p), pow(R, -1, p))

    def test_three_fold_one_correction_has_legal_counterexamples(self):
        for p, expected in ((104857601, -3913789195520001),
                            (69206017, -292326215807)):
            value = (2 * p - 1) * (p - 1)
            for _ in range(3):
                value = fold(value, p)
            self.assertEqual(value, expected)
            self.assertLess(value, -p)  # Adding P once is still negative.

    def test_strict_input_domains_and_finite_correction_bound(self):
        for p, _, _ in PRIMES:
            for a, b in ((-1, 0), (2 * p, 0), (0, p)):
                with self.assertRaises(ValueError):
                    folded_montgomery(a, b, p)
            lo, hi = range_schedule(p, True)[-1]
            self.assertGreaterEqual(lo, -p)
            self.assertLess(hi, 2 * p)


if __name__ == "__main__":
    unittest.main()
