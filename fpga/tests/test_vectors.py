from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from reference.generate_vectors import DEFAULT_SEED, records
from reference.rns_reference import GENEFER_SIGNED_PRIMES, RADIX


class VectorTests(unittest.TestCase):
    def test_committed_vectors_are_complete_and_reproducible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        jsonl_path = root / "vectors" / "montgomery_mul32.jsonl"
        hex_path = root / "vectors" / "montgomery_mul32.hex"
        payload = jsonl_path.read_text(encoding="utf-8")
        parsed = [json.loads(line) for line in payload.splitlines()]
        self.assertEqual(parsed, records(seed=DEFAULT_SEED))
        self.assertEqual(len(parsed), 531)
        for index in (1, 2, 3):
            self.assertEqual(sum(record["prime_index"] == index for record in parsed), 177)

        digest = hashlib.sha256(payload.encode()).hexdigest()
        header = hex_path.read_text(encoding="ascii").splitlines()[0]
        self.assertIn("generator=shake256-counter-v1", header)
        self.assertIn(f"sha256={digest}", header)

    def test_expected_values_use_the_mathematical_definition(self) -> None:
        prime_by_name = {prime.name: prime for prime in GENEFER_SIGNED_PRIMES}
        for record in records(random_count=8):
            prime = prime_by_name[str(record["prime"])]
            expected = int(record["lhs"]) * int(record["rhs"]) * pow(RADIX, -1, prime.p) % prime.p
            self.assertEqual(record["expected"], expected)


if __name__ == "__main__":
    unittest.main()

