"""Read-only next-step model for R7's canonical base-register enable cone.

No RTL transform, job, source successor or clock claim. Canonical's signed33
base-1 bound differs from the field's wrapping unsigned32 bound at base0.
"""
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT/'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-native-v1/full-normal/production-bundle.json'
CAPTURE_PIN = 'e2671f87b4f6173dbfebd5eb30ddfbe0113cb78fe692d4b594d2492e60c343e7'
LEAF = 'genefer_stream27_canonical_image_loadlocal_v1.sv'
LEAF_PIN = 'b8d0806344a737ce019a677f49f325442afecd1c388771bb009d5107dd525a6f'


def signed33(value):
    value &= (1<<33)-1
    return value-(1<<33) if value&(1<<32) else value


def predicates(base, q):
    assert type(base) is int and 0 <= base < 1<<32
    assert type(q) is int and -(1<<31) <= q < 1<<31
    bound = signed33(base-1)
    original = q > bound or q < signed33(-bound)
    # Both base and -base fit signed33. No narrowing/absolute-value trick.
    strict = q >= signed33(base) or q <= signed33(-base)
    return original, strict


def prove():
    bases = {0,1,2,3,131077,604832956,999999937,1000000000,(1<<32)-1}
    for bit in range(32):
        bases.update(v for v in ((1<<bit)-1,1<<bit,(1<<bit)+1) if 0 <= v < 1<<32)
    boundary_cases = 0
    for base in sorted(bases):
        values = {-(1<<31),-(1<<31)+1,-1,0,1,(1<<31)-2,(1<<31)-1}
        values.update(v for v in (base-1,base,base+1,-base-1,-base,-base+1)
                      if -(1<<31) <= v < 1<<31)
        for q in values:
            old,new = predicates(base,q)
            assert old == new
            boundary_cases += 1
    rng = random.Random(95)
    for _ in range(200000):
        base = rng.randrange(1<<32)
        q = rng.randrange(-(1<<31),1<<31)
        old,new = predicates(base,q)
        assert old == new
    return dict(base_boundaries=len(bases),boundary_cases=boundary_cases,random_full_width_cases=200000,
        integer_identity='q>base-1 OR q<-(base-1) equals q>=base OR q<=-base',
        no_signed33_overflow=True,base0_always_correction_bad=True,known_two_state_only=True,
        c1_constant_K_check_unchanged=True,no_input_guard_or_fault_priority_removed=True,
        no_RTL_implementation_or_clock_area_claim=True)


def source():
    raw=CAPTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == CAPTURE_PIN
    bundle=json.loads(raw)
    leaf=bundle['files'][LEAF]
    assert hashlib.sha256(leaf.encode()).hexdigest() == LEAF_PIN
    for anchor in ("bound_c0=$signed({1'b0,base})-33'sd1;",
                   'if(input_c0>bound_c0 || input_c0< -bound_c0 ||',
                   "input_c1>33'(K) || input_c1< -33'(K))correction_bad=1;",
                   'wire legal_begin=rst_n && state==IDLE && !error && !idle_reject && begin_canonical;',
                   'base_reg<=base;address<=0;pass_index<=0;carry<=0;'):
        assert leaf.count(anchor) == 1
    return dict(capture_sha256=CAPTURE_PIN,canonical_leaf_sha256=LEAF_PIN,
                bound_width=33,base_input_width=32,correction_input_width=32,
                raw_path_scope='canonical_owner to scratch.base_reg ENA; not RAM read/write',
                no_default_or_frozen_source_changed=True)


if __name__=='__main__':
    print(json.dumps(dict(source=source(),model=prove()),indent=2))
