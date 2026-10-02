"""Prepare closed T5b controls without native execution or vector regeneration.

AW5 normal, AW5 targeted E0..E9 controls, then AW16 normal. Runtime admission
uses the frozen portable launcher; its resource envelope is NOT yet qualified
for these whole-core builds. Dispatch/review and any larger envelope are main's.
"""
import hashlib
import json
from pathlib import Path
from . import core27_prefill_pipe_v1_structure as design
from . import core27_prefill_pipe_v1_gates as gates
from . import core27_prefill_structure as parent

ROOT=design.ROOT
SELF='reference/core27_prefill_pipe_v1_prepare.py'
LAUNCHER='tools/native_source_gate_v1.py'
STAGE='artifacts/core27-t5b-pipe-v1-preparation'
RUN_ROOT='/home/jtl/gfn-fpga-lab/agent-work/core27-t5b-pipe-v1'
FROZEN={
 LAUNCHER:'5205f587313a1403fddabff58bbcf4565d27c8219aa2e0c3f4aaa3af2901c2cd',
 'tools/snapshot_native_sources_v2.py':'db9786b52e0bb53545aa9a800f45dc00beec6663346cfa77f3ec2d0b1c6c5f83',
}
ANCESTORS={
 5:('core27-prefill-aw5-normal-v2',
    '0501448c1f7655b3e098c1c5dc30f3d4a4f7603fc527bb71a202ff5d86a203b7',
    'a5b46cb2f52ce817bed3de90a91dfc6fb038b30215edc7d861514d1106919edd'),
 16:('core27-prefill-aw16-normal-v1',
    '85d2f6a3eccd83928a15305e52a5319aedda9802e9d1c7e6af599ebe305b0e7d',
    '3449c1e3e1d7c0820842ecb30295b963b4aa81af6b27be8e38b7c87f2bd39f3d')}
TARGET='results/throughput-20260929/core27-prefill-aw5-base-change-v2/vectors.txt'
FROZEN[TARGET]='1080d4454da030795060b347cf1dd7f06cebae4c2451272cd6fecc01378d3603'
for aw,(directory,log,vector) in ANCESTORS.items():
    FROZEN[f'results/throughput-20260929/{directory}/normal.log']=log
    FROZEN[f'results/throughput-20260929/{directory}/vectors.txt']=vector


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normal_expected(text,aw):
    rows=[];count=0
    for line in text.splitlines():
        if ' cycles=' not in line:
            rows.append(line);continue
        label,*tokens=line.split(); values=dict(t.split('=') for t in tokens)
        cold=int(values['prefill_before'])==0
        if int(values['conversion'])!=( (1<<aw)//16+6 if cold else 0):
            raise ValueError('frozen conversion count')
        for key,delta in [('cycles',6 if cold else 3),('carry',3),('conversion',3 if cold else 0)]:
            values[key]=str(int(values[key])+delta)
        rows.append(label+' '+' '.join(k+'='+v for k,v in values.items()));count+=1
    if count!={5:568,16:12}[aw]:raise ValueError('exact normal operation count')
    return '\n'.join(rows)+'\n'


def target_steps():
    steps=[]
    for mode in ('--changed-base','--base-reject','--reload-control'):
        success,recovery=(3,0) if mode=='--changed-base' else (2,1) if mode=='--base-reject' else (2,0)
        footer=f'T5_TARGET_PASS mode={mode} age=0 row=none row_index=1 middle_aliases_final=1 event_hits=1 successful={success} readbacks={success} recoveries={recovery}\n'
        steps.append(dict(name=mode[2:],argv=['{exe}',mode,'{root}/'+TARGET,'control'],expected_returncode=0,expected_stdout=footer,expected_stderr=''))
    for fault in ('reset','error','carry-error'):
        # AW5 middle aliases final. Keep first E0 explicit, then all ten tail
        # ages through the new final-write and registered error-check edges.
        for row,ages in [('first',(0,)),('final',range(10))]:
            for age in ages:
                mode='--tail-'+fault
                footer=f'T5_TARGET_PASS mode={mode} age={age} row={row} row_index={0 if row=="first" else 1} middle_aliases_final=1 event_hits=1 successful=1 readbacks=1 recoveries=1\n'
                steps.append(dict(name=f'{fault}-{row}-e{age}',argv=['{exe}',mode,'{root}/'+TARGET,str(age),row,'control'],expected_returncode=0,expected_stdout=footer,expected_stderr=''))
    return steps


def manifests(root=ROOT):
    root=Path(root)
    if (root/'docs/briefs/PAUSE').exists():raise ValueError('brief PAUSE')
    design.validate(root);derived=gates.validate(root)
    old=parent.validate_files(root)['compiled']
    kernels=[name.replace(design.PARENT,design.CORE) for name in old if '/tb/' not in name]
    names=set(kernels)|set(derived)|set(FROZEN)|set(gates.PINS)|{
        'rtl/kernel/'+design.PARENT+'.sv',
        'reference/core27_prefill_pipe_v1_structure.py',
        'reference/core27_prefill_pipe_v1_gates.py',SELF,
        'reference/core27_prefill_pipe_v1_mutations.py',
        'tests/test_core27_prefill_pipe_v1.py'}
    for name,digest in FROZEN.items():
        if sha(root/name)!=digest:raise ValueError('frozen evidence drift: '+name)
    pins={name:sha(root/name) for name in sorted(names)}
    output={}
    for role,aw in [('aw5-normal',5),('aw5-targeted',5),('aw16-normal',16)]:
        normal=role.endswith('normal')
        top=gates.NORMAL if normal else gates.TAIL
        sv=kernels+['rtl/tb/'+top+'.sv']
        if not normal:
            sv=[p for p in sv if p!='rtl/kernel/'+design.CORE+'.sv']+['rtl/tb/'+gates.BRIDGE+'.sv']
        bench='rtl/tb/core27_prefill_pipe_'+('normal_threaded_v1.cpp' if normal else 'tail_v1.cpp')
        if normal:
            directory=ANCESTORS[aw][0];prefix='results/throughput-20260929/'+directory
            steps=[dict(name=role,argv=['{exe}','{root}/'+prefix+'/vectors.txt','profile'],
                expected_returncode=0,expected_stdout=normal_expected((root/(prefix+'/normal.log')).read_text(),aw),expected_stderr='')]
        else:steps=target_steps()
        output[role]=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='aethia',
            source_root=RUN_ROOT+'/snapshot-v1/fpga',output_parent=RUN_ROOT,sources=pins,
            build=dict(top=top,sv_sources=sv,cpp_source=bench,parameters=dict(AW=aw),cflags=['-std=c++17','-Werror=return-type']),
            probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),steps=steps)
    return output


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--emit-patch',action='store_true');args=parser.parse_args()
    items=manifests()
    if args.emit_patch:
        paths={ROOT/STAGE/(role+'-manifest.json'):json.dumps(body,indent=2)+'\n' for role,body in items.items()}
        if any(path.exists() for path in paths):raise ValueError('fresh manifest paths required')
        print('*** Begin Patch')
        for path,text in paths.items():
            print('*** Add File: '+str(path))
            for line in text.splitlines():print('+'+line)
        print('*** End Patch')
    else:print(json.dumps({role:dict(sources=len(m['sources']),steps=len(m['steps'])) for role,m in items.items()},indent=2))
