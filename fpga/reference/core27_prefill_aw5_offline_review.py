"""Independent archived AW5 T5 normal review. No project imports or execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

MANIFEST='5165293cc441dce05496b89a4cb725c00116ba46d78bf360a2b93dddc1db451d'
PARENT='1bc9950b438397ed2e1bcb230996b6f02d7a30d9d42d65f9d664857ed610bceb'


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def archive(path,expected):
    seen={}
    with tarfile.open(path,'r:gz') as tar:
        for member in tar:
            name=member.name
            need(member.isfile() and name not in seen and not Path(name).is_absolute() and '..' not in Path(name).parts,'unsafe/duplicate archive member')
            data=tar.extractfile(member).read();seen[name]=hashlib.sha256(data).hexdigest()
    need(seen==expected,'exact archive inventory/hash mismatch')
    return seen


def vector_oracle(text):
    tokens=iter(text.split());n=int(next(tokens));need(n==32,'AW5 vector length')
    value=None;base=None;rows=[];loads=0;aborts=0;readbacks=0
    def take(count):return [int(next(tokens)) for _ in range(count)]
    for command in tokens:
        if command in ('LOAD','LOAD_KEEP'):
            label=next(tokens);base=int(next(tokens));digits=take(n)
            need(all(d==-1 or 0<=d<base for d in digits),'canonical input digits')
            value=sum(d*base**i for i,d in enumerate(digits))%(base**n+1);loads+=1
        elif command in ('RUN','RUN_NOREAD'):
            label=next(tokens);bit=int(next(tokens));expected=take(n)
            need(value is not None and bit in (0,1),'loaded operation/double')
            modulus=base**n+1;value=value*value*(1<<bit)%modulus
            actual=sum(d*base**i for i,d in enumerate(expected))%modulus
            need(actual==value and (expected==[-1]+[0]*(n-1) or all(0<=d<base for d in expected)),'independent whole-integer oracle: '+label)
            readbacks+=command=='RUN';rows.append(dict(case=label,base=base,readback=int(command=='RUN')))
        elif command=='ABORT':next(tokens);next(tokens);aborts+=1;value=None
        elif command=='BADBASE':next(tokens);value=None
        elif command in ('BADDIGIT','BADDIGIT_AT'):
            next(tokens);next(tokens)
            if command=='BADDIGIT_AT':next(tokens)
            value=None
        else:raise ValueError('unknown normal vector command: '+command)
    need((len(rows),readbacks,aborts)==(568,561,20),'complete operation coverage')
    return rows,dict(operations=len(rows),readbacks=readbacks,aborts=aborts,loads=loads)


def review(directory,parent_path):
    directory=Path(directory);parent_path=Path(parent_path)
    need(sha(parent_path)==PARENT,'frozen parent report pin')
    parent=json.loads(parent_path.read_text());report=json.loads((directory/'report.json').read_text())
    need(report['status']=='passed_aw5_group_only' and report['group']=='normal' and report['aw']==5,'scoped successful normal status')
    need(report['manifest_sha256']==MANIFEST and sha(directory/'approved-manifest.json')==MANIFEST,'approved manifest identity')
    manifest=json.loads((directory/'approved-manifest.json').read_text())
    need(report['sources']==manifest['sources'] and len(report['sources'])==98,'closed approved98source pins')
    for name,digest in report['artifacts'].items():
        path=directory/name
        need(not path.is_symlink() and path.resolve().is_relative_to(directory.resolve()) and sha(path)==digest,'artifact pin: '+name)
    source_members=archive(directory/'sources.tar.gz',report['sources'])
    generated=archive(directory/'generated-sources.tar.gz',report['generated_source_sha256'])
    need(len(generated)==121,'generated source inventory')
    need(report['compiled']==manifest['compiled']['normal'] and len(report['compiled'])==17,'ordered normal17SVunits')
    vector_rows,coverage=vector_oracle((directory/'vectors.txt').read_text())
    need(sha(directory/'vectors.txt')==parent['vectors']['sha256']==report['vectors']['sha256'],'exact parent vectors')
    output=(directory/'normal.log').read_text();lines=output.splitlines()
    need(lines.count('PASS n=32 squares=568 readbacks=561 aborts=20')==1,'unique exact footer')
    need(not any(x in output for x in ('$fatal','%Error','T5_MONITOR_','mismatch')),'no runtime mismatch/fatal')
    parsed=[]
    for line in lines:
        if ' cycles=' not in line:continue
        label,*tokens=line.split();fields=[t.split('=',1) for t in tokens]
        need(all(len(x)==2 for x in fields) and len({x[0] for x in fields})==len(fields),'unique metric fields')
        parsed.append(dict(case=label,aw=5,n=32,**{k:int(v) for k,v in fields}))
    need(len(parsed)==len(parent['metrics'])==568 and parsed==report['metrics'],'parsed/archive/reported metric identity')
    deltas={};fast=0
    for row,old,vector in zip(parsed,parent['metrics'],vector_rows):
        need(row['case']==old['case']==vector['case'] and row['base']==vector['base'] and row['readback']==vector['readback'],'ordered oracle operation identity')
        need(row['prefill_before'] in (0,1) and row['prefill_after']==1,'image eligibility flags')
        before=row['prefill_before'];fast+=before
        for key,value in old.items():
            expected=0 if key=='conversion' and before else value+5-(old['conversion'] if before else 0) if key=='cycles' else value+5 if key=='carry' else value
            need(row[key]==expected,'matched counter: '+row['case']+'/'+key)
        need(row['cycles']==sum(row[k] for k in ('conversion','roots','ntt','crt','carry')),'independent phase sum')
        delta=row['cycles']-old['cycles'];deltas[str(delta)]=deltas.get(str(delta),0)+1
    need(set(deltas)=={'5','-3'},'cold+5/warm-3 deltas')
    probe=json.loads((directory/'probe.log').read_text())
    need(probe==dict(context_threads=1,model_threads=1,expected_threads=1),'exact runtime context probe')
    limits=report['limits'];quota,period=map(int,limits['cpu_max'])
    need(limits['affinity']==[0,2] and len({tuple(c) for c in limits['physical_cores']})==2 and limits['memory_max_bytes']<=6*(1<<30) and quota<=2*period,'recorded bounded resources')
    need(report['compile_workers']==2 and report['model_threads']==1,'worker/thread evidence')
    need([s['name'] for s in report['steps']]==['verilator-version','compiler-version','build','probe','normal'],'exact native step sequence')
    for step in report['steps']:
        need(step['returncode']==0 and step['error'] is None and sha(directory/step['log'])==step['sha256'],'native step status/hash')
    build=report['steps'][2]['command'];root=manifest['target']
    expected=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module','core27_prefill_probe_v3','-GAW=5','-GNTT_LANES=64','-CFLAGS','-std=c++17 -Werror=return-type -DCORE27_PREFETCH_R2_RUNTIME_THREADS=1','--Mdir',report['scratch']+'/build']+[root+'/'+name for name in report['compiled']]+[root+'/rtl/tb/core27_prefill_normal_v3_threaded.cpp']
    need(build==expected,'exact native build command closure')
    need(report['steps'][-1]['command'][1:] == [str(Path(report['steps'][-1]['command'][0]).parent/'vectors.txt'),'profile'],'exact normal invocation')
    return dict(status='PASS_independent_archived_AW5_normal_review_only',report_sha256=sha(directory/'report.json'),
        parent_report_sha256=PARENT,manifest_sha256=MANIFEST,artifacts_checked=len(report['artifacts']),
        source_members_checked=len(source_members),generated_members_checked=len(generated),coverage=coverage,
        operation_metrics_checked=len(parsed),fast_operations=fast,total_cycle_deltas=deltas,
        thread_probe=probe,limits=limits,
        evidence_class='native AW5 normal output comparator + source/artifact/vector/metric replay; NOT fullT5 qualification',
        next_admission='Separately scoped AW5 targeted gates after exact source review; noAW16/mutant/fit promotion implied',
        limitations=['No binary, HDL, compiler, native or cloud command executed by offline reviewer.',
            'Native tool hashes and cgroup/thread/resource reports are archived worker attestations, not Mac tool executable rehashes.',
            'Native frozen bench compared561 readbacks against independently replayed oracle vectors; raw per-word read values are not separately dumped in normal.log.',
            'Original failed enum-width stage preserved; successful successor does not erase failure.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path);parser.add_argument('parent',type=Path)
    args=parser.parse_args();print(json.dumps(review(args.directory,args.parent),indent=2))
