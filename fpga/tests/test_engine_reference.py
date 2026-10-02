from __future__ import annotations
import random
import unittest
from reference.engine_regression import dif
from reference.rns_reference import GENEFER_SIGNED_PRIMES, naive_ntt


class EngineReferenceTests(unittest.TestCase):
    def test_independent_dif_matches_naive_dft_and_inverse(self) -> None:
        rng=random.Random(654321)
        for prime in GENEFER_SIGNED_PRIMES:
            for n in (2,4,8,16,32):
                for values in ([0]*n,[1]+[0]*(n-1),[prime.p-1]*n,[rng.randrange(prime.p) for _ in range(n)]):
                    with self.subTest(p=prime.name,n=n):
                        transformed=dif(values,prime.p,prime.generator)
                        self.assertEqual(transformed,naive_ntt(values,prime))
                        self.assertEqual(dif(transformed,prime.p,prime.generator,True),values)

