"""Independent model of bounded-transfer carry normalization (not RTL).

Only the convolution coefficient bound and large-radix regime are supported.
Splitting each coefficient independently removes the wide inter-digit carry
dependency. Five-value transfer tables can then be composed in a prefix tree.
"""
from __future__ import annotations

DOMAIN = (-2, -1, 0, 1, 2)


def compose(first: tuple[int, ...], second: tuple[int, ...]) -> tuple[int, ...]:
    """Transfer through first and then second, keeping carry values explicit."""
    return tuple(second[first[c+2]+2] for c in DOMAIN)


def normalize(coefficients: list[int], base: int) -> tuple[list[int], dict]:
    n = len(coefficients)
    if n < 2 or n & (n-1) or base <= 2*n+4:
        raise ValueError("requires power-of-two N>=2 and base>2N+4")
    bound = 2*n*(base-1)**2
    if any(abs(a)>bound for a in coefficients):
        raise ValueError("coefficient exceeds square-and-double bound")
    redistributed = [0]*n
    for i, value in enumerate(coefficients):
        q1, r0 = divmod(value, base)
        q2, r1 = divmod(q1, base)
        for offset, part in enumerate((r0, r1, q2)):
            wraps, address = divmod(i+offset, n)
            redistributed[address] += part*(-1 if wraps & 1 else 1)
    transfers = [tuple((a+c)//base for c in DOMAIN) for a in redistributed]
    if any(c not in DOMAIN for f in transfers for c in f):
        raise AssertionError("carry-domain bound violated")
    # Balanced reduction checks composability rather than assuming scalar
    # carry settling. An RTL parallel prefix would retain intermediate prefixes.
    level = transfers
    while len(level)>1:
        level = [compose(level[i],level[i+1]) for i in range(0,len(level),2)]
    candidates = [c for c in DOMAIN if c == -level[0][c+2]]
    if not candidates:
        return [-1]+[0]*(n-1), {"special_minus_one":True,"transfer":level[0]}
    if len(candidates)!=1:
        raise AssertionError("nonunique canonical carry")
    initial = carry = candidates[0]
    digits=[]
    for value in redistributed:
        carry,digit=divmod(value+carry,base)
        digits.append(digit)
    if carry != -initial:
        raise AssertionError("negacyclic boundary mismatch")
    return digits, {"special_minus_one":False,"initial_carry":initial,"transfer":level[0]}
