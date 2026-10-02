"""Slow independent generalized-Fermat oracle for toy-sized tests.

The full GFN16 computation needs millions of large modular squarings and is
not intended to run through Python big integers.  These routines define the
mathematical boundary used to validate reduced-size RTL and carry logic.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


def modulus(base: int, n_log2: int) -> int:
    if base < 2 or n_log2 < 0:
        raise ValueError("base must be at least two and n_log2 nonnegative")
    return pow(base, 1 << n_log2) + 1


def exponent_bits(base: int, n_log2: int) -> Iterator[int]:
    """Yield bits of M-1 = base^(2^n), most-significant first."""

    exponent = pow(base, 1 << n_log2)
    for shift in range(exponent.bit_length() - 1, -1, -1):
        yield (exponent >> shift) & 1


@dataclass(frozen=True)
class PRPResult:
    base: int
    n_log2: int
    residue: int
    steps: int

    @property
    def probable_prime(self) -> bool:
        return self.residue == 1


def prp_reference(base: int, n_log2: int) -> PRPResult:
    """Compute Genefer's base-2 Fermat residue using the squareDup schedule."""

    candidate = modulus(base, n_log2)
    residue = 1
    steps = 0
    for bit in exponent_bits(base, n_log2):
        residue = residue * residue % candidate
        if bit:
            residue = residue * 2 % candidate
        steps += 1
    direct = pow(2, candidate - 1, candidate)
    if residue != direct:
        raise AssertionError("squareDup schedule disagrees with direct modular exponentiation")
    return PRPResult(base, n_log2, residue, steps)


def decode_digits(digits: list[int] | tuple[int, ...], base: int) -> int:
    value = 0
    factor = 1
    for digit in digits:
        value += digit * factor
        factor *= base
    return value


def canonical_unbalanced_digits(value: int, base: int, size: int) -> list[int]:
    """Canonical toy-oracle encoding in Z/(base^size+1).

    Residues below base^size use ordinary nonnegative radix digits.  The one
    remaining residue, base^size (which is -1), is represented as [-1, 0...].
    This is a boundary format, not Genefer's optimized balanced carry layout.
    """

    if base < 2 or size <= 0:
        raise ValueError("invalid radix shape")
    ring_modulus = pow(base, size) + 1
    residue = value % ring_modulus
    if residue == ring_modulus - 1:
        return [-1] + [0] * (size - 1)
    output: list[int] = []
    for _ in range(size):
        residue, digit = divmod(residue, base)
        output.append(digit)
    if residue:
        raise AssertionError("canonical residue did not fit")
    return output


def square_dup_oracle(digits: list[int], base: int, bit: int) -> list[int]:
    """Independent big-int oracle for a toy-size hardware squareDup."""

    if bit not in (0, 1):
        raise ValueError("bit must be zero or one")
    size = len(digits)
    if size == 0:
        raise ValueError("digits must be nonempty")
    ring_modulus = pow(base, size) + 1
    value = decode_digits(digits, base) % ring_modulus
    result = value * value * (2 if bit else 1) % ring_modulus
    return canonical_unbalanced_digits(result, base, size)


def validate_genefer_candidate(base: int, n_log2: int) -> None:
    """Validate the production input limits stated by pinned genefer22."""

    if not 1_024 <= base <= 2_000_000_000:
        raise ValueError("Genefer base must satisfy 1024 <= b <= 2,000,000,000")
    if base % 2:
        raise ValueError("Genefer candidates use an even base")
    if base & (base - 1) == 0:
        raise ValueError("power-of-two bases are ordinary Fermat numbers")
    if not 12 <= n_log2 <= 23:
        raise ValueError("Genefer exponent n must be in [12, 23]")
