import random
import unittest
from reference.ntt27_experiment import select_basis, prove_basis, MAX_COEFFICIENT
from reference.rns_reference import centered_crt, RADIX


class NTT27Tests(unittest.TestCase):
    def test_roots_and_worst_case_dynamic_range(self):
        proof=prove_basis(select_basis())
        self.assertGreater(proof["crt_modulus"],2*MAX_COEFFICIENT)
        self.assertTrue(all(p["p"]<(1<<27) for p in proof["primes"]))
        for value in (-MAX_COEFFICIENT,-1,0,1,MAX_COEFFICIENT):
            self.assertEqual(centered_crt([value%p.p for p in select_basis()],select_basis()),value)
        with self.assertRaises(ValueError):prove_basis(select_basis()[:2])

    def test_wide_digit_conversion_is_not_truncated(self):
        rng=random.Random(27)
        for prime in select_basis():
            for value in [0,prime.p-1,prime.p,prime.p+1,999999999]+[rng.randrange(1_000_000_000) for _ in range(1000)]:
                product=value*prime.r2
                self.assertLess(product,prime.p*RADIX)
                m=(product*prime.q)&(RADIX-1)
                reduced=(product>>32)-(m*prime.p>>32)
                if reduced<0:reduced+=prime.p
                self.assertEqual(reduced,value*RADIX%prime.p)
