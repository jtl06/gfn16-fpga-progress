"""Track S1 exact arithmetic model, not RTL or a hardware timing model.

Natural-order twist -> DIF(bit-reversed) -> square -> DIT -> untwist ->
three-field centered CRT. S-v1 uses exact bounded-transfer carry. The brief's
single-correction lazy wrap is modeled but FAILS CLOSED on CRT headroom; it is
not an approved replacement profile. Two-coefficient correction is only a
separately labelled mathematical proposal. No HDL or remote actions here.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Sequence

FIELDS=((104857601,3),(69206017,5),(67239937,10))
MODULUS=FIELDS[0][0]*FIELDS[1][0]*FIELDS[2][0]
HALF=MODULUS//2
CRT_WEIGHTS=tuple((MODULUS//p)*pow(MODULUS//p,-1,p) for p,_ in FIELDS)


class ModelMismatch(AssertionError):
    def __init__(self,kind,detail):
        self.kind=kind
        super().__init__(f'{kind}: {detail}')


class CRTRangeError(ModelMismatch):
    def __init__(self,bound):
        self.bound=bound
        super().__init__('crt-range',f'coefficient bound {bound} exceeds centered CRT half {HALF}')


def geometry(n):
    if type(n) is not int or n<2 or n>65536 or n&(n-1):
        raise ValueError('power-of-two N in2..65536 required')
    return n.bit_length()-1


def validate_base(n,base):
    geometry(n)
    if type(base) is not int or not 2*n+4<base<=1_000_000_000:
        raise ValueError('frozen precision-carry base requires2N+4<base<=1e9')


def bit_reverse(value,width):
    result=0
    for _ in range(width):result=(result<<1)|(value&1);value>>=1
    return result


def stage_geometry(n):
    """Arithmetic butterfly spans; NOT spatial delay-buffer/clock claims."""
    aw=geometry(n)
    return dict(n=n,aw=aw,forward_spans=[1<<i for i in range(aw,0,-1)],
                inverse_spans=[1<<i for i in range(1,aw+1)],spectral_order='bit-reversed')


def forward_dif(values,p,omega,*,wrong_twiddle_stage=None):
    n=len(values);geometry(n);data=[v%p for v in values];span=n;stage=0
    while span>=2:
        half=span//2;step=pow(omega,n//span,p)
        for start in range(0,n,span):
            twiddle=1
            for j in range(half):
                a,b=data[start+j],data[start+j+half]
                weight=twiddle
                if stage==wrong_twiddle_stage and start==j==0:weight=weight*omega%p
                data[start+j]=(a+b)%p
                data[start+j+half]=(a-b)*weight%p
                twiddle=twiddle*step%p
        span//=2;stage+=1
    return data


def inverse_dit(values,p,omega):
    n=len(values);geometry(n);data=[v%p for v in values];span=2;inverse=pow(omega,-1,p)
    while span<=n:
        half=span//2;step=pow(inverse,n//span,p)
        for start in range(0,n,span):
            twiddle=1
            for j in range(half):
                a=data[start+j];b=data[start+j+half]*twiddle%p
                data[start+j]=(a+b)%p;data[start+j+half]=(a-b)%p
                twiddle=twiddle*step%p
        span*=2
    scale=pow(n,-1,p)
    return [x*scale%p for x in data]


def field_square(digits,field=0,*,correction=(),mutant=None):
    """Correction[j] is the coefficient added to logical digit j, not a lane.

    One correction is uniform across the spectrum. A second coefficient needs
    c1*psi*omega**frequency, where frequency is the BIT-REVERSED output index.
    """
    n=len(digits);aw=geometry(n);p,g=FIELDS[field]
    if len(correction)>n:raise ValueError('correction degree outside frame')
    psi=pow(g,(p-1)//(2*n),p);omega=psi*psi%p
    if pow(psi,n,p)!=p-1:raise ModelMismatch('root-order','negacyclic root is not primitive')
    weight=1;twisted=[]
    for d in digits:twisted.append(d*weight%p);weight=weight*psi%p
    spectrum=forward_dif(twisted,p,omega,wrong_twiddle_stage=0 if mutant=='wrong-twiddle' else None)
    for index in range(n):
        addition=correction[0] if correction else 0
        if len(correction)>1:
            freq=bit_reverse(index,aw);point=psi*pow(omega,freq,p)%p;addition=0
            for value in reversed(correction):addition=(addition*point+value)%p
        if mutant=='missing-wrap':addition=0
        elif mutant=='wrong-c-sign':addition=-addition
        spectrum[index]=(spectrum[index]+addition)**2%p
    untwisted=inverse_dit(spectrum,p,omega);weight=1;psi_inv=pow(psi,-1,p)
    for i in range(n):untwisted[i]=untwisted[i]*weight%p;weight=weight*psi_inv%p
    return untwisted


def centered_crt(residues):
    if len(residues)!=3 or any(not 0<=r<p for r,(p,_) in zip(residues,FIELDS)):
        raise ValueError('three canonical field residues required')
    value=sum(r*w for r,w in zip(residues,CRT_WEIGHTS))%MODULUS
    return value-MODULUS if value>HALF else value


def coefficient_bound(digits,correction=(),double_bit=0):
    """Uniform safe bound from convolution triangle inequality; not exact max."""
    geometry(len(digits))
    if double_bit not in (0,1):raise ValueError('double bit0/1')
    maximum=max(map(abs,digits),default=0);extra=sum(map(abs,correction))
    return (1<<double_bit)*(len(digits)*maximum**2+2*maximum*extra+extra**2)


def square_coefficients(digits,*,correction=(),double_bit=0,mutant=None):
    bound=coefficient_bound(digits,correction,double_bit)
    if bound>HALF:raise CRTRangeError(bound)
    residues=[field_square(digits,f,correction=correction,mutant=mutant) for f in range(3)]
    return [centered_crt(row)*(1<<double_bit) for row in zip(*residues)]


def direct_negacyclic_square(digits,double_bit=0):
    """Independent quadratic integer oracle; intentionally small frames only."""
    n=len(digits);geometry(n)
    if n>256:raise ValueError('quadratic oracle bounded toN<=256')
    result=[0]*n
    for i,a in enumerate(digits):
        for j,b in enumerate(digits):
            result[(i+j)%n]+=(-1 if i+j>=n else 1)*a*b
    return [v*(1<<double_bit) for v in result]


def exact_carry(coefficients,base):
    """Two-radix split then exact five-state boundary solve, matching v1 math.

    Coefficients independently become r0 + b*r1 + b²*q2. The last r1/q2
    terms wrap into BOTH low positions; only the remaining carry is small.
    """
    n=len(coefficients);validate_base(n,base)
    if any(abs(x)>2*n*(base-1)**2 for x in coefficients):
        raise ModelMismatch('carry-bound','outside frozen square-and-double range')
    redistributed=[0]*n
    for i,x in enumerate(coefficients):
        q1,r0=divmod(x,base);q2,r1=divmod(q1,base)
        for offset,part in enumerate((r0,r1,q2)):
            wraps,address=divmod(i+offset,n)
            redistributed[address]+=part*(-1 if wraps&1 else 1)
    candidates=[]
    for initial in range(-2,3):
        carry=initial
        for x in redistributed:
            carry=(x+carry)//base
            if not -2<=carry<=2:raise ModelMismatch('carry-domain','five-state bound violated')
        if initial==-carry:candidates.append(initial)
    if not candidates:return [-1]+[0]*(n-1)
    if len(candidates)!=1:raise ModelMismatch('carry-uniqueness','multiple boundary solutions')
    carry=candidates[0];digits=[]
    for x in redistributed:carry,digit=divmod(x+carry,base);digits.append(digit)
    if carry!=-candidates[0]:raise ModelMismatch('wrap-boundary','wrong final carry')
    return digits


def _pack(digits,base):
    if len(digits)==1:return digits[0]
    half=len(digits)//2
    return _pack(digits[:half],base)+pow(base,half)*_pack(digits[half:],base)


def _unpack(value,base,n):
    if n==1:return [value]
    half=n//2;high,low=divmod(value,pow(base,half))
    return _unpack(low,base,half)+_unpack(high,base,half)


def canonicalize(digits,base,correction=()):
    """Whole-integer readback oracle, independent of the five-state solver."""
    n=len(digits);validate_base(n,base);modulus=pow(base,n)+1
    value=(_pack(digits,base)+sum(c*pow(base,i) for i,c in enumerate(correction)))%modulus
    return [-1]+[0]*(n-1) if value==modulus-1 else _unpack(value,base,n)


def exact_square(digits,base,double_bit=0,*,mutant=None):
    validate_base(len(digits),base)
    if any(x!=-1 and not 0<=x<base for x in digits):raise ValueError('canonical digit input')
    return exact_carry(square_coefficients(digits,double_bit=double_bit,mutant=mutant),base)


@dataclass(frozen=True)
class LazyState:
    digits: tuple[int,...]
    base: int
    correction: tuple[int,...]=()

    def canonical(self):return canonicalize(self.digits,self.base,self.correction)


def serial_lazy_carry(coefficients,base):
    """Unbounded integer mathematical candidate, not a valid27-bit profile.

    Sum(coeff[i]*b**i)=sum(digit[i]*b**i)+q*b**N; therefore correction=-q.
    q itself is NOT the small carry of the frozen split/prefix construction.
    """
    validate_base(len(coefficients),base);carry=0;digits=[]
    for coefficient in coefficients:carry,digit=divmod(coefficient+carry,base);digits.append(digit)
    return LazyState(tuple(digits),base,(-carry,))


def lazy_square(state,double_bit=0,*,mutant=None):
    coefficients=square_coefficients(state.digits,correction=state.correction,
                                    double_bit=double_bit,mutant=mutant)
    return serial_lazy_carry(coefficients,state.base)


def all_max_counterexample(n=65536,base=1_000_000_000):
    """O(N), no full-size NTT: exact coefficients for the canonical all-B input."""
    validate_base(n,base);B=base-1
    coefficients=[(2*i+2-n)*B*B for i in range(n)]
    state=serial_lazy_carry(coefficients,base);q=-state.correction[0];d=state.digits
    actual=(d[0]-q)**2-sum(d[i]*d[n-i] for i in range(1,n))
    reconstructed=centered_crt([actual%p for p,_ in FIELDS])
    q1,q0=divmod(q,base)
    return dict(n=n,base=base,top_carry=q,provisional_digit0=d[0],corrected_digit0=d[0]-q,
                next_coefficient0=actual,next_coefficient_bits=abs(actual).bit_length(),
                crt_half=HALF,crt_alias=reconstructed,range_failure=abs(actual)>HALF,
                split_correction=(-q0,-q1))


def two_correction_proposal_bound(n,base):
    """Analytic invariant for a DIFFERENT two-coefficient correction proposal.

    For N>=32, B=b-1>=2N+4, K=2N+24: K/B<=3/2. If0<=d_i<=B,
    c0 in[-B,0], |c1|<=K, doubled convolution A=2*((N+3)B²+4BK+K²).
    |serial q|<=ceil(A/B), hence |floor(q/b)|<=ceil(A/(B*b))<=2N+23<K.
    Euclidean q=q0+b*q1 gives next(c0,c1)=(-q0,-q1), closing the range.
    Max A over allowed N,b is attained at65536,1e9 and below CRT half.
    This proves only range/algebra, NOT timing/ports/precision of a new profile.
    """
    validate_base(n,base)
    if n<32:raise ValueError('proposal proof covers AW5..16 only')
    B=base-1;K=2*n+24;bound=2*((n+3)*B*B+4*B*K+K*K)
    q_bound=(bound+B-1)//B;next_c1_bound=(q_bound+base-1)//base
    if 2*K>3*B or next_c1_bound>K:raise ModelMismatch('proposal-invariant','range closure failed')
    return dict(status='unapproved_two_correction_mathematical_proposal',n=n,base=base,
                c0_min=-B,c0_max=0,c1_abs_max=K,doubled_coefficient_bound=bound,
                serial_carry_abs_bound=q_bound,next_c1_abs_bound=next_c1_bound,
                closed=True,within_centered_crt=bound<=HALF,
                transform_correction='c0+c1*psi*omega**bit_reverse(output_index,AW)',
                hardware_timing_and_profile_qualification=False)


def check_equal(actual,expected,kind='output'):
    if actual!=expected:
        index=next((i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b),None)
        raise ModelMismatch(kind,f'first differing index {index}')


def normal_cases(path):
    """Read existing normal-vector streams; rejection/abort commands are not gates here."""
    lines=Path(path).read_text().splitlines();n=int(lines[0]);geometry(n)
    index=1;digits=None;base=None;epoch=0
    while index<len(lines):
        words=lines[index].split();index+=1
        if not words:continue
        if words[0] in ('LOAD','LOAD_KEEP'):
            base=int(words[2]);digits=tuple(map(int,lines[index].split()));index+=1;epoch+=1
            if len(digits)!=n:raise ValueError('LOAD length')
        elif words[0] in ('RUN','RUN_NOREAD'):
            expected=tuple(map(int,lines[index].split()));index+=1
            if digits is None or len(expected)!=n:raise ValueError('RUN without LOAD or wrong length')
            yield dict(epoch=epoch,name=words[1],base=base,digits=digits,expected=expected,double_bit=int(words[2]))
            digits=expected
        elif words[0] in ('BADBASE','BADDIGIT','BADDIGIT_AT','ABORT'):pass
        else:raise ValueError('unknown vector command '+words[0])


def verify_normal_vectors(path,variant='exact',max_cases=None):
    if variant not in ('exact','lazy-scalar'):raise ValueError('explicit exact/lazy-scalar variant')
    if max_cases is not None and (type(max_cases) is not int or max_cases<1):raise ValueError('positive max_cases required')
    checked=0;epoch=None;state=None
    for case in normal_cases(path):
        if max_cases is not None and checked>=max_cases:break
        if variant=='exact':actual=exact_square(case['digits'],case['base'],case['double_bit'])
        else:
            if epoch!=case['epoch']:state=LazyState(case['digits'],case['base']);epoch=case['epoch']
            state=lazy_square(state,case['double_bit']);actual=state.canonical()
        check_equal(actual,list(case['expected']),variant+'-vector:'+case['name']);checked+=1
    if not checked:raise ValueError('no normal transactions checked')
    return dict(status='passed_arithmetic_only',variant=variant,cases=checked,
                vector_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                limitation='Not cycle, spatial dataflow, RTL, reset, rejection-command, resource or clock qualification.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vectors',type=Path);parser.add_argument('--variant',choices=('exact','lazy-scalar'),default='exact')
    parser.add_argument('--max-cases',type=int);parser.add_argument('--range-audit',action='store_true')
    args=parser.parse_args()
    if args.range_audit:
        print(json.dumps(dict(scalar=all_max_counterexample(),two_correction_proposal=two_correction_proposal_bound(65536,1_000_000_000)),indent=2))
    elif args.vectors:
        if args.max_cases is not None and args.max_cases<1:parser.error('positive max-cases required')
        print(json.dumps(verify_normal_vectors(args.vectors,args.variant,args.max_cases),indent=2))
    else:parser.error('--range-audit or --vectors required')
