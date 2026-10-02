"""Optional full-N=65,536 arithmetic check (slower than unit tests)."""

from __future__ import annotations

import hashlib
import struct
import time

from .rns_reference import GENEFER_SIGNED_PRIMES, negacyclic_convolution, ntt


def main() -> None:
    size = 1 << 16
    for prime in GENEFER_SIGNED_PRIMES:
        values = [(index * index + 17 * index + 5) % prime.p for index in range(size)]
        started = time.monotonic()
        restored = ntt(ntt(values, prime), prime, inverse=True)
        if restored != values:
            raise SystemExit(f"{prime.name}: full-length NTT round trip failed")
        digest = hashlib.sha256()
        for value in restored:
            digest.update(struct.pack("<I", value))
        print(f"{prime.name}: PASS sha256={digest.hexdigest()} elapsed={time.monotonic() - started:.3f}s")

    # A full-size identity with a known answer catches wrap-sign and scaling
    # errors that a forward/inverse round trip can share.
    prime = GENEFER_SIGNED_PRIMES[0]
    left = [0] * size
    right = [0] * size
    left[size - 1] = 7
    right[1] = 11
    started = time.monotonic()
    product = negacyclic_convolution(left, right, prime)
    expected = [0] * size
    expected[0] = prime.p - 77
    if product != expected:
        raise SystemExit("P1: full-length negacyclic wrap identity failed")
    print(f"P1: PASS full-length negacyclic wrap elapsed={time.monotonic() - started:.3f}s")


if __name__ == "__main__":
    main()
