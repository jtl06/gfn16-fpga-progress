"""A10 merged CT/GS arithmetic profile, separate from every frozen profile.

Model only: natural ordinary residues -> bit-reversed odd-root evaluations ->
Montgomery square (R^-1 domain) -> natural GS inverse -> ordinary CRT residues.
R remains 2^32. Full numeric frames require aethia; Mac tests stop at N256.
This module deliberately imports no transform implementation for its oracle.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import prod
import platform
from typing import Sequence

PROFILE = "merged-negacyclic27-ctgs-ordinary-v1"
RADIX = 1 << 32
MASK = RADIX - 1
MAX_LOCAL_N = 256


@dataclass(frozen=True)
class Field:
    p: int
    q: int
    generator: int

    @property
    def r(self):
        return RADIX % self.p

    def mont(self, a, b):
        """Positive-inverse subtraction reduction, matching sparse27 bits."""
        if not 0 <= a < self.p or not 0 <= b < self.p:
            raise ValueError("canonical Montgomery operands required")
        product = a * b
        m = ((product & MASK) * self.q) & MASK
        result = (product >> 32) - ((m * self.p) >> 32)
        if result < 0:
            result += self.p
        assert 0 <= result < self.p
        return result

    def encode(self, value, exponent=0):
        return value % self.p * pow(self.r, exponent, self.p) % self.p


FIELDS = (Field(104857601, 4190109697, 3),
          Field(69206017, 4225761281, 5),
          Field(67239937, 4227727361, 10))
MODULUS = prod(f.p for f in FIELDS)
HALF = MODULUS // 2
CRT_WEIGHTS = tuple((MODULUS // f.p) * pow(MODULUS // f.p, -1, f.p)
                    for f in FIELDS)


class Mismatch(AssertionError):
    def __init__(self, kind, index):
        self.kind = kind
        super().__init__(f"{kind}: first mismatching index {index}")


def compare(actual, expected, kind):
    if len(actual) != len(expected):
        raise Mismatch(kind, "length")
    for i, (a, b) in enumerate(zip(actual, expected)):
        if a != b:
            raise Mismatch(kind, i)


def geometry(n):
    if type(n) is not int or n < 2 or n > 65536 or n & (n - 1):
        raise ValueError("power-of-two N2..65536 required")
    return n.bit_length() - 1


def numeric_geometry(n):
    aw = geometry(n)
    if n > MAX_LOCAL_N and (platform.system() != "Linux" or platform.node() != "aethia"):
        raise RuntimeError("numeric N>256 gate requires aethia")
    return aw


def bit_reverse(value, width):
    return int(f"{value:0{width}b}"[::-1], 2)


def psi_for(n, field):
    geometry(n)
    psi = pow(field.generator, (field.p - 1) // (2 * n), field.p)
    if (field.p - 1) % (2 * n) or pow(psi, n, field.p) != field.p - 1:
        raise ValueError("root lacks exact negacyclic order")
    return psi


def _canonical(values, field):
    numeric_geometry(len(values))
    if any(type(x) is not int or not 0 <= x < field.p for x in values):
        raise ValueError("canonical field vector required")
    return list(values)


def merged_forward(values: Sequence[int], field: Field, *, mutant=None):
    """CT multiply-before-add, descending spans, group-constant psi roots.

    Physical output i is sum_j a[j]*psi**((2*bit_reverse(i,AW)+1)*j).
    All twiddles use exponent +1 in R, preserving the input domain exponent.
    """
    data = _canonical(values, field)
    n = len(data); aw = geometry(n); p = field.p; psi = psi_for(n, field)
    groups = 1
    while groups < n:
        half = n // (2 * groups)
        for group in range(groups):
            exponent = bit_reverse(groups + group, aw)
            if mutant == "wrong-root-index":
                exponent = groups + group
            if mutant == "forward-inverse-root":
                exponent = -exponent
            root = pow(psi, exponent, p)
            power = 2 if mutant == "r2-first-stage" and groups == 1 else 1
            if mutant == "ordinary-root":
                power = 0
            weight = field.encode(root, power)
            start = group * 2 * half
            for j in range(start, start + half):
                u, v = data[j], data[j + half]
                t = field.mont(v, weight)
                data[j] = (u + t) % p
                data[j + half] = (u - t) % p
        groups *= 2
    if mutant == "natural-spectrum":
        data = [data[bit_reverse(i, aw)] for i in range(n)]
    return data


def normalization_constant(n, field, input_exponent=0):
    """Mont(N*coeff*R^(2e-1), R^(2-2e)/N) = ordinary coeff."""
    return field.encode(pow(n, -1, field.p), 2 - 2 * input_exponent)


def merged_inverse(values: Sequence[int], field: Field, *, scale=None, mutant=None):
    """GS add-before-multiply, ascending spans. Unscaled output is N*a.

    With scale supplied, final lower root incorporates scale and the upper
    output needs its own Montgomery multiplication. That extra work is counted.
    """
    data = _canonical(values, field)
    n = len(data); aw = geometry(n); p = field.p; psi = psi_for(n, field)
    if scale is not None and not 0 <= scale < p:
        raise ValueError("canonical scale required")
    groups = n // 2
    while groups:
        half = n // (2 * groups)
        for group in range(groups):
            exponent = bit_reverse(groups + group, aw)
            sign = 1 if mutant == "inverse-forward-root" else -1
            root = pow(psi, sign * exponent, p)
            final_scale = scale is not None and groups == 1
            weight = root * scale % p if final_scale else field.encode(root, 1)
            start = group * 2 * half
            for j in range(start, start + half):
                u, v = data[j], data[j + half]
                upper = (u + v) % p
                data[j] = field.mont(upper, scale) if final_scale and mutant != "upper-unscaled" else upper
                data[j + half] = field.mont((u - v) % p, weight)
        groups //= 2
    return data


def direct_spectrum(values, field):
    """Independent O(N²) polynomial evaluation, small frames only."""
    n = len(values); aw = geometry(n)
    if n > MAX_LOCAL_N:
        raise ValueError("direct spectrum oracle limited to N256")
    psi = psi_for(n, field); p = field.p
    return [sum(value * pow(psi, (2 * bit_reverse(i, aw) + 1) * j, p)
                for j, value in enumerate(values)) % p for i in range(n)]


def current_parent_forward(digits, field):
    """Source-derived format2 R² twist + conventional DIF, independent loops."""
    n = len(digits); numeric_geometry(n); p = field.p; psi = psi_for(n, field)
    omega = psi * psi % p
    data = [field.mont(d % p, field.encode(pow(psi, i, p), 2))
            for i, d in enumerate(digits)]
    span = n
    while span >= 2:
        half = span // 2; step = pow(omega, n // span, p)
        for start in range(0, n, span):
            weight = field.r
            for j in range(half):
                u, v = data[start + j], data[start + j + half]
                data[start + j] = (u + v) % p
                data[start + j + half] = field.mont((u - v) % p, weight)
                weight = weight * step % p
        span //= 2
    return data


def current_parent_square(digits, field):
    n = len(digits); data = current_parent_forward(digits, field)
    p = field.p; psi = psi_for(n, field); omega = psi * psi % p
    data = [field.mont(x, x) for x in data]
    span = 2
    while span <= n:
        half = span // 2; step = pow(omega, -n // span, p)
        for start in range(0, n, span):
            weight = field.r
            for j in range(half):
                u = data[start + j]
                v = field.mont(data[start + j + half], weight)
                data[start + j] = (u + v) % p
                data[start + j + half] = (u - v) % p
                weight = weight * step % p
        span *= 2
    inverse_n = pow(n, -1, p)
    return [field.mont(x, pow(psi, -i, p) * inverse_n % p)
            for i, x in enumerate(data)]


def field_square(digits, field, *, input_exponent=0, mutant=None, normalization="folded"):
    data = [field.encode(d, input_exponent) for d in digits]
    data = merged_forward(data, field, mutant=mutant)
    data = [field.mont(x, x) for x in data]
    scale = normalization_constant(len(data), field, input_exponent)
    if mutant == "normalization-r":
        scale = field.encode(pow(len(data), -1, field.p), 1)
    if mutant == "missing-normalization":
        scale = field.encode(1, 2 - 2 * input_exponent)
    if normalization == "folded":
        return merged_inverse(data, field, scale=scale, mutant=mutant)
    if normalization != "pre-crt":
        raise ValueError("normalization folded or pre-crt required")
    return [field.mont(x, scale) for x in merged_inverse(data, field, mutant=mutant)]


def direct_coefficients(digits):
    n = len(digits); geometry(n)
    if n > MAX_LOCAL_N:
        raise ValueError("quadratic coefficient oracle limited to N256")
    out = [0] * n
    for i, a in enumerate(digits):
        for j, b in enumerate(digits):
            out[(i + j) % n] += a * b * (-1 if i + j >= n else 1)
    return out


def square_coefficients(digits):
    numeric_geometry(len(digits))
    if len(digits) * max(map(abs, digits), default=0) ** 2 > HALF:
        raise ValueError("centered CRT coefficient bound exceeded")
    planes = [field_square(digits, field) for field in FIELDS]
    out = []
    for row in zip(*planes):
        value = sum(r * w for r, w in zip(row, CRT_WEIGHTS)) % MODULUS
        out.append(value - MODULUS if value > HALF else value)
    return out


def cycle_work(n=65536, lanes=64):
    """Source-bound parent and conditional successor; not hardware cycles.

    New merged root setup is an unknown, explicitly left symbolic. +8 stage
    and +7 point tails are inherited assumptions, not a merged-RTL result.
    """
    aw = geometry(n)
    if lanes != 64:
        raise ValueError("matched current parent has 64 arithmetic lanes")
    groups = (n + 2 * lanes - 1) // (2 * lanes)
    point_groups = (n + lanes - 1) // lanes
    point = point_groups + 7
    point_setup = min(4, point_groups) * min(lanes, n) + 4
    def transform_setup(descending):
        total = 0
        for ordinal in range(aw):
            stage = aw - 1 - ordinal if descending else ordinal
            period = 1 if stage < 7 else 1 << (stage - 6)
            seeds = min(4, groups, period) * min(lanes, 1 << stage)
            total += seeds + 4 if ordinal == 0 else 1 + max(0, seeds - groups - 4)
        return total
    parent_transform_setup = transform_setup(True) + transform_setup(False)
    parent = 3 * point + 2 * aw * (groups + 8) + 2 * point_setup + parent_transform_setup + 10
    # Three steps each retain start/done controller edges, against five before.
    successor_without_root_setup = point + 2 * aw * (groups + 8) + 6
    B = n * aw // 2
    return dict(n=n, lanes=lanes, parent_ntt_cycles=parent,
                parent_point_pass_cycles=point, parent_point_setup_cycles=point_setup,
                parent_transform_setup_cycles=parent_transform_setup,
                two_pass_only_saving=2*point,
                removed_point_setup_and_control=2*point_setup+4,
                successor_base_without_new_root_setup=successor_without_root_setup,
                folded_parallel_delta_formula=f"{parent-successor_without_root_setup} - Smerged",
                pre_crt_delta_formula=f"{parent-successor_without_root_setup-4} - Smerged - Hadditional",
                serialized_extra_issues=groups,
                serialized_delta_formula=f"{parent-successor_without_root_setup-groups} - Smerged - Hadditional",
                delta_at_inherited_root_setup_parallel=parent-successor_without_root_setup-parent_transform_setup,
                delta_at_inherited_root_setup_pre_crt=parent-successor_without_root_setup-parent_transform_setup-4,
                delta_at_inherited_root_setup_serialized=parent-successor_without_root_setup-parent_transform_setup-groups,
                montgomery_ops_per_field=dict(parent=2*B+3*n,
                    folded=2*B+n+n//2, pre_crt=2*B+2*n),
                additional_parallel_normalizer_pipelines=dict(folded=3*lanes, pre_crt=3*16),
                full_root_table_bits=2*(n-1)*27*3,
                status="conditional_model_no_cycle_resource_or_clock_qualification")
