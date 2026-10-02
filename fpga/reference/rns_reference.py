"""Small, exact reference for Genefer's 32-bit RNS arithmetic.

This module intentionally implements mathematical primitives, not the full
Genefer z-transform or proof protocol.  Constants are locked to genefer22
commit d5060c61090942f42a908492628eba13ebd7cd82.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import prod
from typing import Iterable, Sequence

RADIX = 1 << 32
MASK32 = RADIX - 1


def _is_prime_32(value: int) -> bool:
    if value < 2:
        return False
    if value % 2 == 0:
        return value == 2
    divisor = 3
    while divisor * divisor <= value:
        if value % divisor == 0:
            return False
        divisor += 2
    return True


def _prime_factors(value: int) -> tuple[int, ...]:
    factors: list[int] = []
    remainder = value
    divisor = 2
    while divisor * divisor <= remainder:
        if remainder % divisor == 0:
            factors.append(divisor)
            while remainder % divisor == 0:
                remainder //= divisor
        divisor = 3 if divisor == 2 else divisor + 2
    if remainder > 1:
        factors.append(remainder)
    return tuple(factors)


@dataclass(frozen=True)
class RNSPrime:
    name: str
    p: int
    q: int
    r: int
    r2: int
    generator: int

    def validate(self) -> None:
        if not (0 < self.p < RADIX):
            raise ValueError(f"{self.name}: modulus is not a positive 32-bit value")
        if (self.p * self.q) & MASK32 != 1:
            raise ValueError(f"{self.name}: q is not p^-1 modulo 2^32")
        if self.r != RADIX % self.p:
            raise ValueError(f"{self.name}: incorrect Montgomery R")
        if self.r2 != (self.r * self.r) % self.p:
            raise ValueError(f"{self.name}: incorrect Montgomery R^2")
        if not _is_prime_32(self.p):
            raise ValueError(f"{self.name}: modulus is not prime")
        for factor in _prime_factors(self.p - 1):
            if pow(self.generator, (self.p - 1) // factor, self.p) == 1:
                raise ValueError(f"{self.name}: generator does not have full order")

    def add(self, lhs: int, rhs: int) -> int:
        total = lhs + rhs
        return total - self.p if total >= self.p else total

    def sub(self, lhs: int, rhs: int) -> int:
        return lhs - rhs if lhs >= rhs else lhs + self.p - rhs

    def mont_mul(self, lhs: int, rhs: int) -> int:
        """Match Genefer OpenCL mulmod for two residues in [0, p)."""

        if not (0 <= lhs < self.p and 0 <= rhs < self.p):
            raise ValueError("Montgomery operands must be reduced residues")
        product = lhs * rhs
        lo = product & MASK32
        hi = (product >> 32) & MASK32
        m = (lo * self.q) & MASK32
        mp_hi = (m * self.p) >> 32
        return self.sub(hi, mp_hi)

    def to_mont(self, value: int) -> int:
        return self.mont_mul(value % self.p, self.r2)

    def from_mont(self, value: int) -> int:
        return self.mont_mul(value, 1)

    def pow_mont(self, value_mont: int, exponent: int) -> int:
        if exponent < 0:
            raise ValueError("negative exponent")
        result = self.r
        base = value_mont
        power = exponent
        while power:
            if power & 1:
                result = self.mont_mul(result, base)
            base = self.mont_mul(base, base)
            power >>= 1
        return result

    def primitive_root(self, order: int) -> int:
        if order <= 0 or (self.p - 1) % order:
            raise ValueError(f"{order} does not divide {self.name} - 1")
        root = pow(self.generator, (self.p - 1) // order, self.p)
        if pow(root, order, self.p) != 1:
            raise AssertionError("invalid root order")
        for factor in _prime_factors(order):
            if pow(root, order // factor, self.p) == 1:
                raise AssertionError("root has smaller than requested order")
        return root


GENEFER_SIGNED_PRIMES: tuple[RNSPrime, ...] = (
    RNSPrime("P1", 2_130_706_433, 2_164_260_865, 33_554_430, 402_124_772, 3),
    RNSPrime("P2", 2_113_929_217, 2_181_038_081, 67_108_862, 2_111_798_781, 5),
    RNSPrime("P3", 2_013_265_921, 2_281_701_377, 268_435_454, 1_172_168_163, 31),
)

GENEFER_UNSIGNED_PRIMES: tuple[RNSPrime, ...] = (
    RNSPrime("P1U", 4_194_304_001, 100_663_297, 100_663_295, 232_465_106, 3),
    RNSPrime("P2U", 4_076_863_489, 218_103_809, 218_103_807, 3_444_438_393, 7),
    RNSPrime("P3U", 3_942_645_761, 352_321_537, 352_321_535, 3_810_498_414, 3),
)


@dataclass(frozen=True)
class RNSProfile:
    name: str
    primes: tuple[RNSPrime, ...]


def profile_for(base: int, n_log2: int) -> RNSProfile:
    """Match transform_ocl.cpp's exact integer/strict-comparison selection."""

    if base <= 0 or n_log2 < 0:
        raise ValueError("base and transform exponent must be positive")
    transform_size = 1 << n_log2
    signed_limit = GENEFER_SIGNED_PRIMES[0].p * GENEFER_SIGNED_PRIMES[1].p // 2 // transform_size
    unsigned_limit = GENEFER_UNSIGNED_PRIMES[0].p * GENEFER_UNSIGNED_PRIMES[1].p // 2 // transform_size
    if base * base < signed_limit:
        return RNSProfile("s2", GENEFER_SIGNED_PRIMES[:2])
    if base * base < unsigned_limit:
        return RNSProfile("u2", GENEFER_UNSIGNED_PRIMES[:2])
    if base <= 1_000_000_000:
        return RNSProfile("s3", GENEFER_SIGNED_PRIMES)
    return RNSProfile("u3", GENEFER_UNSIGNED_PRIMES)


