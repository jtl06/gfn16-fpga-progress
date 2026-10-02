from __future__ import annotations

import random
import unittest
from math import prod

from reference.rns_reference import (
    GENEFER_SIGNED_PRIMES,
    GENEFER_UNSIGNED_PRIMES,
    RADIX,
    carry_reduce,
    centered_crt,
    cyclic_convolution,
    genefer_gpu_allocated_buffer_bytes,
    genefer_gpu_reported_memory_bytes,
    negacyclic_convolution,
    naive_ntt,
    ntt,
    profile_for,
    rns_square_dup,
    schoolbook_cyclic_convolution,
    schoolbook_negacyclic_convolution,
)
from reference.gfn_reference import (
    canonical_unbalanced_digits,
    decode_digits,
    exponent_bits,
    modulus,
    prp_reference,
    square_dup_oracle,
    validate_genefer_candidate,
)


class ReferenceTests(unittest.TestCase):
    def test_constants_and_montgomery_equivalence(self) -> None:
        rng = random.Random(0xA10)
        for prime in GENEFER_SIGNED_PRIMES + GENEFER_UNSIGNED_PRIMES:
            prime.validate()
            inverse_radix = pow(RADIX, -1, prime.p)
            for _ in range(2_000):
                lhs = rng.randrange(prime.p)
                rhs = rng.randrange(prime.p)
                self.assertEqual(prime.mont_mul(lhs, rhs), lhs * rhs * inverse_radix % prime.p)

    def test_montgomery_round_trip_and_product(self) -> None:
        rng = random.Random(16)
        for prime in GENEFER_SIGNED_PRIMES:
            for _ in range(500):
                lhs = rng.randrange(prime.p)
                rhs = rng.randrange(prime.p)
                lhs_m = prime.to_mont(lhs)
                rhs_m = prime.to_mont(rhs)
                self.assertEqual(prime.from_mont(lhs_m), lhs)
                self.assertEqual(
                    prime.from_mont(prime.mont_mul(lhs_m, rhs_m)), lhs * rhs % prime.p
                )

    def test_ntt_round_trip(self) -> None:
        rng = random.Random(65_536)
        for prime in GENEFER_SIGNED_PRIMES:
            for size in (1, 2, 4, 8, 16, 64):
                values = [rng.randrange(prime.p) for _ in range(size)]
                self.assertEqual(ntt(ntt(values, prime), prime, inverse=True), values)

    def test_ntt_matches_independent_naive_dft(self) -> None:
        values = [19, 7, 42, 0, 91, 5, 3, 77]
        for prime in GENEFER_SIGNED_PRIMES:
            self.assertEqual(ntt(values, prime), naive_ntt(values, prime))
            transformed = naive_ntt(values, prime)
            self.assertEqual(ntt(transformed, prime, inverse=True), values)

    def test_ntt_convolution(self) -> None:
        rng = random.Random(0xC0FFEE)
        for prime in GENEFER_SIGNED_PRIMES:
            lhs = [rng.randrange(10_000) for _ in range(16)]
            rhs = [rng.randrange(10_000) for _ in range(16)]
            self.assertEqual(
                cyclic_convolution(lhs, rhs, prime),
                schoolbook_cyclic_convolution(lhs, rhs, prime.p),
            )

    def test_negacyclic_convolution(self) -> None:
        rng = random.Random(0x1768)
        for prime in GENEFER_SIGNED_PRIMES:
            lhs = [rng.randrange(10_000) for _ in range(16)]
            rhs = [rng.randrange(10_000) for _ in range(16)]
            self.assertEqual(
                negacyclic_convolution(lhs, rhs, prime),
                schoolbook_negacyclic_convolution(lhs, rhs, prime.p),
            )

    def test_gfn16_roots(self) -> None:
        transform_size = 1 << 16
        expected = (373_019_801, 1_502_475_247, 1_286_330_022)
        for prime, root in zip(GENEFER_SIGNED_PRIMES, expected, strict=True):
            self.assertEqual(prime.primitive_root(2 * transform_size), root)
            self.assertEqual(pow(root, transform_size, prime.p), prime.p - 1)

    def test_gfn16_profile_boundaries(self) -> None:
        self.assertEqual(profile_for(5_862_084, 16).name, "s2")
        self.assertEqual(profile_for(5_862_086, 16).name, "u2")
        self.assertEqual(profile_for(11_421_892, 16).name, "u2")
        self.assertEqual(profile_for(11_421_894, 16).name, "s3")
        self.assertEqual(profile_for(604_832_956, 16).name, "s3")
        self.assertEqual(profile_for(1_000_000_002, 16).name, "u3")

    def test_production_candidate_validation(self) -> None:
        validate_genefer_candidate(604_832_956, 16)
        validate_genefer_candidate(2_000_000_000, 16)
        for base, n_log2 in ((1023, 16), (1025, 16), (1024, 16), (604_832_956, 11), (604_832_956, 24)):
            with self.assertRaises(ValueError):
                validate_genefer_candidate(base, n_log2)
        with self.assertRaises(ValueError):
            validate_genefer_candidate(2_000_000_002, 16)

    def test_centered_crt(self) -> None:
        modulus = prod(prime.p for prime in GENEFER_SIGNED_PRIMES)
        samples = [0, 1, -1, modulus // 2, -(modulus // 2), 123456789012345678]
        for value in samples:
            residues = [value % prime.p for prime in GENEFER_SIGNED_PRIMES]
            self.assertEqual(centered_crt(residues, GENEFER_SIGNED_PRIMES), value)

    def test_upstream_memory_formulas(self) -> None:
        self.assertEqual(
            genefer_gpu_reported_memory_bytes(num_regs=4, use_wi=False),
            (4_456_448, 1_179_648),
        )
        self.assertEqual(
            genefer_gpu_reported_memory_bytes(num_regs=4, use_wi=True),
            (4_849_664, 1_572_864),
        )
        self.assertEqual(genefer_gpu_allocated_buffer_bytes(num_regs=4), 4_849_664)

    def test_toy_genefer_prp_schedule(self) -> None:
        result = prp_reference(10, 3)
        self.assertEqual(modulus(10, 3), 100_000_001)
        self.assertEqual(result.residue, 65_536)
        self.assertEqual(result.steps, len(tuple(exponent_bits(10, 3))))
        self.assertFalse(result.probable_prime)
        self.assertTrue(prp_reference(2, 3).probable_prime)

    def test_toy_square_dup_digit_oracle(self) -> None:
        base = 10
        digits = [7, 9, 3, 1, 0, 8, 2, 4]
        for bit in (0, 1):
            output = square_dup_oracle(digits, base, bit)
            ring_modulus = base ** len(digits) + 1
            expected = decode_digits(digits, base) ** 2 * (2 if bit else 1) % ring_modulus
            self.assertEqual(decode_digits(output, base) % ring_modulus, expected)
        self.assertEqual(
            canonical_unbalanced_digits(-1, 10, 8), [-1, 0, 0, 0, 0, 0, 0, 0]
        )

    def test_composed_rns_square_dup_matches_bigint(self) -> None:
        rng = random.Random(0x5A3)
        for size in (2, 4, 8, 16):
            for base in (10, 257, 1024):
                for _ in range(5):
                    digits = [rng.randrange(base) for _ in range(size)]
                    for bit in (0, 1):
                        expected = square_dup_oracle(digits, base, bit)
                        self.assertEqual(
                            rns_square_dup(digits, base, bit, GENEFER_SIGNED_PRIMES),
                            expected,
                        )

    def test_rns_capacity_guard(self) -> None:
        with self.assertRaisesRegex(ValueError, "distinct primes"):
            rns_square_dup([1, 2], 10, 1, ())
        huge = 2_000_000_000 - 1
        with self.assertRaisesRegex(ValueError, "too small"):
            rns_square_dup([huge, huge], 2_000_000_000, 1, GENEFER_SIGNED_PRIMES[:2])

    def test_carry_wrap_and_large_coefficients(self) -> None:
        rng = random.Random(0xCA771)
        for size in (2, 8, 32):
            for base in (2, 10, 1000):
                ring_modulus = base**size + 1
                for _ in range(20):
                    coefficients = [rng.randrange(-base * base * size, base * base * size) for _ in range(size)]
                    reduced = carry_reduce(coefficients, base)
                    self.assertEqual(
                        decode_digits(reduced, base) % ring_modulus,
                        decode_digits(coefficients, base) % ring_modulus,
                    )



if __name__ == "__main__":
    unittest.main()
