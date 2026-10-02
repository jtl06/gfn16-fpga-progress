"""Finite scalar-host paired native packaging; small ordinary integer oracle.

Only N32/N256 scalar arithmetic on coordinator. All HDL execution belongs to
the immutable native dispatcher, never this source preparation. Actual DUT
output words, not oracle-converted output, are compared with actual T5b RTL.
"""
import hashlib
import json
from pathlib import Path
import shutil
from .stream27_host_core_v1 import ROOT,prepare as compile_core

BENCH='rtl/tb/stream27_host_core_v1.cpp'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ordinary_image(words,base,count,mask,twice):
    """Independent whole integer square/mod, not NTT or barrier pass algorithm."""
    n=len(words)
    if n not in (32,256):raise ValueError('S4_HOST_ORACLE_SMALL_ONLY')
    modulus=base**n+1;x=sum(int(word)*base**address for address,word in enumerate(words))%modulus
    for index in range(count):x=(x*x*(2 if (twice if index==0 else (mask>>index)&1) else 1))%modulus
    if x==modulus-1:return [-1]+[0]*(n-1)
    result=[]
    for address in range(n):x,digit=divmod(x,base);result.append(digit)
    if x:raise ValueError('S4_HOST_ORACLE_MATERIALIZATION')
    return result


def cases(n):
    if n not in (32,256):raise ValueError('S4_HOST_CORPUS_SMALL_ONLY')
    result=[]
    for kind in range(5):
        base=1000000000 if kind==2 else 1000;state=0x394fed89+kind;words=[]
        for address in range(n):
            state=(1664525*state+1013904223)&0xffffffff
            words.append(0 if kind in (0,1,4) else (state%base if kind==2 else base-1))
        if kind==1:words[3]=1;words[n-1]=1
        if kind==4:words[n//2]=1 # Square exactly b^N: real7N special path, then signed-1 cold input.
        initial=list(words);jobs=[]
        for index in range(2):
            changed_base=base+9 if kind==3 and index else base
            count=([1,4,2,1,1] if index==0 else [1,2,4,1,2])[kind]
            batch=count!=1;mask=10 if kind in (1,2) else 0;twice=int(kind==2 and index==0)
            changes=[]
            if index:
                address=[3,n-1,7,0,0][kind];value=[7,5,-1,1,-1][kind];changes=[(address,value)];words[address]=value
            if any(word<-1 or word>=changed_base for word in words):raise ValueError('S4_HOST_CORPUS_INVALID_IMAGE')
            expected=ordinary_image(words,changed_base,count,mask,twice)
            jobs.append(dict(base=changed_base,count=count,mask=mask,twice=twice,batch=int(batch),changes=changes,expected=expected))
            words=expected;base=changed_base
        result.append(dict(id=kind,initial=initial,jobs=jobs))
    return result


def corpus_text(n,corpus):
    lines=[f'{n.bit_length()-1} {len(corpus)}']
    for case in corpus:
        lines+=[f"{case['id']} {len(case['jobs'])}",' '.join(map(str,case['initial']))]
        for job in case['jobs']:
            lines.append(' '.join(str(job[key]) for key in ('base','count','mask','twice','batch'))+' '+str(len(job['changes'])))
            lines+=[' '.join(map(str,change)) for change in job['changes']]
            lines.append(' '.join(map(str,job['expected'])))
    return '\n'.join(lines)+'\n'


def prepare(destination,*,n=32):
    destination=Path(destination).resolve()
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_HOST_NATIVE_FRESH_PAUSE')
    if n not in (32,256):raise ValueError('S4_HOST_NATIVE_SMALL_ONLY')
    b=compile_core(n,paired=True);aw=n.bit_length()-1;g=b['geometry'];source=destination/'inputs/fpga';source.mkdir(parents=True)
    for name,text in b['files'].items():
        path=source/'rtl'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    path=source/BENCH;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/BENCH,path)
    label=f'S4_SCALAR_HOST_T5B_AW{aw}_PASS';k=2*n+384;minimum=max(2*n+5,(2*k+2)//3+1)
    header=f'''#include "V{b['top']}.h"
using DUT=V{b['top']};
constexpr unsigned AW={aw},N={n},MIN_BASE={minimum},INTERVAL={g['warm_interval']},CARRY_DONE={g['carry_done']};
constexpr const char* PASS_LABEL="{label}";
'''
    (source/'rtl/tb/s4_host_config_v1.h').write_text(header)
    corpus=cases(n);asset='assets/host-corpus-v1.txt';(source/'assets').mkdir();(source/asset).write_text(corpus_text(n,corpus))
    deps=list(dict.fromkeys(b['source_dependencies']+['reference/stream27_host_core_native_v1.py',BENCH]))
    for name in deps:
        path=source/'lineage'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
    sources={str(path.relative_to(source)):sha(path) for path in sorted(source.rglob('*')) if path.is_file()}
    frames=sum(job['count'] for case in corpus for job in case['jobs'])
    footer=f'{label} cases=5 jobs=10 frames={frames} paired_reads={10*n} mutations=5 faults=4 reset_aborts=2 copied_words={10*n}\n'
    negative=f'S4_HOST_ORACLE_TYPED aw={aw} case=0 job=0 address=0 expected=1 actual=0\n'
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='UNBOUND_NO_DISPATCH',source_root=str(source),
        output_parent=str(destination/'UNBOUND_OUTPUT'),sources=sources,
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=BENCH,
            parameters=dict(AW=aw,P=16,CONTEXTS=1),cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name=f's4-aw{aw}-scalar-host-t5b',argv=['{exe}','{root}/'+asset],expected_returncode=0,expected_stdout=footer,expected_stderr=''),
            dict(name='s4-host-negative-oracle',argv=['{exe}','{root}/'+asset,'--negative'],expected_returncode=1,expected_stdout='',expected_stderr=negative)],
        lint_baseline_policy='Fresh r38 class-gated lint; no defect/unknown waiver.')
    (destination/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    r=dict(status='source_prepared_not_executed',manifest_sha256=sha(destination/'manifest.json'),source_count=len(sources),top=b['top'],
        geometry=g,host_contract=b['host_contract'],cycle_contract=b['cycle_contract'],source_sha256=b['source_sha256'],generated_sha256=b['generated_sha256'],
        counts=dict(cases=5,jobs=10,frames=frames,paired_reads=10*n,mutations=5,faults=4,reset_aborts=2,copied_words=10*n),
        assets_sha256={asset:sha(source/asset)},oracle='Independent ordinary whole-integer mod b^N+1 atN32/N256, not NTT/barrier implementation; no oracle output conversion.',
        actual_output='Candidate actual copied signed32 RAM/signextended96 versus independently instantiated exact production T5b.',
        costs='Exact host_done including cold setup/cache, actual warm recurrence,6N/7N barrier,Ncopy/handoff/drain; legacycount1 and explicitbatch1/2/4 tested.',
        remaining=['long-chain arbitrary conditional-double protocol','fullN numeric/threaded native','whole physical fit/clock'],
        full_N_numeric_NTT_performed_on_Mac=False,native_run_performed=False,promotion_allowed=False)
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    if len(sys.argv)!=3:raise ValueError('S4_HOST_NATIVE_USAGE destination n')
    r=prepare(sys.argv[1],n=int(sys.argv[2]));print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','counts')},indent=2))