def ntt(values: Sequence[int], prime: RNSPrime, *, inverse: bool = False) -> list[int]:
    """Reference radix-2 cyclic NTT using Montgomery butterflies.

    This validates arithmetic building blocks.  Genefer's production
    transform uses a different optimized layout and z-transform schedule.
    """

    n = len(values)
    if n == 0 or n & (n - 1):
        raise ValueError("NTT length must be a nonzero power of two")
    if (prime.p - 1) % n:
        raise ValueError("NTT length does not divide p - 1")

    data = [prime.to_mont(value) for value in values]

    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            data[i], data[j] = data[j], data[i]

    root = prime.primitive_root(n)
    if inverse:
        root = pow(root, -1, prime.p)

    length = 2
    while length <= n:
        twiddle_step = prime.to_mont(pow(root, n // length, prime.p))
        half = length // 2
        for start in range(0, n, length):
            twiddle = prime.r
            for offset in range(half):
                even = data[start + offset]
                odd = prime.mont_mul(data[start + offset + half], twiddle)
                data[start + offset] = prime.add(even, odd)
                data[start + offset + half] = prime.sub(even, odd)
                twiddle = prime.mont_mul(twiddle, twiddle_step)
        length <<= 1

    if inverse:
        scale = prime.to_mont(pow(n, -1, prime.p))
        data = [prime.mont_mul(value, scale) for value in data]

    return [prime.from_mont(value) for value in data]


def naive_ntt(values: Sequence[int], prime: RNSPrime, *, inverse: bool = False) -> list[int]:
    """Independent O(N^2) DFT used only to validate small optimized transforms."""

    n = len(values)
    if n == 0 or n & (n - 1):
        raise ValueError("NTT length must be a nonzero power of two")
    root = prime.primitive_root(n)
    if inverse:
        root = pow(root, -1, prime.p)
    result = []
    for frequency in range(n):
        total = 0
        for index, value in enumerate(values):
            total += value * pow(root, index * frequency, prime.p)
        result.append(total % prime.p)
    if inverse:
        scale = pow(n, -1, prime.p)
        result = [value * scale % prime.p for value in result]
    return result


def cyclic_convolution(lhs: Sequence[int], rhs: Sequence[int], prime: RNSPrime) -> list[int]:
    if len(lhs) != len(rhs):
        raise ValueError("cyclic convolution operands must have equal length")
    left = ntt(lhs, prime)
    right = ntt(rhs, prime)
    pointwise = [(a * b) % prime.p for a, b in zip(left, right, strict=True)]
    return ntt(pointwise, prime, inverse=True)


def schoolbook_cyclic_convolution(
    lhs: Sequence[int], rhs: Sequence[int], modulus: int
) -> list[int]:
    if len(lhs) != len(rhs):
        raise ValueError("cyclic convolution operands must have equal length")
    n = len(lhs)
    result = [0] * n
    for i, a in enumerate(lhs):
        for j, b in enumerate(rhs):
            result[(i + j) % n] = (result[(i + j) % n] + a * b) % modulus
    return result


def negacyclic_convolution(lhs: Sequence[int], rhs: Sequence[int], prime: RNSPrime) -> list[int]:
    """Compute multiplication modulo x^N + 1 with a conventional NTT twist."""

    if len(lhs) != len(rhs):
        raise ValueError("negacyclic convolution operands must have equal length")
    n = len(lhs)
    if n == 0 or n & (n - 1):
        raise ValueError("negacyclic convolution length must be a power of two")
    psi = prime.primitive_root(2 * n)
    psi_inverse = pow(psi, -1, prime.p)
    left_twisted: list[int] = []
    right_twisted: list[int] = []
    left_factor = 1
    right_factor = 1
    for left, right in zip(lhs, rhs, strict=True):
        left_twisted.append(left * left_factor % prime.p)
        right_twisted.append(right * right_factor % prime.p)
        left_factor = left_factor * psi % prime.p
        right_factor = right_factor * psi % prime.p
    convolved = cyclic_convolution(left_twisted, right_twisted, prime)
    result: list[int] = []
    factor = 1
    for value in convolved:
        result.append(value * factor % prime.p)
        factor = factor * psi_inverse % prime.p
    return result


def schoolbook_negacyclic_convolution(
    lhs: Sequence[int], rhs: Sequence[int], modulus: int
) -> list[int]:
    if len(lhs) != len(rhs):
        raise ValueError("negacyclic convolution operands must have equal length")
    n = len(lhs)
    result = [0] * n
    for i, left in enumerate(lhs):
        for j, right in enumerate(rhs):
            index = i + j
            if index < n:
                result[index] = (result[index] + left * right) % modulus
            else:
                result[index - n] = (result[index - n] - left * right) % modulus
    return result


def centered_crt(residues: Iterable[int], primes: Sequence[RNSPrime]) -> int:
    """Reconstruct the unique centered integer represented by RNS residues."""

    residue_list = list(residues)
    if len(residue_list) != len(primes):
        raise ValueError("one residue is required for each prime")
    modulus = prod(prime.p for prime in primes)
    value = 0
    for residue, prime in zip(residue_list, primes, strict=True):
        if not 0 <= residue < prime.p:
            raise ValueError("residue outside its prime field")
        partial = modulus // prime.p
        value += residue * partial * pow(partial, -1, prime.p)
    value %= modulus
    return value - modulus if value > modulus // 2 else value


def carry_reduce(coefficients: Sequence[int], base: int) -> list[int]:
    """Normalize coefficients using b^N == -1 with an actual carry sweep.

    Output is the canonical unbalanced boundary form: digits 0..b-1, except
    the unique residue -1 is encoded as [-1, 0, ...].
    """

    if base < 2 or not coefficients:
        raise ValueError("invalid radix shape")
    work = list(coefficients)
    minus_one = [-1] + [0] * (len(work) - 1)
    for _ in range(64):
        if work == minus_one:
            return work
        output: list[int] = []
        carry = 0
        for coefficient in work:
            carry, digit = divmod(coefficient + carry, base)
            output.append(digit)
        if carry == 0:
            return output
        # carry * b^N is -carry in Z/(b^N + 1).
        output[0] -= carry
        work = output
    raise ArithmeticError("radix carry did not converge")


def rns_negacyclic_product(
    lhs: Sequence[int],
    rhs: Sequence[int],
    primes: Sequence[RNSPrime],
    *,
    coefficient_scale: int = 1,
) -> list[int]:
    """Compose per-prime NTT multiplication and centered CRT reconstruction."""

    if len(lhs) != len(rhs) or not lhs:
        raise ValueError("RNS operands must have the same nonzero length")
    if not primes or len({prime.p for prime in primes}) != len(primes):
        raise ValueError("RNS basis must contain distinct primes")
    if coefficient_scale <= 0:
        raise ValueError("coefficient scale must be positive")
    coefficient_bound = (
        len(lhs)
        * max(abs(value) for value in lhs)
        * max(abs(value) for value in rhs)
        * coefficient_scale
    )
    crt_modulus = prod(prime.p for prime in primes)
    if 2 * coefficient_bound >= crt_modulus:
        raise ValueError("RNS basis is too small for unambiguous centered reconstruction")
    residue_planes = [negacyclic_convolution(lhs, rhs, prime) for prime in primes]
    return [
        centered_crt((plane[index] for plane in residue_planes), primes)
        for index in range(len(lhs))
    ]


def rns_square_dup(
    digits: Sequence[int], base: int, bit: int, primes: Sequence[RNSPrime]
) -> list[int]:
    if bit not in (0, 1):
        raise ValueError("bit must be zero or one")
    multiplier = 2 if bit else 1
    coefficients = rns_negacyclic_product(
        digits, digits, primes, coefficient_scale=multiplier
    )
    return carry_reduce([coefficient * multiplier for coefficient in coefficients], base)


def genefer_gpu_reported_memory_bytes(
    *, n_log2: int = 16, rns_size: int = 3, num_regs: int = 4, use_wi: bool = False
) -> tuple[int, int]:
    """Return Genefer's (reported memory, reported cache) estimates.

    The no-USE_WI estimate discounts unused/derived root storage. OpenCL buffer
    objects themselves are allocated at the larger size returned by
    genefer_gpu_allocated_buffer_bytes().
    """

    n = 1 << n_log2
    zp_word_bytes = 4
    carry_bytes = n // 4 * 8
    if use_wi:
        allocation = rns_size * n * (num_regs + 2) * zp_word_bytes + carry_bytes
        cache = rns_size * n * 2 * zp_word_bytes
    else:
        allocation = (
            rns_size * n * (2 * num_regs + 3) // 2 * zp_word_bytes + carry_bytes
        )
        cache = rns_size * n * 3 // 2 * zp_word_bytes
    return allocation, cache


def genefer_gpu_allocated_buffer_bytes(
    *, n_log2: int = 16, rns_size: int = 3, num_regs: int = 4
) -> int:
    """Sum the z, zp, w, and carry buffer sizes in engines::allocMemory()."""

    n = 1 << n_log2
    return rns_size * n * (num_regs + 2) * 4 + n // 4 * 8


for _prime in GENEFER_SIGNED_PRIMES + GENEFER_UNSIGNED_PRIMES:
    _prime.validate()
