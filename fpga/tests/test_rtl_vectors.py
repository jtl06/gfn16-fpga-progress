from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from pathlib import Path

from reference.rns_reference import GENEFER_SIGNED_PRIMES, RADIX
from reference.rtl_vectors import write_vectors


class RTLVectorTests(unittest.TestCase):
    def test_counts_ranges_and_montgomery_identities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vectors.txt"
            self.assertEqual(write_vectors(path), 13317)
            counts: Counter[int] = Counter()
            for line in path.read_text().splitlines():
                field, a, b, w, mul, y0, y1 = map(int, line.split())
                p = GENEFER_SIGNED_PRIMES[field].p
                self.assertTrue(all(0 <= v < p for v in (a, b, w, mul, y0, y1)))
                # Check identities without repeating the generator's inverse calculation.
                self.assertEqual(mul * RADIX % p, a * b % p)
                self.assertEqual((y0 - a) * RADIX % p, b * w % p)
                self.assertEqual((a - y1) * RADIX % p, b * w % p)
                counts[field] += 1
            self.assertEqual(counts, {0: 4439, 1: 4439, 2: 4439})

    def test_seed_reproducibility(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            a, b, c = (Path(directory) / name for name in ("a", "b", "c"))
            write_vectors(a, seed=1)
            write_vectors(b, seed=1)
            write_vectors(c, seed=2)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertNotEqual(a.read_bytes(), c.read_bytes())
