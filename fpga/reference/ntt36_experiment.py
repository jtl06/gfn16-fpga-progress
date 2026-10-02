"""Isolated36-bit sparse-prime/radix/range proof; execute on aethia only."""
from __future__ import annotations
import argparse
from functools import lru_cache
from itertools import combinations
import json
from math import isqrt,prod
from pathlib import Path
import random
import resource
import socket

RADIX_BITS=36
RADIX=1<<RADIX_BITS
MAX_N=65536
BASES=(1000000000,604832956)

def is_prime(n):
    # Exact trial division, sufficient and inexpensive for this bounded search.
    if n<2 or n%2==0:return n==2
    return all(n%d for d in range(3,isqrt(n)+1,2))

def factors(n):
    result=[];d=2
    while d*d<=n:
        if n%d==0:
            result.append(d)
            while n%d==0:n//=d
        d=3 if d==2 else d+2
    if n>1:result.append(n)
    return result

@lru_cache(maxsize=1)
def select_basis():
    candidates=[]
    for extra_count in (1,2):
        for extras in combinations(range(18,35),extra_count):
            shifts=(35,*reversed(extras));p=1+sum(1<<s for s in shifts)
            if is_prime(p):candidates.append((len(shifts),-p,shifts))
        if len(candidates)>=3:break
    chosen=sorted(candidates)[:3]
    if len(chosen)<3:raise RuntimeError('insufficient sparse36 primes')
    result=[]
    for _,negative,shifts in chosen:
        p=-negative;fs=factors(p-1)
        g=next(g for g in range(2,p) if all(pow(g,(p-1)//f,p)!=1 for f in fs))
        result.append(dict(p=p,q=pow(p,-1,RADIX),r=RADIX%p,r2=RADIX*RADIX%p,
                           generator=g,shifts=list(shifts),factors=fs))
    return tuple(result)

def range_proof():
    fields=select_basis();pairs=[]
    for i,j in combinations(range(3),2):
        m=fields[i]['p']*fields[j]['p']
        # Strict M > 2*C, where C=2*N*(base-1)^2 includes doubling.
        maximum_base=isqrt((m-1)//(4*MAX_N))+1
        assert m>4*MAX_N*(maximum_base-1)**2
        assert m<=4*MAX_N*maximum_base**2
        pairs.append(dict(fields=[i+1,j+1],modulus=m,max_base_doubled=maximum_base,
                          max_base_square_only=isqrt((m-1)//(2*MAX_N))+1))
    all_modulus=prod(f['p'] for f in fields)
    return dict(radix_bits=36,fields=fields,max_n=MAX_N,pairs=pairs,
        universal_two36_ceiling=isqrt(((1<<72)-1)//(4*MAX_N))+1,
        supported_base_checks=[dict(base=b,required_centered_modulus_exclusive=4*MAX_N*(b-1)**2,
            any_two36_possible=(1<<72)>4*MAX_N*(b-1)**2,
            three_selected_sufficient=all_modulus>4*MAX_N*(b-1)**2) for b in BASES],
        three_field_modulus=all_modulus,
        status='arithmetic_experiment_not_NTT_or_core_replacement')

def validate():
    report=range_proof();rng=random.Random(0x36a11ce);checks=0
    for f in report['fields']:
        p,q=f['p'],f['q'];assert p.bit_length()==36 and (p-1)%(2*MAX_N)==0
        assert (p-1)**2%RADIX==0 and q==(2-p)%RADIX and p*q%RADIX==1
        assert prod(f['factors'])>0 and is_prime(p)
        for lg in range(1,17):
            order=2<<lg;w=pow(f['generator'],(p-1)//order,p)
            assert pow(w,order,p)==1 and pow(w,order//2,p)==p-1
        for lo in [0,1,RADIX-1,*[rng.randrange(RADIX) for _ in range(10000)]]:
            assert (lo-sum(lo<<s for s in f['shifts']))%RADIX==lo*q%RADIX
            assert lo+sum(lo<<s for s in f['shifts'])==lo*p<(1<<72)
            checks+=1
    assert all(not x['any_two36_possible'] and x['three_selected_sufficient'] for x in report['supported_base_checks'])
    report.update(status='passed_math_only',sparse_identity_checks=checks)
    return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path);args=ap.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30));args.output.mkdir(parents=True,exist_ok=False)
    report=validate();(args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
