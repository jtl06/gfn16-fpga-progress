"""Isolated 27-bit RNS feasibility experiment; run validation on aethia only.

Does not change the frozen Genefer-compatible basis or select new RTL modules.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from functools import lru_cache
import hashlib
from itertools import combinations
import json
from math import prod
from pathlib import Path
import platform
import random

from .rns_reference import RNSPrime, RADIX, _is_prime_32, _prime_factors, carry_reduce, centered_crt
from .engine_regression import dif

MAX_N = 65536
MAX_BASE = 1_000_000_000
MAX_COEFFICIENT = 2 * MAX_N * (MAX_BASE - 1) ** 2


def encode(digits: list[int], base: int) -> int:
    """Balanced polynomial evaluation avoids quadratic full-size conversion."""
    if len(digits) == 1:
        return digits[0]
    half = len(digits)//2
    return encode(digits[:half], base) + pow(base, half)*encode(digits[half:], base)


@lru_cache(maxsize=1)
def select_basis() -> tuple[RNSPrime, ...]:
    # All candidates have enough 2-adic order for a negacyclic N65536 NTT.
    candidates = [k * (2 * MAX_N) + 1 for k in range(512, 1024)
                  if _is_prime_32(k * (2 * MAX_N) + 1)]
    eligible = [row for row in combinations(candidates, 3) if prod(row) > 2 * MAX_COEFFICIENT]
    # Sparse constants may map well, but this heuristic is NOT a DSP-cost proof.
    chosen = min(eligible, key=lambda row: (sum(p.bit_count() for p in row), -prod(row)))
    result = []
    for index, p in enumerate(sorted(chosen, reverse=True)):
        factors = _prime_factors(p - 1)
        generator = next(g for g in range(2, p) if all(pow(g, (p - 1)//f, p) != 1 for f in factors))
        result.append(RNSPrime(f"P27_{index+1}", p, pow(p, -1, RADIX), RADIX % p,
                               RADIX * RADIX % p, generator))
    return tuple(result)


def prove_basis(primes: tuple[RNSPrime, ...]) -> dict:
    if len(primes) != 3 or len({p.p for p in primes}) != 3:
        raise ValueError("three distinct fields required")
    modulus = prod(p.p for p in primes)
    if modulus <= 2 * MAX_COEFFICIENT:
        raise ValueError("insufficient centered-CRT dynamic range")
    for prime in primes:
        prime.validate()
        if prime.p.bit_length() != 27:
            raise ValueError("not a 27-bit modulus")
        for aw in range(1, 17):
            prime.primitive_root(2 << aw)
    p1, p2, p3 = (p.p for p in primes)
    if not p1 < 2*p2:
        raise ValueError("existing single-subtract r1-to-p2 reduction would be invalid")
    return {"primes": [asdict(p) for p in primes], "crt_modulus": modulus,
            "max_doubled_coefficient": MAX_COEFFICIENT,
            "centered_range_margin": modulus / (2 * MAX_COEFFICIENT),
            "crt_constants": {"P12": p1*p2, "INV12": pow(p1, -1, p2),
                              "INV123": pow(p1*p2, -1, p3)},
            "conversion_warning": "Radix digits may exceed a 27-bit prime. Keep a full-width digit-to-Montgomery converter; never truncate digits to27 bits.",
            "conversion_bound": "digit<2^32 and R2<P imply digit*R2<P*2^32, sufficient for the current positive-inverse Montgomery reduction formula, but wider than its documented canonical-input contract.",
            "status": "mathematical_basis_only_not_integrated_RTL_or_fitted_DSP_claim"}


def square_coefficients(digits: list[int], prime: RNSPrime) -> list[int]:
    n=len(digits);p=prime.p;psi=prime.primitive_root(2*n)
    powers=[];w=1
    for _ in range(n): powers.append(w);w=w*psi%p
    transformed=dif([a*w%p for a,w in zip(digits,powers)],p,prime.generator)
    values=dif([x*x%p for x in transformed],p,prime.generator,True)
    inverse=pow(psi,-1,p);w=1;result=[]
    for value in values: result.append(value*w%p);w=w*inverse%p
    return result


def validate(output: Path, full: bool) -> dict:
    if platform.system() != "Linux" or platform.node() != "aethia":
        raise RuntimeError("Run reference experiments on aethia only")
    output.mkdir(parents=True, exist_ok=False)
    primes=select_basis();report=prove_basis(primes)
    report.update(status="running", host=platform.node(), checks=[], full_size=full)
    root=Path(__file__).resolve().parents[1]
    names=("reference/ntt27_experiment.py", "reference/rns_reference.py", "reference/engine_regression.py")
    report["sources"]={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}
    rng=random.Random(270929)
    try:
        for aw in ([1,4,8,16] if full else [1,4,8]):
            n=1<<aw
            cases=[("random",604832956,[rng.randrange(604832956) for _ in range(n)]),
                   ("max",MAX_BASE,[MAX_BASE-1]*n), ("minus-one",604832956,[-1]+[0]*(n-1))]
            for name,base,digits in cases:
                planes=[square_coefficients(digits,p) for p in primes]
                coefficients=[centered_crt([row[i] for row in planes],primes) for i in range(n)]
                assert all(abs(c)<=n*(base-1)**2 for c in coefficients)
                if name=="max":
                    assert coefficients==[(2*i+2-n)*(base-1)**2 for i in range(n)]
                for bit in (0,1):
                    normalized=carry_reduce([c*(1<<bit) for c in coefficients],base)
                    modulus=pow(base,n)+1
                    expected=pow(encode(digits,base),2,modulus)*(1<<bit)%modulus
                    assert encode(normalized,base)%modulus==expected
                    report["checks"].append({"case":name,"n":n,"base":base,"double_bit":bit,"passed":True})
                print(f"PASS n={n} {name}: three27-bit fields, CRT and carry vs integer oracle",flush=True)
        report["status"]="passed_mathematical_experiment_not_RTL"
    finally:
        (output/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--full",action="store_true")
    args=parser.parse_args();print(json.dumps(validate(args.output,args.full),indent=2))


if __name__=="__main__":main()
