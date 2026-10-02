"""Bounded materialized canonical-readback barrier, outside warm recurrence.

Three serial Euclidean passes plus a special-image write pass. Numeric model
and independent whole-integer oracle are deliberately limited to N<=256;
full-N geometry/bounds/cycle/resource ledgers use no numeric NTT or big residue.
"""
from dataclasses import dataclass

MAX_BASE = 1000000000
ERRORS = dict(CONFLICT=1,LOAD_ORDER=2,BASE_RANGE=3,CORRECTION_RANGE=4,
              NOT_READY=5,DIGIT_RANGE=6,INTERNAL_RANGE=7)


def need(ok, why):
    if not ok: raise ValueError(why)


def geometry(aw, p):
    need(type(aw) is int and 5<=aw<=16 and type(p) is int and p in (8,16), 'CANON_GEOMETRY')
    n=1<<aw;t=n//p;k=2*n+24*p
    minimum=max(2*n+5,(2*k+2)//3+1)
    return dict(aw=aw,p=p,n=n,t=t,row_w=aw-(p.bit_length()-1),k=k,minimum_base=minimum)


def proof(aw,p,base):
    g=geometry(aw,p)
    need(type(base) is int and g['minimum_base']<=base<=MAX_BASE,'CANON_BASE_RANGE')
    b=base-1;k=g['k']
    need(2*k<=3*b,'CANON_PROFILE_BOUND')
    # Every pass1 feedback is in[-2,2], closed under the five-way fold.
    minimum=min(-2,-b-2,-k-2)
    maximum=max(b+2,2*b+2,b+k+2)
    need(minimum>=-2*base and maximum<3*base,'CANON_FIRST_PASS_CLOSED')
    need(-2>=-base and b+2<2*base,'CANON_SECOND_PASS_CLOSED')
    return dict(**g,base=base,b=b,first_value_minimum=minimum,first_value_maximum=maximum,
        first_carry_range=(-2,2),later_carry_range=(-1,1),
        normal_begin_to_done=6*g['n'],special_begin_to_done=7*g['n'],
        read_request_to_registered_response_edges=1,read_II=1,
        image_RAM_bits=32*g['n'],numerical_full_N_performed=False)


def fold(value,base):
    need(type(value) is int and type(base) is int and base>=3 and -2*base<=value<3*base,'CANON_FOLD_RANGE')
    q=2 if value>=2*base else 1 if value>=base else 0 if value>=0 else -1 if value>=-base else -2
    r=value-q*base
    need(0<=r<base,'CANON_FOLD_REMAINDER')
    return q,r


@dataclass(frozen=True)
class CanonicalResult:
    digits: tuple
    carries: tuple
    special: bool
    cycles: int


def validate_input(digits,c0,c1,base):
    n=len(digits);p=len(c0)
    need(n<=256,'CANON_NUMERIC_SMALL_ONLY')
    need(n>=32 and n&(n-1)==0 and len(c1)==p,'CANON_INPUT_GEOMETRY')
    info=proof(n.bit_length()-1,p,base)
    need(all(type(d) is int and 0<=d<base for d in digits),'CANON_DIGIT_RANGE')
    need(all(type(c) is int and abs(c)<=base-1 for c in c0) and
         all(type(c) is int and abs(c)<=info['k'] for c in c1),'CANON_CORRECTION_RANGE')
    return info


def canonicalize(digits,c0,c1,base):
    info=validate_input(digits,c0,c1,base);n,t=info['n'],info['t']
    image=list(digits);carry=0;ends=[]
    for phase in range(3):
        for j in range(n):
            value=image[j]+carry
            if phase==0:
                block,row=divmod(j,t)
                value+=c0[block] if row==0 else c1[block] if row==1 else 0
            carry,image[j]=fold(value,base)
            need(abs(carry)<= (2 if phase==0 else 1),'CANON_CARRY_RANGE')
        ends.append(carry)
        if phase<2:carry=-carry
    special=ends[-1]!=0
    if special:
        need((ends[-1]==1 and all(d==0 for d in image)) or
             (ends[-1]==-1 and all(d==base-1 for d in image)),'CANON_THIRD_SPECIAL_IMAGE')
        image=[-1]+[0]*(n-1)
    return CanonicalResult(tuple(image),tuple(ends),special,(7 if special else 6)*n)


def independent_integer_oracle(digits,c0,c1,base):
    """Whole-X divmod reference, independent of carry passes; small only."""
    info=validate_input(digits,c0,c1,base);n,t=info['n'],info['t']
    x=sum(d*base**j for j,d in enumerate(digits))
    x+=sum((c0[b]+c1[b]*base)*base**(b*t) for b in range(info['p']))
    modulus=base**n+1;value=x%modulus
    if value==modulus-1:return (-1,)+(0,)*(n-1)
    result=[]
    for _ in range(n):value,d=divmod(value,base);result.append(d)
    need(value==0,'CANON_ORACLE_TOP_DIGIT')
    return tuple(result)


def protocol_ledger(aw,p):
    g=geometry(aw,p)
    return dict(**g,load='strict rows0..T-1; gaps allowed; first row invalidates published image',
        begin='L+1 after final accepted load legal; freezes base/c0/c1; no coasserted requests',
        busy_requests='ignored; base/corrections frozen; no lost accepted host transaction',
        idle_fault='sticky registered error/code, no successful done, reset+fullreload recovery',
        normal_cycles=6*g['n'],special_cycles=7*g['n'],cycles_exclude='rawload rows and host reads',
        read='E0 accepted request → E1 registered signed96 data/address/valid; II1',
        materialization='32bit P-bank RAM; special writes[-1,0,...] beforedone',
        barrier_usage='once when warm recurrence stops or host access/mutation/base change requested, not per square',
        full_N_numeric_performed=False)
