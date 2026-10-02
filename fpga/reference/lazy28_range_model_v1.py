"""Scalar exploration of range-safe lazy butterflies; NOT an adopted profile.

Inputs/outputs are in [0, 2P); twiddles are canonical Montgomery residues.
No HDL, cycle, resource or timing claim is made. The frozen multiplier is NOT
compatible: it slices both inputs to 27 bits. This model explicitly preserves
the 28th data bit and uses the same positive-inverse REDC convention.

Bounds: lhs < 2P, rhs < P => T < 2P**2 < P*R, because 2P < R.
Let m=(T mod R)*P^-1 mod R. T-mP is divisible by R, and -P<t<P.
Adding P iff t<0 therefore gives a canonical Montgomery product. The largest
product has at most 55 bits. m remains 32 bits and mP needs 59 bits.
"""

FIELDS = (104857601, 69206017, 67239937)
R = 1 << 32
LOW27 = (1 << 27) - 1


def check_field(p):
    if p not in FIELDS:
        raise ValueError("unsupported field")


def mont28x27(lhs, rhs, p):
    check_field(p)
    if not (0 <= lhs < 2*p and 0 <= rhs < p):
        raise ValueError("noncanonical twiddle or out-of-range lazy data")
    # A proposed one-27x27-product plus high-bit correction realization.
    # This decomposition is exact arithmetic, NOT evidence of DSP inference.
    product = (lhs & LOW27)*rhs + ((lhs >> 27)*rhs << 27)
    m = ((product & (R-1)) * (2-p)) & (R-1)
    delta = (product >> 32) - ((m*p) >> 32)
    return delta if delta >= 0 else delta+p


def butterfly(u, v, w, p, form):
    check_field(p)
    if not (0 <= u < 2*p and 0 <= v < 2*p and 0 <= w < p):
        raise ValueError("invalid butterfly range")
    if form == "CT":
        # One pre-correction replaces two canonical output corrections.
        uc = u-p if u >= p else u
        t = mont28x27(v, w, p)
        return uc+t, uc+p-t
    if form == "GS":
        # Both sums need 29-bit temporaries before reduction to 28 bits.
        # This form alone does NOT demonstrate fewer correction operations.
        total = u+v
        diff = u+2*p-v
        a = total-2*p if total >= 2*p else total
        b = diff-2*p if diff >= 2*p else diff
        return a, mont28x27(b, w, p)
    raise ValueError("unknown butterfly form")


def oracle(u, v, w, p, form):
    """Independent modular expression: no positive-inverse REDC/decomposition."""
    twiddle = w * pow(R, -1, p) % p
    if form == "CT":
        return (u+v*twiddle) % p, (u-v*twiddle) % p
    if form == "GS":
        return (u+v) % p, ((u-v)*twiddle) % p
    raise ValueError("unknown butterfly form")
