"""r87C private scalar/range model; no HDL, fitted area or timing claims."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random

PRIMES = ((104857601, 22, 25), (69206017, 21, 33), (67239937, 17, 513))
R, RADIX = 1 << 32, 1 << 26
SOURCE = Path(__file__).resolve().parents[1] / "rtl/kernel/genefer_stream27_montgomery_factored_v1.sv"


def fold(value: int, p: int) -> int:
    # Euclidean split also works for negative intermediate values.
    high, low = divmod(value, RADIX)
    return low - (p - RADIX) * high


def range_schedule(p: int, scaled: bool) -> list[tuple[int, int]]:
    upper = (2 * p - 1) * (p - 1)
    if scaled:
        upper *= pow(R, -1, p)
    lower = 0
    intervals = [(lower, upper)]
    for _ in range(120):
        lower, upper = (-(p - RADIX) * (upper // RADIX),
                        RADIX - 1 - (p - RADIX) * (lower // RADIX))
        intervals.append((lower, upper))
        if lower >= -p and upper < 2 * p:
            return intervals
    raise AssertionError("No bounded correction schedule")


def folded_montgomery(a: int, b: int, p: int) -> int:
    if not 0 <= a < 2 * p or not 0 <= b < p:
        raise ValueError("lazy28x27 domain")
    value = a * b * pow(R, -1, p)
    for lower, upper in range_schedule(p, True)[1:]:
        value = fold(value, p)
        assert lower <= value <= upper
    if value < 0:
        value += p
    if value >= p:
        value -= p
    assert 0 <= value < p
    return value


def factored_bit_model(a: int, b: int, p: int, k: int, c: int) -> int:
    """Mirror finite-width subtractive REDC in the frozen current source."""
    if not 0 <= a < 2 * p or not 0 <= b < p:
        raise ValueError("lazy28x27 domain")
    product = ((a & ((1 << 27) - 1)) * b) + ((a >> 27) * b << 27)
    d = 32 - k
    lo = product & (R - 1)
    m_high = ((lo >> k) - c * (lo & ((1 << d) - 1))) & ((1 << d) - 1)
    m = (m_high << k) | (lo & ((1 << k) - 1))
    assert m == (lo * (2 - p)) % R
    carry = int((lo >> k) < m_high)
    mp_hi = ((m >> d) * c + ((m & ((1 << d) - 1)) * c >> d) + carry) & ((1 << 27) - 1)
    # The low product limb equals lo: subtractive REDC uses floor(m*P/R).
    assert mp_hi == (m * p) // R
    value = (product >> 32) - mp_hi
    if value < 0:
        value += p
    assert 0 <= value < p
    return value


def analyze(samples: int = 10000) -> dict:
    rng = random.Random(0x8732)
    fields = []
    checks = 0
    for p, k, c in PRIMES:
        assert p == c * (1 << k) + 1
        assert pow(p, -1, R) == (2 - p) % R
        ordinary, scaled = range_schedule(p, False), range_schedule(p, True)
        edges_a = {0, 1, p - 1, p, p + 1, 2 * p - 1,
                   (1 << 27) - 1, 1 << 27, (1 << 27) + 1}
        pairs = [(a, b) for a in sorted(edges_a) if 0 <= a < 2 * p
                 for b in (0, 1, p // 2, p - 2, p - 1)]
        # Canonical adapter and lazy core both remain in the existing R32 domain.
        pairs += [(rng.randrange(p), rng.randrange(p)) for _ in range(samples)]
        pairs += [(rng.randrange(2 * p), rng.randrange(p)) for _ in range(samples)]
        for a, b in pairs:
            expected = a * b * pow(R, -1, p) % p
            assert factored_bit_model(a, b, p, k, c) == expected
            assert folded_montgomery(a, b, p) == expected
            checks += 1
        fields.append({
            "p": p, "sparse_k": k, "sparse_c": c, "delta_from_2pow26": p - RADIX,
            "r_inverse": pow(R, -1, p), "r_inverse_popcount": pow(R, -1, p).bit_count(),
            "ordinary_product_initial_unsigned_bits": ordinary[0][1].bit_length(),
            "scaled_montgomery_initial_unsigned_bits": scaled[0][1].bit_length(),
            "ordinary_sufficient_fold_count": len(ordinary) - 1,
            "scaled_montgomery_sufficient_fold_count": len(scaled) - 1,
            "ordinary_intervals": ordinary, "scaled_montgomery_intervals": scaled,
            "scalar_checks": len(pairs),
            "ordinary_domain_counterexample": {"a": 1, "b": 1, "ordinary_result": 1,
                                               "required_montgomery_result": pow(R, -1, p)},
        })
    source = SOURCE.read_text()
    assert "m_high=lo[31:K]-lo_coeff" in source
    assert "accepted k -> k+3/II1" in source
    return {
        "evidence_class": "private scalar algorithm/range/source model only",
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "montgomery_r": R, "checks": checks, "fields": fields,
        "fold_bound_method": "Conservative integer intervals; counts are sufficient for this explicit 2^26 fold, not a lower bound for every possible reduction algorithm.",
        "correction_contract": "After listed folds x in [-P,2P); addP if negative then subtractP if >=P yields canonical. Intermediate signed precision must match each interval; never truncate low bits.",
        "current_cell_contract": "accepted E0 -> result E3, II1; async reset revokes validity. Canonical32 adapter requires operands<P; lazy28 lhs<2P, rhs27<P. One variable27x27 DSP product plus high-bit correction. Exact R32 domain and roots unchanged.",
        "assessment": "The suggested uniform two-to-three folds plus one correction is not established. This explicit ordinary-fold algorithm needs sufficient counts34/6/4; preserving R32 by constant scaling needs60/10/6. Existing subtractive REDC already exploits qinv=2-P and small25/33/513 shift-add factors. No actionable smaller E3/II1 replacement from this model; no RTL/cell fit submitted and no20ALM or whole-multiplier savings claimed.",
    }


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2))
