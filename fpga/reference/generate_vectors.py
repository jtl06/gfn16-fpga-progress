"""Generate deterministic Montgomery-multiplier vectors."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .rns_reference import GENEFER_SIGNED_PRIMES, RADIX

DEFAULT_SEED = 0x47464E3136


def records(random_count: int = 128, seed: int = DEFAULT_SEED) -> list[dict[str, int | str]]:
    output: list[dict[str, int | str]] = []
    for prime_index, prime in enumerate(GENEFER_SIGNED_PRIMES, start=1):
        edges = [0, 1, 2, 3, prime.p // 2, prime.p - 2, prime.p - 1]
        pairs = [(a, b) for a in edges for b in edges]
        for counter in range(random_count):
            prefix = seed.to_bytes(16, "little") + prime_index.to_bytes(4, "little") + counter.to_bytes(8, "little")
            lhs_raw = int.from_bytes(hashlib.shake_256(prefix + b"lhs").digest(8), "little")
            rhs_raw = int.from_bytes(hashlib.shake_256(prefix + b"rhs").digest(8), "little")
            pairs.append((lhs_raw % prime.p, rhs_raw % prime.p))
        for standard_lhs, standard_rhs in pairs:
            lhs = prime.to_mont(standard_lhs)
            rhs = prime.to_mont(standard_rhs)
            # Deliberately independent of the mulmod implementation under test.
            expected = lhs * rhs * pow(RADIX, -1, prime.p) % prime.p
            output.append(
                {
                    "schema": "montgomery-record/v1",
                    "prime_index": prime_index,
                    "prime": prime.name,
                    "p": prime.p,
                    "q": prime.q,
                    "lhs": lhs,
                    "rhs": rhs,
                    "expected": expected,
                    "standard_lhs": standard_lhs,
                    "standard_rhs": standard_rhs,
                    "standard_expected": (standard_lhs * standard_rhs) % prime.p,
                }
            )
    return output


def write_vectors(jsonl_path: Path, hex_path: Path, random_count: int, seed: int) -> None:
    vector_records = records(random_count=random_count, seed=seed)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    hex_path.parent.mkdir(parents=True, exist_ok=True)

    json_lines = [json.dumps(record, sort_keys=True, separators=(",", ":")) for record in vector_records]
    json_payload = "\n".join(json_lines) + "\n"
    jsonl_path.write_text(json_payload, encoding="utf-8")

    with hex_path.open("w", encoding="ascii") as stream:
        stream.write(f"// generator=shake256-counter-v1 seed=0x{seed:x} count={len(vector_records)} sha256={hashlib.sha256(json_payload.encode()).hexdigest()}\n")
        stream.write("// prime_index lhs_mont rhs_mont expected_mont\n")
        for record in vector_records:
            stream.write(
                f"{record['prime_index']} {record['lhs']:08x} {record['rhs']:08x} {record['expected']:08x}\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--hex", dest="hex_path", type=Path, required=True)
    parser.add_argument("--random-count", type=int, default=128)
    parser.add_argument("--seed", type=lambda value: int(value, 0), default=DEFAULT_SEED)
    args = parser.parse_args()
    write_vectors(args.jsonl, args.hex_path, args.random_count, args.seed)


if __name__ == "__main__":
    main()
