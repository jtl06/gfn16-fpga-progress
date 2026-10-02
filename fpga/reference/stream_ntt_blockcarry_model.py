"""stream27-blockcarry: approved S1 arithmetic evaluation, not adopted RTL.

Frozen proposal reused by hash. Full-size transform execution is aethia-only.
The wider minimum-base guard is explicit; no unsupported vector is skipped.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys

PROFILE='stream27-blockcarry'
PROPOSAL_SHA='b6f94debf66b07aa118ab7e82be6802fd5a81cbc8c41a99cb79f65f91726e255'
_path=Path(__file__).with_name('stream_ntt_blockwrap2_proposal.py')
if hashlib.sha256(_path.read_bytes()).hexdigest()!=PROPOSAL_SHA:raise ValueError('proposal source drift')
_spec=importlib.util.spec_from_file_location('_blockcarry_proposal',_path)
proposal=importlib.util.module_from_spec(_spec);sys.modules[_spec.name]=proposal;_spec.loader.exec_module(proposal)
core=proposal.core

def exact_json(value):
    if type(value) is int and abs(value)>2**53:return str(value)
    if isinstance(value,dict):return {k:exact_json(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [exact_json(v) for v in value]
    return value

def minimum_base(n,lanes):return max(2*n+5,proposal.ceildiv(2*(2*n+24*lanes),3)+1)

def proof(n,lanes,base):
    result=proposal.bound_proof(n,lanes,base)
    return dict(result,profile=PROFILE,evaluation_authorized=True,adopted_profile=False,
                minimum_base=minimum_base(n,lanes))

def load(digits,base,lanes):
    proof(len(digits),lanes,base)
    if any(type(d) is not int or not -1<=d<base for d in digits):raise ValueError('frozen input-digit range')
    canonical=core.canonicalize(digits,base) if any(d<0 for d in digits) else list(digits)
    if canonical[0]==-1:
        return proposal.BlockState((0,)*len(digits),base,(-1,)+(0,)*(lanes-1),(0,)*lanes)
    return proposal.BlockState.from_digits(canonical,base,lanes)

def square_coefficients(state,double_bit=0,*,mutant=None):
    n=len(state.digits)
    if n>256 and socket.gethostname()!='aethia':raise RuntimeError('full-size transforms require aethia')
    if type(double_bit) is not int or double_bit not in (0,1):raise ValueError('double bit')
    profile=proof(n,len(state.c0),state.base);residues=[]
    for field,(p,g) in enumerate(core.FIELDS):
        psi=pow(g,(p-1)//(2*n),p);omega=psi*psi%p;twiddle=1;data=[]
        for d in state.digits:data.append(d*twiddle%p);twiddle=twiddle*psi%p
        data=core.forward_dif(data,p,omega,wrong_twiddle_stage=0 if mutant=='wrong-twiddle' else None)
        tables=proposal.correction_tables(state,field)
        data=[(v+proposal.spectral_correction(state,field,i,tables,mutant=mutant))**2%p for i,v in enumerate(data)]
        values=core.inverse_dit(data,p,omega);step=pow(psi,-1,p);twiddle=1
        for i,v in enumerate(values):values[i]=v*twiddle%p;twiddle=twiddle*step%p
        residues.append(values)
    coefficients=[core.centered_crt(row)*(1<<double_bit) for row in zip(*residues)]
    if max(map(abs,coefficients))>profile['doubled_coefficient_bound']:raise core.ModelMismatch('blockcarry-coefficient-range','closed bound exceeded')
    return coefficients

def verify_vectors(path,lanes):
    epoch=None;state=None;count=corrected=0;peak=0;both=0
    for row in core.normal_cases(path):
        if epoch!=row['epoch']:
            state=load(row['digits'],row['base'],lanes);epoch=row['epoch']
        coefficients=square_coefficients(state,row['double_bit'])
        serial,ends=proposal.carry_serial(coefficients,state.base,lanes)
        state,stats=proposal.carry_split(coefficients,state.base,lanes)
        if state!=serial or stats['block_carries']!=ends:raise core.ModelMismatch('blockcarry-split-versus-serial','state or boundary mismatch')
        core.check_equal(state.canonical(),list(row['expected']),'blockcarry-vector:'+row['name'])
        count+=1;corrected+=any(state.c0) or any(state.c1)
        both+=bool(any(state.c0) and any(state.c1));peak=max(peak,max(map(abs,coefficients)))
    if not count:raise ValueError('no normal cases')
    return dict(status='passed_blockcarry_arithmetic_only',profile=PROFILE,lanes=lanes,cases=count,
        corrected_cases=corrected,both_terms_nonzero_cases=both,peak_abs_coefficient=peak,
        vector_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        scope='Full normal vector stream within explicit profile guard; split/serial carries agree. No spatial timing, RTL, reset/error or resource qualification.')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--vectors',required=True,type=Path);ap.add_argument('--lanes',required=True,type=int)
    args=ap.parse_args();print(json.dumps(exact_json(verify_vectors(args.vectors,args.lanes)),indent=2))
