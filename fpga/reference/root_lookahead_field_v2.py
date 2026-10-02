"""F2 field integration oracle/data/config; no runner or HDL execution.

Ordinary modular DIF/DIT phase vectors are checked against direct polynomial
oracles at N<=256. Full numeric vectors require the admitted aethia Linux host.
Existing F2 RTL and all launcher policies remain unchanged. Native results must
check the actual paired engine, eligibility/reset, all phases and exact cycles.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
from fpga.reference import merged_negacyclic27_model as field_math
from fpga.reference.core27_prefetch_r2_structure import profile_word

ROOT=Path(__file__).resolve().parents[1]
PROFILE_SHA='2aa8c7a34a709433d5aeafa53f9cfeca996fd1d778bd45ee37b80bd84e798dc3'
MATH_SHA='103c7bbe6917288a92c7432e80d50bc317e6c50eb720a6c604b3a121966adfb4'
SELF='reference/root_lookahead_field_v2.py'
BENCH='rtl/tb/root_lookahead_field_v2.cpp'
THREAD_HEADER='rtl/tb/native_runtime_context_v1.h'
PAIR='rtl/tb/root_lookahead_engine_pair_v1.sv'


def need(ok, why):
    if not ok: raise ValueError(why)


def source_guard():
    for name,digest in [('reference/core27_prefetch_r2_structure.py',PROFILE_SHA),
                        ('reference/merged_negacyclic27_model.py',MATH_SHA)]:
        need(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,'field oracle pin:'+name)


def numeric_gate(n):
    field_math.geometry(n)
    need(n<=256 or (platform.system()=='Linux' and platform.node()=='aethia'),
         'full numeric field vectors require admitted aethia worker')


def powers(base,n,p):
    out=[1]*n
    for i in range(1,n): out[i]=out[i-1]*base%p
    return out


def cyclic(values,omega,p,*,inverse=False):
    """Ordinary integer roots; no sparse REDC or imported transform loops."""
    n=len(values);numeric_gate(n);data=list(values)
    span=2 if inverse else n
    while span<=n if inverse else span>=2:
        half=span//2;step=pow(omega,n//span,p)
        for start in range(0,n,span):
            weight=1
            for j in range(half):
                a,b=data[start+j],data[start+j+half]
                if inverse:
                    t=b*weight%p
                    data[start+j],data[start+j+half]=(a+t)%p,(a-t)%p
                else:
                    data[start+j],data[start+j+half]=(a+b)%p,(a-b)*weight%p
                weight=weight*step%p
        span=span*2 if inverse else span//2
    return data


def phases(digits,field):
    n=len(digits);numeric_gate(n);p=field.p;psi=field_math.psi_for(n,field)
    twist=[x*w*field.r%p for x,w in zip(digits,powers(psi,n,p))]
    forward=cyclic(twist,psi*psi%p,p)
    square=[x*x*pow(field.r,-1,p)%p for x in forward]
    inverse=cyclic(square,pow(psi,-2,p),p,inverse=True)
    factor=pow(n*field.r,-1,p)
    output=[x*w*factor%p for x,w in zip(inverse,powers(pow(psi,-1,p),n,p))]
    if n<=256:
        need(forward==field_math.current_parent_forward(digits,field),'forward vs frozen domain model')
        need(output==[x%p for x in field_math.direct_coefficients(digits)],'direct integer negacyclic square')
        expected=field_math.direct_spectrum(digits,field)
        need(forward==[x*field.r%p for x in expected],'independent odd-root polynomial spectrum')
    return [twist,forward,square,inverse,output]


def corpus(aw=5,field=0):
    source_guard();need(1<=aw<=16 and field in (0,1,2),'field vector config')
    n=1<<aw;numeric_gate(n);f=field_math.FIELDS[field]
    inputs=[[1]+[0]*(n-1),[0]*(n-1)+[f.p-1],[f.p-1]*n]
    seed=0xF202001+aw+field;random=[]
    for _ in range(n):
        seed=(1664525*seed+1013904223)&0xffffffff;random.append(seed%f.p)
    inputs.append(random)
    words=(2*aw+2)*257
    text=f'F2FIELD2 {aw} {f.p} {words} 4\n'
    text+=' '.join(str(profile_word(f.p,f.generator,aw,64,i)) for i in range(words))+'\n'
    for c,digits in enumerate(inputs):
        rows=phases(digits,f)
        if c==0: need(rows[-1]==digits,'impulse square')
        if c==1:
            want=[0]*n;want[n-2]=f.p-1;need(rows[-1]==want,'last monomial wrap sign')
        if c==2: need(rows[-1]==[(2*i-n+2)%f.p for i in range(n)],'all-minus-one exact coefficient formula')
        for row in [digits]+rows:text+=' '.join(map(str,row))+'\n'
    return text,dict(aw=aw,p=f.p,n=n,cases=4,operations=20,readbacks=20*n,
                     aborts=10,faults=11,numeric_oracle='ordinary DIF/DIT with small-N direct polynomial cross-check',
                     profile_words=words,profile_format=2,cycle_delta_expected=0,
                     source_hashes={SELF:hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                    'reference/core27_prefetch_r2_structure.py':PROFILE_SHA,
                                    'reference/merged_negacyclic27_model.py':MATH_SHA})


def validate(stdout,stderr,returncode,config,assets):
    """Shared native queue validator contract; no native execution here."""
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int,'field validator types')
    need(stderr=='' and returncode==0,'field native control failed')
    need(set(assets)=={'vectors'},'field validator assets')
    first=assets['vectors'].splitlines()[0].split()
    need(first==['F2FIELD2',str(config['aw']),str(config['p']),str((2*config['aw']+2)*257),'4'],
         'field validator header')
    pattern=(r'F2_FIELD_PASS aw=(\d+) p=(\d+) cases=(\d+) operations=(\d+) readbacks=(\d+) '
             r'aborts=(\d+) faults=(\d+) phase_cycles=(\d+),(\d+),(\d+),(\d+),(\d+) threads=(\d+)\n')
    match=re.fullmatch(pattern,stdout);need(match is not None,'field exact native footer')
    numbers=list(map(int,match.groups()))
    need(numbers[:7]==[config['aw'],config['p'],4,20,20*(1<<config['aw']),10,11],
         'field exact scope/coverage')
    need(all(0<x<200000 for x in numbers[7:12]),'field cycle bounds')
    need(numbers[12]==config.get('runtime_threads',1),'field runtime threads')
    return dict(status='PASS_F2_field_native_control',aw=config['aw'],p=config['p'],
                phase_cycles=numbers[7:12],total_engine_cycles=sum(numbers[7:12]),
                paired_parent_candidate_cycle_delta=0,reset_aborts=10,checked_faults=11,
                qualified_readbacks=numbers[4],independent_review_pending=True,
                physical_or_whole_core_promotion=False)


def integration_build(aw=5,field=0,runtime_threads=1):
    need(aw in (5,8,16) and field in (0,1,2),'integration build scope')
    need(runtime_threads==1 or (aw==16 and runtime_threads==2),'allocated aethia runtime threads')
    f=field_math.FIELDS[field]
    names=['genefer_montgomery_mul27_sparse_pipe','genefer_sdp_ram32','genefer_sp_ram',
           'genefer_ntt_banked27_engine','genefer_root_recurrence27','genefer_root_recurrence27_lookahead_v1',
           'genefer_ntt_banked27_prefetch_r2_orient8_rootfused_engine',
           'genefer_ntt_banked27_prefetch_r2_orient8_rootfused_lookahead_v1_engine',
           'genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_engine',
           'genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_lookahead_v1_engine']
    return dict(top='root_lookahead_engine_pair_v1',sv_sources=['rtl/kernel/'+n+'.sv' for n in names]+[PAIR],
                cpp_source=BENCH,parameters=dict(AW=aw,LANES=64,HOST_LANES=16,P=f.p,Q=f.q),
                cflags=['-std=c++17','-Werror=return-type',f'-DF2_TEST_AW={aw}',f'-DF2_TEST_P={f.p}'],
                runtime_threads=runtime_threads,
                dependencies=[THREAD_HEADER],
                validator=dict(source=SELF,function='validate',config=dict(aw=aw,p=f.p,runtime_threads=runtime_threads),
                               assets=dict(vectors=f'field-aw{aw}-f{field}-vectors.txt')),
                negative_step=dict(argv=['{exe}',f'{{root}}/field-aw{aw}-f{field}-vectors.txt','--negative-oracle'],
                                   expected_returncode=1,expected_stdout='',expected_stderr='F2_FIELD_INTEGER_ORACLE\n'),
                no_launcher_clone=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--aw',type=int,default=5)
    parser.add_argument('--field',type=int,default=0);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();text,receipt=corpus(args.aw,args.field)
    need(not args.output.exists(),'fresh vector output')
    args.output.write_text(text)
    print(json.dumps(receipt,indent=2))
