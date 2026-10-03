"""Unapproved block-wrap2 arithmetic proposal; no profile, RTL or 2T claim.

Each contiguous block normalizes with initial carry zero. Boundary carries
are retained as two sparse coefficients at the NEXT block's first positions;
the final boundary has negative sign because x**N=-1. Full-size operations
here are scalar bound calculations only; transform/quadratic tests are small.
"""
from dataclasses import dataclass
import hashlib
import importlib.util
from pathlib import Path
import sys

CORE_SHA='b8526b6174491c35b537c0287a33c7467c07fa049c7a397c1f491e56c6121b23'
PROPOSAL='stream27-blockwrap2-unapproved-proposal'
_path=Path(__file__).with_name('stream_ntt_model.py')
if hashlib.sha256(_path.read_bytes()).hexdigest()!=CORE_SHA:
    raise ValueError('frozen arithmetic dependency drift')
_spec=importlib.util.spec_from_file_location('_blockwrap2_frozen_core',_path)
core=importlib.util.module_from_spec(_spec);sys.modules[_spec.name]=core
_spec.loader.exec_module(core)


def ceildiv(a,b):return -(-a//b)


def bound_proof(n,lanes,base):
    """Triangle bound plus carry induction, including arbitrary doubled chains.

For each output index, d*d contributes N B²; d*c0 and c0*c0
contribute at most 3P B²; d*c1 and c0*c1 contribute 4P B K;
c1*c1 contributes P K². Each sparse support has P positions.
T>=2 keeps the two input supports disjoint (their product supports may overlap).
With K/B<=3/2, A/(B*b)<2*(N+3P+6P+9P/4)=2N+22.5P.
Thus ceil(A/(B*b))<=2N+23P<K=2N+24P.
Serial block carry |q|<=ceil(A/B) closes by floor-division induction;
splitting q=q0+b*q1 implies |q1|<=ceil(A/(B*b)).
"""
    core.validate_base(n,base)
    if n<32 or type(lanes) is not int or lanes<1 or lanes&(lanes-1) or n%lanes or n//lanes<2:
        raise ValueError('N>=32, power-of-two P dividing N, T=N/P>=2 required')
    B=base-1;K=2*n+24*lanes
    if 2*K>3*B:raise ValueError('unqualified base: requires 2K<=3B')
    A=2*((n+3*lanes)*B*B+4*lanes*B*K+lanes*K*K)
    Q=ceildiv(A,B);next_c1=ceildiv(A,B*base);q2=ceildiv(A,base*base)
    if next_c1>2*n+23*lanes or next_c1>=K:
        raise core.ModelMismatch('blockwrap-bound','carry invariant failed')
    if A>core.HALF:raise core.CRTRangeError(A)
    return dict(proposal=PROPOSAL,n=n,lanes=lanes,block_length=n//lanes,base=base,
                c0_abs_max=B,c1_abs_max=K,doubled_coefficient_bound=A,
                serial_carry_abs_bound=Q,next_c1_abs_bound=next_c1,q2_abs_bound=q2,
                small_carry_min=-2,small_carry_max=3,
                one_adjust_boundary_normalization_proved=q2+3<=B,
                within_centered_crt=True,arithmetic_induction_closed=True,
                adopted_profile=False,hardware_timing_qualified=False)


@dataclass(frozen=True)
class BlockState:
    digits: tuple
    base: int
    c0: tuple
    c1: tuple

    def __post_init__(self):
        proof=bound_proof(len(self.digits),len(self.c0),self.base)
        if len(self.c1)!=len(self.c0):raise ValueError('boundary array width')
        for values,low,high in ((self.digits,0,self.base-1),
                                (self.c0,1-self.base,self.base-1),
                                (self.c1,-proof['c1_abs_max'],proof['c1_abs_max'])):
            if any(type(x) is not int or not low<=x<=high for x in values):raise ValueError('state outside invariant')

    @classmethod
    def from_digits(cls,digits,base,lanes):
        return cls(tuple(digits),base,(0,)*lanes,(0,)*lanes)

    def effective(self):
        values=list(self.digits);T=len(values)//len(self.c0)
        for k,(a,b) in enumerate(zip(self.c0,self.c1)):
            values[k*T]+=a;values[k*T+1]+=b
        return values

    def canonical(self):return core.canonicalize(self.effective(),self.base)


def _finish(digits,base,lanes,block_carries):
    c0=[0]*lanes;c1=[0]*lanes
    for k,q in enumerate(block_carries):
        high,low=divmod(q,base);target=(k+1)%lanes;sign=-1 if target==0 else 1
        c0[target]=sign*low;c1[target]=sign*high
    return BlockState(tuple(digits),base,tuple(c0),tuple(c1))


def carry_serial(coefficients,base,lanes):
    """Independent serial large-divmod reference for each contiguous block."""
    proof=bound_proof(len(coefficients),lanes,base);T=proof['block_length']
    if any(type(x) is not int or abs(x)>proof['doubled_coefficient_bound'] for x in coefficients):
        raise core.ModelMismatch('blockwrap-coefficient-bound','unqualified carry input')
    digits=[];boundaries=[]
    for start in range(0,len(coefficients),T):
        q=0
        for a in coefficients[start:start+T]:
            q,d=divmod(a+q,base);digits.append(d)
            if abs(q)>proof['serial_carry_abs_bound']:raise core.ModelMismatch('blockwrap-carry-bound','serial induction')
        boundaries.append(q)
    return _finish(digits,base,lanes,boundaries),tuple(boundaries)


def carry_split(coefficients,base,lanes,*,require_one_adjust=False):
    """Arithmetic hardware sketch, NOT cycle scheduling or divider throughput.

Independent coefficient split has no large quotient feedback. Only c in
[-2,3] feeds back through y+c. Boundary raw0 may need TWO radix adjustments
under the broad arithmetic guard; the extra q2+3<=B guard proves just one.
"""
    proof=bound_proof(len(coefficients),lanes,base);T=proof['block_length']
    if require_one_adjust and not proof['one_adjust_boundary_normalization_proved']:
        raise ValueError('one-adjust hardware sketch needs q2_bound+3<=B')
    if any(type(x) is not int or abs(x)>proof['doubled_coefficient_bound'] for x in coefficients):
        raise core.ModelMismatch('blockwrap-coefficient-bound','unqualified carry input')
    digits=[];boundaries=[];raws=[];small=[];adjustments=[]
    for start in range(0,len(coefficients),T):
        parts=[]
        for a in coefficients[start:start+T]:
            q,r0=divmod(a,base);q2,r1=divmod(q,base);parts.append((r0,r1,q2))
            if abs(q2)>proof['q2_abs_bound']:raise core.ModelMismatch('blockwrap-q2-bound','coefficient split')
        c=0
        for i,(r0,r1,q2) in enumerate(parts):
            y=r0+(parts[i-1][1] if i else 0)+(parts[i-2][2] if i>=2 else 0)
            c,d=divmod(y+c,base);digits.append(d);small.append(c)
            if not -2<=c<=3:raise core.ModelMismatch('blockwrap-small-carry','six-state invariant')
        raw0=parts[-1][1]+parts[-2][2]+c;raw1=parts[-1][2]
        if require_one_adjust:
            adjust=-1 if raw0<0 else int(raw0>=base);low=raw0-adjust*base
            if not 0<=low<base:raise core.ModelMismatch('blockwrap-one-adjust','insufficient boundary correction')
        else:adjust,low=divmod(raw0,base)
        q=low+base*(raw1+adjust);boundaries.append(q);raws.append((raw0,raw1));adjustments.append(adjust)
    return _finish(digits,base,lanes,boundaries),dict(block_carries=tuple(boundaries),
        raw_boundary_pairs=tuple(raws),radix_adjustments=tuple(adjustments),
        small_carry_min=min(small),small_carry_max=max(small))


def correction_tables(state,field):
    """Two ordinary P-point DFTs; table entries are natural j mod P order."""
    n=len(state.digits);P=len(state.c0);T=n//P;p,g=core.FIELDS[field]
    psi=pow(g,(p-1)//(2*n),p);omega=psi*psi%p;root=pow(omega,T,p)
    weights=[pow(psi,k*T,p) for k in range(P)]
    tables=[]
    for coefficients in (state.c0,state.c1):
        tables.append(tuple(sum(c*weights[k]*pow(root,k*j,p) for k,c in enumerate(coefficients))%p for j in range(P)))
    return tuple(tables)


def spectral_correction(state,field,index,tables=None,*,mutant=None):
    n=len(state.digits);P=len(state.c0);aw=core.geometry(n);p,g=core.FIELDS[field]
    if not 0<=index<n:raise ValueError('spectral index')
    j=index if mutant=='wrong-frequency' else core.bit_reverse(index,aw)
    psi=pow(g,(p-1)//(2*n),p);omega=psi*psi%p
    A,B=tables if tables is not None else correction_tables(state,field)
    value=(A[j%P]+psi*pow(omega,j,p)*B[j%P])%p
    if mutant=='missing-wrap':return 0
    return -value%p if mutant=='wrong-c-sign' else value


def square_coefficients(state,double_bit=0,*,mutant=None):
    """Small arithmetic NTT test; full-N transforms explicitly excluded here."""
    n=len(state.digits)
    if n>256:raise ValueError('proposal transforms limited to N<=256 on local model')
    if type(double_bit) is not int or double_bit not in (0,1):raise ValueError('double bit')
    residues=[]
    for field,(p,g) in enumerate(core.FIELDS):
        psi=pow(g,(p-1)//(2*n),p);omega=psi*psi%p
        data=core.forward_dif([d*pow(psi,i,p)%p for i,d in enumerate(state.digits)],p,omega,
                              wrong_twiddle_stage=0 if mutant=='wrong-twiddle' else None)
        tables=correction_tables(state,field)
        data=[(x+spectral_correction(state,field,i,tables,mutant=mutant))**2%p for i,x in enumerate(data)]
        residues.append([x*pow(psi,-i,p)%p for i,x in enumerate(core.inverse_dit(data,p,omega))])
    return [core.centered_crt(row)*(1<<double_bit) for row in zip(*residues)]


def square(state,double_bit=0,*,mutant=None):
    coefficients=square_coefficients(state,double_bit,mutant=mutant)
    return carry_split(coefficients,state.base,len(state.c0))[0]


def one_adjust_counterexample():
    n=32;P=8;base=172;proof=bound_proof(n,P,base);a=[0]*n
    a[2]=proof['doubled_coefficient_bound'];a[3]=base*base-1
    state,stats=carry_split(a,base,P)
    return dict(n=n,lanes=P,base=base,coefficient_bound=proof['doubled_coefficient_bound'],
                first_block_coefficients=a[:4],raw_boundary=stats['raw_boundary_pairs'][0],
                radix_adjustment=stats['radix_adjustments'][0],
                qualification='arbitrary coefficient-bound state, not asserted reachable from a particular square',
                arithmetic_state_valid=True,one_adjust_sufficient=False)
