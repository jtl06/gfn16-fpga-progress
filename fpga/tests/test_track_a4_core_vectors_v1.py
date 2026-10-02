import unittest
from fpga.reference.track_a4_core_vectors_v1 import canonical, corpus, integer


class CoreOracleTests(unittest.TestCase):
    def test_corpus(self):
        for aw in (5, 8):
            text, report = corpus(aw)
            self.assertEqual(report["squares"], 14)
            self.assertEqual(report["cold_squares"], 8)
            self.assertEqual(report["profile_loads"], 4)
            self.assertEqual(len(text.splitlines()), report["commands"]+1)

    def test_independent_small_radix(self):
        for base in (3, 7, 300):
            for n in (2, 4):
                modulus = base**n+1
                for value in (-modulus*2-1, -1, 0, 1, modulus-2, modulus-1, modulus, modulus+1):
                    words = canonical(value, base, n)
                    self.assertEqual(integer(words, base) % modulus, value % modulus)
                    self.assertTrue(words == [-1]+[0]*(n-1) or all(0 <= w < base for w in words))


if __name__ == "__main__":
    unittest.main()
