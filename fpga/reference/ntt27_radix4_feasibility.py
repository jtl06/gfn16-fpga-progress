"""Exact adjacent-stage fusion and bank/resource feasibility, not RTL simulation.

No frozen engine, profile format or arithmetic module is changed. Ordinary
modular arithmetic is deliberate: hardware still requires canonical R=2^32
Montgomery operands and a separately validated implementation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from pathlib import Path
from .ntt27_experiment import select_basis
from .engine_regression import dif
from .ntt_difdit_regression import bitreverse
from .ntt_cached_regression import encode
from .rns_reference import naive_ntt, centered_crt


def bank_of(address, banks):
    width = banks.bit_length()-1
    result = 0
    while address:
        result ^= address & (banks-1)
        address >>= width
    return result


def groups(lg, lanes, high):
    """Each yielded group contains complete four-point dependency components.

    Replace the two low-bank-coordinate representative bits by the actual
    transform bits. XOR-fold banking then has one varied bit per coordinate.
    """
    if lanes < 2 or lanes & (lanes-1):
        raise ValueError("four-point single-beat grouping requires power-of-two LANES>=2")
    if not 1 <= high < lg:
        raise ValueError("adjacent stage pair outside runtime transform")
    banks = 2*lanes; width = banks.bit_length()-1
    low = high-1
    chosen = {high % width:high, low % width:low}
    varying = sorted({chosen.get(r,r) for r in range(min(width,lg))})
    fixed = [bit for bit in range(lg) if bit not in varying]
    for index in range(1 << len(fixed)):
        base = sum(((index >> j) & 1) << bit for j,bit in enumerate(fixed))
        addresses = [base | sum(((v >> j) & 1) << bit for j,bit in enumerate(varying))
                     for v in range(1 << len(varying))]
        yield addresses


def roots_for_group(addresses, lg, high):
    low = high-1
    # First/second in descending DIF order; DIT consumes these in reverse.
    first = {(a & ((1 << high)-1)) << (lg-1-high)
             for a in addresses if not (a & (1 << high))}
    second = {(a & ((1 << low)-1)) << (lg-1-low)
              for a in addresses if not (a & (1 << low))}
    return first, second


def check_banks(lg, lanes, high):
    n = 1 << lg; banks = 2*lanes; width = banks.bit_length()-1
    visited = bytearray(n); group_roots = []; root_reads = [0,0]
    for addresses in groups(lg,lanes,high):
        unique = set(addresses)
        assert len(unique) == min(n,banks)
        assert len({bank_of(a,banks) for a in addresses}) == len(addresses)
        for a in addresses:
            assert not visited[a]; visited[a] = 1
            assert (a ^ (1 << high)) in unique
            assert (a ^ (1 << (high-1))) in unique
            # The existing bank/row inverse remains exactly valid.
            b = bank_of(a,banks); row = a >> width
            assert (row << width) | (b ^ bank_of(row << width,banks)) == a
        roots = roots_for_group(addresses,lg,high)
        maps = []
        for side, exponents in enumerate(roots):
            mapping = {bank_of(exponent,banks):exponent for exponent in exponents}
            assert len(mapping) == len(exponents), "root-bank conflict within one microphase"
            root_reads[side] += len(exponents); maps.append(mapping)
        group_roots.append(maps)
    assert all(visited)
    # A spatial two-layer pipeline would fetch roots for A(g) and B(g-6)
    # simultaneously. Show actual distinct-address collisions, if any, rather
    # than assuming aggregate root bandwidth proves the schedule.
    conflicts = 0; witness = None
    for g in range(6,len(group_roots)):
        a, b = group_roots[g][0], group_roots[g-6][1]
        for bank in a.keys() & b.keys():
            if a[bank] != b[bank]:
                conflicts += 1
                if witness is None: witness = {"read_group":g,"second_group":g-6,"bank":bank,"first_root":a[bank],"second_root":b[bank]}
    return {"lg":lg,"lanes":lanes,"high_stage":high,"groups":len(group_roots),
            "addresses_checked":n,"root_reads":root_reads,
            "spatial_root_conflicts_at_lag6":conflicts,"spatial_conflict_example":witness}


def dif4(values, w, w_low, i, p, factored=False):
    a,b,c,d = values
    if factored:
        plus = (a+c) % p; other = (b+d) % p
        delta = (a-c) % p; rotated = (b-d)*i % p
        return [(plus+other)%p, (plus-other)*w_low%p,
                (delta+rotated)*w%p, (delta-rotated)*(w*w_low%p)%p]
    x0 = (a+c)%p; x1 = (b+d)%p
    x2 = (a-c)*w%p; x3 = (b-d)*(w*i%p)%p
    return [(x0+x1)%p, (x0-x1)*w_low%p, (x2+x3)%p, (x2-x3)*w_low%p]


def dit4(values, w, w_low, i, p):
    a,b,c,d = values
    x0 = (a+b*w_low)%p; x1 = (a-b*w_low)%p
    x2 = (c+d*w_low)%p; x3 = (c-d*w_low)%p
    return [(x0+x2*w)%p, (x1+x3*(w*i%p))%p,
            (x0-x2*w)%p, (x1-x3*(w*i%p))%p]


def single_stage(a, stage, omega, p, reverse):
    half = 1 << stage; stride = len(a)//(2*half)
    for start in range(0,len(a),2*half):
        for j in range(half):
            u,v = a[start+j],a[start+j+half]; w = pow(omega,j*stride,p)
            if reverse: a[start+j],a[start+j+half] = (u+v)%p,(u-v)*w%p
            else: a[start+j],a[start+j+half] = (u+v*w)%p,(u-v*w)%p


def fused_transform(values, prime, inverse=False, reverse=True, lanes=16, factored=False):
    n = len(values); lg = n.bit_length()-1; p = prime.p
    omega = pow(prime.generator,(p-1)//n,p)
    if inverse: omega = pow(omega,-1,p)
    powers = [1]*(n//2)
    for j in range(1,len(powers)): powers[j] = powers[j-1]*omega%p
    i = pow(omega,n//4,p) if n >= 4 else 0
    a = [x%p for x in values]
    order = list(range(lg-1,-1,-1) if reverse else range(lg))
    for pos in range(0,lg,2):
        if pos+1 == lg:
            single_stage(a,order[pos],omega,p,reverse); continue
        high = max(order[pos:pos+2]); low = high-1
        for addresses in groups(lg,lanes,high):
            for base in addresses:
                if base & ((1 << high)|(1 << low)): continue
                indices = [base,base|(1 << low),base|(1 << high),base|(1 << low)|(1 << high)]
                j = base & ((1 << low)-1)
                w = powers[j << (lg-1-high)]; w_low = powers[j << (lg-high)]
                values4 = [a[index] for index in indices]
                result = dif4(values4,w,w_low,i,p,factored) if reverse else dit4(values4,w,w_low,i,p)
                for index,value in zip(indices,result): a[index] = value
    return a


def reusable_pipeline(groups_count):
    """Clock-edge schedule with the frozen six-stage butterfly latency.

    Read A at2g; accept A at2g+1; output after2g+6; hold at2g+7.
    Read B roots at2g+7; accept B at2g+8; output after2g+13;
    commit the banked result at2g+14. One extra frame holds A results.
    """
    requests = {}; root_reads = {}; live = set(); peak_live = 0
    for g in range(groups_count):
        for tick,phase in ((2*g+1,"A"),(2*g+8,"B")):
            assert tick not in requests; requests[tick] = (g,phase)
        for tick,phase in ((2*g,"A"),(2*g+7,"B")):
            assert tick not in root_reads; root_reads[tick] = (g,phase)
    for tick in range(2*groups_count+13):
        if tick >= 8 and tick % 2 == 0:
            g = (tick-8)//2
            if g < groups_count: assert g in live; live.remove(g)
        if tick >= 7 and tick % 2 == 1:
            g = (tick-7)//2
            if g < groups_count: live.add(g)
        peak_live = max(peak_live,len(live))
    assert not live
    return {"groups":groups_count,"read_to_write_clocks":14,"extra_intermediate_frames":peak_live,
            "pair_cycles_with_one_setup":2*groups_count+14,
            "baseline_two_stage_cycles":2*(groups_count+8)}


def verify_transform(lg, lanes, prime, seed):
    rng = random.Random(seed); n = 1 << lg; p = prime.p
    patterns = [[0]*n,[p-1]*n,[rng.randrange(p) for _ in range(n)]] if lg <= 5 else [[rng.randrange(p) for _ in range(n)]]
    count = 0
    for a in patterns:
        for inverse in (False,True):
            natural = dif(a,p,prime.generator,inverse)
            if inverse: natural = [v*n%p for v in natural]
            if lg <= 5:
                naive = naive_ntt(a,prime,inverse=inverse)
                if inverse: naive = [v*n%p for v in naive]
                assert natural == naive
            assert fused_transform(a,prime,inverse,True,lanes) == bitreverse(natural)
            assert fused_transform(a,prime,inverse,True,lanes,True) == bitreverse(natural)
            assert fused_transform(bitreverse(a),prime,inverse,False,lanes) == natural
            count += 3*n
    return count


def negacyclic_case(lg, lanes, digits, base, primes):
    n = 1 << lg; planes = []
    for prime in primes:
        p = prime.p; psi = pow(prime.generator,(p-1)//(2*n),p)
        twisted = [d*pow(psi,j,p)%p for j,d in enumerate(digits)]
        forward = fused_transform(twisted,prime,False,True,lanes)
        back = fused_transform([v*v%p for v in forward],prime,True,False,lanes)
        planes.append([v*pow(n,-1,p)*pow(psi,-j,p)%p for j,v in enumerate(back)])
    coeff = [centered_crt((plane[j] for plane in planes),primes) for j in range(n)]
    modulus = pow(base,n)+1
    assert encode(coeff,base)%modulus == pow(encode(digits,base),2,modulus)
    doubled = [centered_crt((2*planes[f][j]%primes[f].p for f in range(3)),primes) for j in range(n)]
    assert doubled == [2*c for c in coeff]
    assert encode(doubled,base)%modulus == 2*pow(encode(digits,base),2,modulus)%modulus
    if all(d == base-1 for d in digits):
        assert coeff == [(2*j-n+2)*(base-1)**2 for j in range(n)]
    if n <= 32:
        exact = [0]*n
        for i,a in enumerate(digits):
            for j,b in enumerate(digits): exact[(i+j)%n] += a*b*(1 if i+j<n else -1)
        assert coeff == exact
    return {"lg":lg,"lanes":lanes,"base":base,"coefficients":n,
            "input_kind":"all_max" if all(d==base-1 for d in digits) else "minus_one" if digits==[-1]+[0]*(n-1) else "random",
            "whole_integer_match":True,"optional_double_match":True}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--quick",action="store_true")
    args = parser.parse_args(); maximum = 10 if args.quick else 16
    primes = select_basis(); bank_checks = []; value_checks = 0; squares = []
    for lanes in (16,64):
        for lg in range(2,maximum+1):
            for high in range(1,lg): bank_checks.append(check_banks(lg,lanes,high))
        for lg in range(1,maximum+1):
            for index,prime in enumerate(primes): value_checks += verify_transform(lg,lanes,prime,73013+lg+index)
        for lg in (1,4,maximum):
            rng = random.Random(93017+lg); n = 1 << lg; base = 1000000000
            squares.append(negacyclic_case(lg,lanes,[rng.randrange(base) for _ in range(n)],base,primes))
            if lg <= 4: squares.append(negacyclic_case(lg,lanes,[-1]+[0]*(n-1),base,primes))
            if lg == maximum: squares.append(negacyclic_case(lg,lanes,[base-1]*n,base,primes))
    schedules = [reusable_pipeline(g) for g in (1,2,3,4,8,32,512,2048)]
    full = []
    for lanes in (16,64):
        n = 1 << maximum; g = max(1,n//(2*lanes)); pair_count = maximum//2
        existing = maximum*(g+8)
        proposed = pair_count*(2*g+14)+(g+8 if maximum%2 else 0)
        paired = [row for row in bank_checks if row["lg"]==maximum and row["lanes"]==lanes and row["high_stage"] in range(maximum-1,0,-2)]
        full.append({"lanes":lanes,"n":n,"paired_stages_per_transform":pair_count,
            "baseline_data_word_accesses_per_transform":2*n*maximum,
            "fused_data_word_accesses_per_transform":2*n*((maximum+1)//2),
            "root_word_reads_for_fused_pairs":sum(sum(row["root_reads"]) for row in paired),
            "baseline_root_word_reads":g*sum(min(lanes,1<<s) for s in range(maximum)),
            "generic_modular_products_per_pair":n,
            "extra_generic_multiplier_pipelines":0,
            "extra_intermediate_data_bits":2*lanes*32,
            "modeled_transform_cycles":proposed,"baseline_transform_cycles":existing,
            "cycle_model_scope":"shared butterfly array, exact static issue model; unvalidated RTL, root fetch aligned to phase, excludes new routing or control stalls"})
    report = {"status":"mathematical_prototype_passed_not_rtl","max_lg":maximum,
        "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "montgomery_hardware_radix_bits":32,"reference_arithmetic":"ordinary exact modular integers",
        "bank_cases":len(bank_checks),"addresses_checked":sum(r["addresses_checked"] for r in bank_checks),
        "transform_coefficient_checks":value_checks,"whole_integer_squares":squares,
        "root_fourth_units":[{"P":p.p,"i":(i:=pow(p.generator,(p.p-1)//4,p.p)),"centered_i":i if i<p.p//2 else i-p.p} for p in primes],
        "shared_pipeline_schedules":schedules,"resource_models":full,
        "spatial_root_conflict_examples":[next(r for r in bank_checks if r["lg"]==maximum and r["lanes"]==lanes and r["spatial_conflict_example"]) for lanes in (16,64)],
        "reference_source_hashes":{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ("ntt27_experiment.py","engine_regression.py","ntt_difdit_regression.py","ntt_cached_regression.py","rns_reference.py")},
        "all_pair_bank_checks_passed":True,
        "limits":["No RTL, synthesis or throughput result.","Spatial doubling requires additional butterfly arrays and a different root delivery schedule; naive same-bank dual fetch conflicts.","Factored radix4 retains a nontrivial fourth-root multiplication; it is not a free complex swap.","Odd logarithms keep one unchanged radix2 stage; runtimeN2 is unchanged."]}
    print(json.dumps(report,indent=2))

if __name__ == "__main__": main()
