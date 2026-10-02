"""Independent integer oracle for streaming RTL, not the Genefer reduction code."""
from __future__ import annotations

import argparse
import itertools
import random
from pathlib import Path

from .rns_reference import GENEFER_SIGNED_PRIMES, RADIX


def write_vectors(path: Path, seed: int = 0x47464E16, count: int = 4096) -> int:
    rng = random.Random(seed)
    total = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii") as stream:
        for field, prime in enumerate(GENEFER_SIGNED_PRIMES):
            p = prime.p
            rinv = pow(RADIX, -1, p)
            edges = [0, 1, 2, p // 2, p - 2, p - 1, RADIX % p]
            triples = list(itertools.product(edges, repeat=3))
            triples.extend(tuple(rng.randrange(p) for _ in range(3)) for _ in range(count))
            for a, b, w in triples:
                mul = a * b * rinv % p
                t = b * w * rinv % p
                stream.write(f"{field} {a} {b} {w} {mul} {(a+t) % p} {(a-t) % p}\n")
                total += 1
    return total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=lambda x: int(x, 0), default=0x47464E16)
    args = parser.parse_args()
    print(f"Wrote {write_vectors(args.output, args.seed)} independent RTL vectors")


if __name__ == "__main__":
    main()
