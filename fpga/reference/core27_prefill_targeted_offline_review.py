"""Independent archived AW5 targeted T5 replay; stdlib only, no binary runs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import tarfile

REPORT='a790b2a3ac60d4e0f2785a2113fc39cdbd6f391aa26ee46199d895df5a4da9f2'
MANIFEST='aa21028dfd7110fe4b103eee8c3a29b57c4e79eba3ea0e090bee289a717bf23a'
NORMAL='a94f431c20319cba713df4d9e845fbd36bea237d82d355a353aff7f523ec5f5d'
VECTOR='1080d4454da030795060b347cf1dd7f06cebae4c2451272cd6fecc01378d3603'


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(path,expected):
    seen={}
    with tarfile.open(path,'r:gz') as tar:
        for member in tar:
            name=member.name
            need(member.isfile() and name not in seen and not Path(name).is_absolute() and '..' not in Path(name).parts,'safe unique regular archive members')
            seen[name]=hashlib.sha256(tar.extractfile(member).read()).hexdigest()
    need(seen==expected,'exact member/hash inventory')
    return len(seen)


def review(directory):
    directory=Path(directory);need(sha(directory/'report.json')==REPORT,'exact targeted native report pin')
    d=json.loads((directory/'report.json').read_text())
    need(d['status']=='passed_aw5_targeted_controls_only' and d['mode']=='targeted-controls' and d['mutation'] is None and (d['aw'],d['n'])==(5,32),'scoped positive suite')
    need(d['manifest_sha256']==MANIFEST and sha(directory/'approved-manifest.json')==MANIFEST,'exact approved manifest')
    m=json.loads((directory/'approved-manifest.json').read_text());need(m['sources']==d['sources'],'approved source closure')
    need(d['prerequisite_normal_sha256']==NORMAL and sha(directory/'prerequisite-normal-report.json')==NORMAL,'normal prerequisite pin')
    for name,value in d['artifacts'].items():
        path=directory/name
        need(not path.is_symlink() and path.resolve().is_relative_to(directory.resolve()) and sha(path)==value,'artifact pin: '+name)
    sources=inventory(directory/'sources.tar.gz',d['sources']);need(sources==104,'104source members')
    need(set(d['builds'])=={'targeted-controls'},'one original-source control build')
    b=d['builds']['targeted-controls'];generated=inventory(directory/b['generated_archive'],b['generated_source_sha256'])
    for name,value in b['derived_sources'].items():
        need(value==d['sources'][name] and sha(directory/'derived-targeted-controls'/name)==value,'unmodified original source overlay')
    identity=b['executable_archive_identity'];exe=directory/b['executable_archive']
    need(sha(exe)==identity['compressed_sha256'] and exe.stat().st_size==identity['compressed_bytes'],'compressed executable provenance')
    with gzip.open(exe,'rb') as stream:data=stream.read()
    need(hashlib.sha256(data).hexdigest()==identity['uncompressed_sha256']==b['executable_sha256'] and len(data)==identity['uncompressed_bytes'],'decompressed exact model identity')
    vector=(directory/'vectors.txt').read_text();need(sha(directory/'vectors.txt')==VECTOR,'fixed target vector')
    values=list(map(int,vector.split()));n,a,radix=values[:3];need((n,a,radix)==(32,604832956,10**9) and len(values)==131,'exact vector geometry')
    rows=[values[3+i*n:3+(i+1)*n] for i in range(4)]
    for original,expected,base,bit in ((rows[0],rows[1],a,0),(rows[1],rows[2],radix,0),(rows[2],rows[3],radix,1)):
        x=sum(c*base**i for i,c in enumerate(original));y=x*x*(1<<bit)%(base**n+1)
        need(sum(c*base**i for i,c in enumerate(expected))%(base**n+1)==y and all(0<=c<base for c in expected),'direct whole-integer targeted oracle')
    groups=[('reset-tail','--tail-reset',[(i,'final') for i in range(7)]),
        ('reset-emission','--tail-reset',[(0,'first'),(0,'middle')]),
        ('host-error-tail','--tail-error',[(i,'final') for i in range(7)]),
        ('host-error-emission','--tail-error',[(0,'first'),(0,'middle')]),
        ('carry-error-tail','--tail-carry-error',[(i,'final') for i in range(7)]),
        ('base-change',None,[(0,'--changed-base'),(0,'--base-reject')]),
        ('reload-control',None,[(0,'--reload-control')])]
    need([g['name'] for g in d['groups']]==[x[0] for x in groups],'complete ordered seven groups')
    expected_names=[];coverage=[]
    for actual,(group,mode,cases) in zip(d['groups'],groups):
        need(len(actual['cases'])==len(cases),'exact group case count')
        for recorded,(age,row) in zip(actual['cases'],cases):
            simple=mode is None;name=row[2:] if simple else f'{group}-{row}-e{age}'
            argv=[b['executable'],row,str(Path(d['steps'][4]['command'][2])),'control'] if simple else [b['executable'],mode,str(Path(d['steps'][4]['command'][2])),str(age),row,'control']
            # The first native case's vector path is argument2; every case must
            # bind to that exact same preserved vectors.txt location.
            need(recorded['name']==name and recorded['command']==argv,'command-bound case')
            step=next(s for s in d['steps'] if s['name']==name)
            need(step['command']==argv,'recorded command/step identity')
            output=(directory/step['log']).read_text();lines=re.findall(r'^T5_TARGET_PASS (.*)$',output,re.M)
            need(len(lines)==1 and not any(x in output for x in ('%Fatal','%Error','Assertion failed')),'one positive footer/no fatal')
            fields=[x.split('=',1) for x in lines[0].split()]
            need(all(len(x)==2 for x in fields) and len({x[0] for x in fields})==len(fields),'unique target fields')
            counts=(3,3,0) if row=='--changed-base' else (2,2,1) if row=='--base-reject' else (2,2,0) if row=='--reload-control' else (1,1,1)
            expected=dict(mode=row if simple else mode,age='0' if simple else str(age),row='none' if simple else row,
                row_index='0' if row=='first' else '1',middle_aliases_final='1',event_hits='1',
                successful=str(counts[0]),readbacks=str(counts[1]),recoveries=str(counts[2]))
            need(dict(fields)==expected==recorded['footer'],'independent mode/age/row/count footer')
            expected_names.append(name);coverage.append(expected)
    need(len(expected_names)==len(set(expected_names))==28,'28unique positive cases')
    need([s['name'] for s in d['steps']]==['verilator-version','compiler-version','build-targeted-controls','probe-targeted-controls']+expected_names,'exact32native steps')
    for s in d['steps']:need(s['returncode']==0 and s['error'] is None and sha(directory/s['log'])==s['sha256'],'step status/log pin')
    probe=json.loads((directory/'probe-targeted-controls.log').read_text());need(probe==dict(context_threads=1,model_threads=1,expected_threads=1),'runtime model context')
    build=d['steps'][2]['command']
    expected_build=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module','core27_prefill_tail_probe_v3','-GAW=5','-GNTT_LANES=64','-CFLAGS','-std=c++17 -Werror=return-type','--Mdir',b['fresh_build_directory']]+b['compiled_source_order']+[m['target']+'/rtl/tb/core27_prefill_adversarial_v1.cpp']
    need(build==expected_build,'exact native build argv')
    overlay=str(Path(d['steps'][4]['command'][2]).parent/'derived-targeted-controls')
    need(b['compiled_source_order']==[overlay+'/'+name if name in b['derived_sources'] else m['target']+'/'+name for name in m['compiled']],'ordered18-source compile provenance')
    quota,period=map(int,d['limits']['cpu_max'])
    need(d['limits']['affinity']==[0,2] and len({tuple(x) for x in d['limits']['physical_cores']})==2 and d['limits']['memory_max_bytes']<=6*(1<<30) and quota<=2*period,'recorded cgroup/core guard')
    need(d['durable_reservation_bytes']==32*(1<<20) and d['scratch_reservation_bytes']==768*(1<<20) and d['model_threads']==1,'reservation/context policy')
    return dict(status='PASS_independent_AW5_targeted_positive_archive_review',report_sha256=REPORT,
        manifest_sha256=MANIFEST,artifacts_checked=len(d['artifacts']),source_members=sources,generated_members=generated,
        compressed_and_uncompressed_model_hashes_verified=True,independent_integer_oracle_cases=3,
        positive_commands=28,groups=7,source_derived_observer_events=True,
        coverage=coverage,mutation_pair_admission='GO one fresh control/mutant pair per separately reviewed invocation; defer until CPU0/2 free and32MiB+10GiB preflight passes',
        limitation='AW5 middle aliases final; no distinct interior AW16 reset qualification, mutation results, fit, clock, board or fullPRP claim. Reviewer did not execute binaries/HDL/native/cloud.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    print(json.dumps(review(p.parse_args().directory),indent=2))
