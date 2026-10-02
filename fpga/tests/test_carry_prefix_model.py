import itertools
import random
import unittest
from reference.carry_prefix_model import normalize, compose, DOMAIN


class CarryPrefixModelTests(unittest.TestCase):
    def check(self, values, base):
        digits, _ = normalize(values,base)
        modulus=base**len(values)+1
        expected=sum(a*base**i for i,a in enumerate(values))%modulus
        got=sum(a*base**i for i,a in enumerate(digits))%modulus
        self.assertEqual(got,expected)
        if expected==modulus-1:
            self.assertEqual(digits,[-1]+[0]*(len(values)-1))
        else:
            self.assertTrue(all(0<=d<base for d in digits))

    def test_small_exhaustive(self):
        for values in itertools.product(range(-20,21),repeat=2):
            self.check(list(values),9)

    def test_signed_boundaries_and_random(self):
        rng=random.Random(20260929)
        for n in (2,4,16,128):
            for base in (2*n+5,604832956,1_000_000_000):
                bound=2*n*(base-1)**2
                for values in ([0]*n,[-1]+[0]*(n-1),[bound]*n,[-bound]*n,
                               [bound if i%2 else -bound for i in range(n)]):
                    self.check(values,base)
                for _ in range(20):
                    self.check([rng.randint(-bound,bound) for _ in range(n)],base)

    def test_associative_transfer_composition(self):
        rng=random.Random(3)
        for _ in range(100):
            a,b,c=[tuple(rng.choice(DOMAIN) for _ in DOMAIN) for _ in range(3)]
            self.assertEqual(compose(compose(a,b),c),compose(a,compose(b,c)))

    def test_full_size_exact_max_digit_square(self):
        # (b^N-1)^2 == 4 modulo b^N+1; negacyclic coefficients span
        # almost the entire signed square bound and both wrap positions.
        n=65536
        for base in (604832956,1_000_000_000):
            coefficients=[(2*i+2-n)*(base-1)**2 for i in range(n)]
            for double in (1,2):
                digits,_=normalize([double*a for a in coefficients],base)
                self.assertEqual(digits,[4*double]+[0]*(n-1))
            digits,_=normalize([-1]+[0]*(n-1),base)
            self.assertEqual(digits,[-1]+[0]*(n-1))

    def test_rejects_unsupported(self):
        with self.assertRaises(ValueError): normalize([0,0],8)
        with self.assertRaises(ValueError): normalize([0,0,0],100)
        with self.assertRaises(ValueError): normalize([257,0],9)
