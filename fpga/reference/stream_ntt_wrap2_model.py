"""Accepted working profile stream27-wrap2: arithmetic/contract model only.

No RTL, spatial commutator, timing, resource or final S2 profile qualification.
The frozen S1 source is verified before import and never edited. Large receipt
integers are encoded as decimal strings so a JSON/JavaScript hop is lossless.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys

PROFILE='stream27-wrap2'
CORE_SHA='b8526b6174491c35b537c0287a33c7467c07fa049c7a397c1f491e56c6121b23'
GENERATOR='reference/square_core27_regression.py'
GENERATOR_SHA='2bee8871c86c5d8da4f91cac2f216cc183f8c164a7c73984a13d2cbf2a8085af'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _core():
    path=Path(__file__).with_name('stream_ntt_model.py')
    if sha(path)!=CORE_SHA:raise ValueError('frozen S1 arithmetic source drift')
    spec=importlib.util.spec_from_file_location('_wrap2_frozen_s1',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


core=_core()
ModelMismatch=core.ModelMismatch


def exact_json(value):
    if type(value) is int and abs(value)>2**53:return str(value)
    if isinstance(value,dict):return {k:exact_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [exact_json(v) for v in value]
    return value


def bound_proof(n,base):
    proof=core.two_correction_proposal_bound(n,base)
    return dict(proof,status='accepted_working_profile_arithmetic_bound',profile=PROFILE,
                signed_digit0_min=-(base-1),signed_digit0_max=base-1,
                signed_digit1_min=-(2*n+24),signed_digit1_max=base-1+2*n+24,
                final_S2_profile_qualified=False)


@dataclass(frozen=True)
class Wrap2State:
    digits: tuple[int,...]
    base: int
    c0: int=0
    c1: int=0

    def __post_init__(self):
        proof=bound_proof(len(self.digits),self.base);B=self.base-1
        if any(type(x) is not int or not 0<=x<=B for x in self.digits):raise ValueError('provisional digits must be canonical')
        if type(self.c0) is not int or not -B<=self.c0<=0:raise ValueError('c0 range')
        if type(self.c1) is not int or abs(self.c1)>proof['c1_abs_max']:raise ValueError('c1 range')

    def canonical(self):
        return core.canonicalize(self.digits,self.base,(self.c0,self.c1))

    @classmethod
    def from_digits(cls,digits,base):
        n=len(digits);bound_proof(n,base)
        if any(type(d) is not int or (d!=-1 and not 0<=d<base) for d in digits):
            raise ModelMismatch('input-digit','outside frozen signed digit contract')
        if all(d>=0 for d in digits):return cls(tuple(digits),base)
        canonical=core.canonicalize(digits,base)
        if canonical[0]==-1:return cls((0,)*n,base,-1,0)
        return cls(tuple(canonical),base)


def point_correction(state,field,index,*,mutant=None):
    n=len(state.digits);aw=core.geometry(n);p,g=core.FIELDS[field]
    if not 0<=index<n:raise ValueError('spectral position')
    psi=pow(g,(p-1)//(2*n),p);omega=psi*psi%p
    frequency=index if mutant=='wrong-frequency' else core.bit_reverse(index,aw)
    c0=0 if mutant=='missing-c0' else state.c0
    c1=0 if mutant=='missing-c1' else state.c1
    correction=(c0+c1*psi*pow(omega,frequency,p))%p
    if mutant=='missing-wrap':return 0
    return -correction%p if mutant=='wrong-c-sign' else correction


def field_square(state,field,*,mutant=None):
    n=len(state.digits);p,g=core.FIELDS[field];psi=pow(g,(p-1)//(2*n),p);omega=psi*psi%p
    twiddle=1;twisted=[]
    for digit in state.digits:twisted.append(digit*twiddle%p);twiddle=twiddle*psi%p
    spectrum=core.forward_dif(twisted,p,omega,wrong_twiddle_stage=0 if mutant=='wrong-twiddle' else None)
    for index,value in enumerate(spectrum):spectrum[index]=(value+point_correction(state,field,index,mutant=mutant))**2%p
    result=core.inverse_dit(spectrum,p,omega);twiddle=1;step=pow(psi,-1,p)
    for index,value in enumerate(result):result[index]=value*twiddle%p;twiddle=twiddle*step%p
    return result


def square_coefficients(state,double_bit=0,*,mutant=None):
    if type(double_bit) is not int or double_bit not in (0,1):raise ValueError('double bit0/1')
    proof=bound_proof(len(state.digits),state.base)
    actual_bound=core.coefficient_bound(state.digits,(state.c0,state.c1),double_bit)
    if actual_bound>proof['doubled_coefficient_bound'] or actual_bound>core.HALF:
        raise core.CRTRangeError(actual_bound)
    residues=[field_square(state,f,mutant=mutant) for f in range(3)]
    return [core.centered_crt(row)*(1<<double_bit) for row in zip(*residues)]


def carry(coefficients,base):
    """Serial divmod oracle, with explicit digit1 carry-in and bounded split.

    This is not a P-parallel carry circuit or its critical-path estimate.
    q is top carry; signed ring correction c=-q is split as(-q0,-q1).
    """
    proof=bound_proof(len(coefficients),base);A=proof['doubled_coefficient_bound']
    if any(abs(x)>A for x in coefficients):raise ModelMismatch('carry-bound','coefficient exceeds proven profile bound')
    q=0;digits=[];carry_in_digit1=None;max_abs_q=0
    for i,value in enumerate(coefficients):
        q,digit=divmod(value+q,base);digits.append(digit);max_abs_q=max(max_abs_q,abs(q))
        if i==0:carry_in_digit1=q
        if abs(q)>proof['serial_carry_abs_bound']:raise ModelMismatch('carry-induction','serial carry bound failed')
    q1,q0=divmod(q,base)
    result=Wrap2State(tuple(digits),base,-q0,-q1)
    if result.c0+base*result.c1!=-q:raise ModelMismatch('wrap-split','incorrect signed correction')
    return result,dict(top_carry=q,carry_in_digit1=carry_in_digit1,max_abs_serial_carry=max_abs_q,
                       c0=result.c0,c1=result.c1,coefficient_abs_max=max(map(abs,coefficients)))


def square(state,double_bit=0,*,mutant=None):
    return carry(square_coefficients(state,double_bit,mutant=mutant),state.base)


class ContractError(ModelMismatch):
    def __init__(self,kind,detail):super().__init__('contract-'+kind,detail)


class Machine:
    """Transaction-level ownership model, NOT cycle-accurate RTL reset proof.

    Canonicalization is explicit before host mutation or changed-base starts.
    A reset/error invalidates every loaded word and all pending eligibility.
    """
    def __init__(self,n):
        if core.geometry(n)<5:raise ValueError('working profile AW5..16')
        self.n=n;self.epoch=0;self.reset()

    def reset(self):
        self.epoch+=1;self.failed=False;self.busy=False;self.state=None;self.pending=None
        self.host_digits=[None]*self.n;self.base=None

    def _idle(self):
        if self.failed:raise ContractError('failed','reset and full reload required')
        if self.busy:raise ContractError('busy','operation owns the state')

    def error(self):
        self.epoch+=1;self.failed=True;self.busy=False;self.state=None;self.pending=None
        self.host_digits=[None]*self.n

    def load(self,digits,base):
        self._idle()
        if len(digits)!=self.n:raise ValueError('full LOAD width')
        self.state=Wrap2State.from_digits(digits,base);self.base=base
        self.host_digits=list(digits);self.epoch+=1

    def host_write(self,address,digit):
        self._idle()
        if not 0<=address<self.n or type(digit) is not int:raise ValueError('host descriptor')
        if self.state is not None:self.host_digits=self.state.canonical()
        self.state=None;self.host_digits[address]=digit;self.epoch+=1

    def readback(self):
        self._idle()
        if self.state is not None:return self.state.canonical()
        if any(x is None for x in self.host_digits):raise ContractError('reload','not every digit loaded')
        return list(self.host_digits)

    def begin(self,double_bit=0,*,base=None,mutant=None):
        self._idle();chosen=self.base if base is None else base
        try:
            if chosen is None:raise ContractError('reload','base and all digits required')
            if self.state is None or chosen!=self.state.base:
                raw=self.state.canonical() if self.state is not None else self.host_digits
                if any(x is None for x in raw):raise ContractError('reload','not every digit loaded')
                self.state=Wrap2State.from_digits(raw,chosen)
            result,stats=square(self.state,double_bit,mutant=mutant)
        except (ValueError,ModelMismatch):
            self.error();raise
        self.busy=True;self.pending=(self.epoch,result,stats)
        return self.epoch

    def complete(self,token):
        if not self.busy or self.pending is None or token!=self.epoch or token!=self.pending[0]:
            raise ContractError('stale','reset/error/reload canceled pending result')
        _,self.state,stats=self.pending;self.base=self.state.base;self.busy=False;self.pending=None
        self.epoch+=1
        return stats

    def run(self,double_bit=0,*,base=None,mutant=None):
        return self.complete(self.begin(double_bit,base=base,mutant=mutant))


def verify_vectors(path,max_cases=None):
    if max_cases is not None and (type(max_cases) is not int or max_cases<1):raise ValueError('positive max_cases')
    machine=None;epoch=None;checked=0;nonzero_both=0;peak_q=peak_coefficient=0
    for row in core.normal_cases(path):
        if max_cases is not None and checked>=max_cases:break
        if machine is None:machine=Machine(len(row['digits']))
        if epoch!=row['epoch']:
            machine.load(row['digits'],row['base']);epoch=row['epoch']
        stats=machine.run(row['double_bit']);actual=machine.readback()
        core.check_equal(actual,list(row['expected']),'wrap2-vector:'+row['name']);checked+=1
        nonzero_both+=bool(stats['c0'] and stats['c1'])
        peak_q=max(peak_q,stats['max_abs_serial_carry']);peak_coefficient=max(peak_coefficient,stats['coefficient_abs_max'])
    if not checked:raise ValueError('no normal transactions checked')
    return dict(status='passed_wrap2_arithmetic_only',profile=PROFILE,cases=checked,
                both_correction_terms_nonzero_cases=nonzero_both,peak_abs_serial_carry=peak_q,
                peak_abs_coefficient=peak_coefficient,vector_sha256=sha(path),
                limitation='Normal arithmetic chains only. Vector rejection/ABORT commands skipped; separate transaction-level reset tests are not RTL reset/cycle proof.')


def frozen_generator(root):
    """Compile only three functions from the exact frozen ordinary-integer oracle."""
    path=Path(root)/GENERATOR
    if sha(path)!=GENERATOR_SHA:raise ValueError('frozen vector-generator identity')
    tree=ast.parse(path.read_text(),str(path));names=('pack','unpack','write_vectors')
    functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
    if [node.name for node in functions]!=list(names):raise ValueError('generator function closure')
    namespace={'random':random,'hashlib':hashlib}
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(path),'exec'),namespace)
    return namespace['write_vectors']


def prepare_vectors(destination,root=None):
    """New AW8/AW12 reusable vectors; never described as historical native evidence."""
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    generator=frozen_generator(root);destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    vectors={}
    for aw in (8,12):
        path=destination/f'vectors-aw{aw}.txt';info=generator(path,aw,20260929,True)
        count=sum(1 for _ in core.normal_cases(path))
        if count!=info['squares']:raise ValueError('generated normal count')
        vectors[str(aw)]=dict(info,path=path.name,normal_cases=count)
    receipt=dict(status='new_vectors_prepared_not_model_or_native_qualified',generator=GENERATOR,
                 generator_sha256=GENERATOR_SHA,extracted_functions=['pack','unpack','write_vectors'],
                 seed=20260929,prefix_carry=True,vectors=vectors,historical_archive=False)
    (destination/'manifest.json').write_text(json.dumps(exact_json(receipt),indent=2)+'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--vectors',type=Path);mode.add_argument('--prepare-vectors',type=Path);mode.add_argument('--proof',action='store_true')
    parser.add_argument('--max-cases',type=int)
    args=parser.parse_args()
    if args.vectors:result=verify_vectors(args.vectors,args.max_cases)
    elif args.prepare_vectors:result=prepare_vectors(args.prepare_vectors)
    else:result=dict(profile=PROFILE,proofs=[bound_proof(1<<aw,base) for aw in (5,8,12,16) for base in (2*(1<<aw)+5,604832956,1_000_000_000)])
    print(json.dumps(exact_json(result),indent=2))
