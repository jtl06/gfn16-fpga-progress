"""Independent G4 rootfused+CRT-Montgomery archive audit; no saved code runs.

AW5 ordinary-integer vectors are freshly checked. AW16 uses exact source-bound
previously verified parent vectors; no full-N arithmetic is rerun locally.
Candidate identities, sources, commands and metrics are never rewritten as an
ancestor. Reuses only pinned offline archive/source/integer-audit primitives.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shlex

ROOT_AUDITOR_SHA='c1a052c3b3c270729939f7c2969f2c26e51f8a9accd91c28fb99d458a31213a9'
NORMAL_SHA='63e4c7ba0fed1bb203956b5fd28f595dc2a4a957ba905f4160ad8e96961eea6f'
INTEGER_SHA='785100ed9ae507e04c086a893fd401db189a847cdbc9e428e6ee6f9ed5de9920'
MANIFEST_SHA='fc10698824eb675c490eefd06c517c1a00cdf58e952185532c0c3552dff8172d'
STAGE_ARCHIVE_SHA='c01b24ae4af3a34c684e0a4e4b0d900a95f47c2283ecaca33df4b221b2bb6922'
PARENT_METRICS_SHA='a7f17a28d57eeaa5cd17406ab7255b011e0bcdff49a7db57269558a9a14d151f'
G2_SHA='551d5365dbd8059a372c9bed26fc860b47191a72b596e4f911af862753c3902e'
PARENT_TOP='genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused'
TOP=PARENT_TOP+'_crtmont'
BENCH=TOP.removeprefix('genefer_')
RUNNER='reference/core27_prefetch_r2_rootfused_crtmont_regression.py'
RUNNER_SHA='95898756fd1c8c547343341428836379e90400644659635bd7dc77010107b208'
SNAPSHOT='/home/jtl/gfn-fpga-lab/agent-work/core27-prefetch-r2-rootfused-crtmont/snapshot-v1/fpga'
FLAGS=['-std=c++17','-Werror=return-type','-DCORE27_PREFETCH_R2_RUNTIME_THREADS=1']
EXTRA_PINS={
 'reference/core27_prefetch_r2_rootfused_crtmont_structure.py':'2a0fa601d3b5cf209707863962e74895cd419146b4ebf79c399e3c768258e3f7',
 'rtl/kernel/genefer_crt3_27_mont_pipe.sv':'8bb5b62423c1f61e069f131b5d393dd3dbc84d05348fc1945f6e9c419c104c58',
 'rtl/kernel/'+TOP+'.sv':'b6dbd4fccc6d7708fd295d3c82e2ebec444c4a2fbde8612851f10f979da04895',
 'rtl/tb/'+BENCH+'.cpp':'5680df12450b1c301361b23264f3a56a386e5e8dbecd5ca7ad1324ecd1dcd526',
 'rtl/tb/'+BENCH+'_threaded.cpp':'2667f3662c90d931372d8f946deee2d54d898be61bae5bee8c2361fb84dc022e',
 'docs/briefs/2026-09-30-answers-B20260930-r3.md':'39acc1d9537aff429f00ce2c23161be2df9553eecb0fba03b7c7907ba6a367ee',
 RUNNER:RUNNER_SHA,
}
VECTOR_SHA={5:'a5b46cb2f52ce817bed3de90a91dfc6fb038b30215edc7d861514d1106919edd',16:'3449c1e3e1d7c0820842ecb30295b963b4aa81af6b27be8e38b7c87f2bd39f3d'}
PARENT_REPORT_SHA={5:'82a99f555fa8f0a7836f616b5b8c0be5b1e78fa339171571492fda87edcff786',16:'7447dbe4813e1e6b45c5c5071da5019c7aa4ee0b47e0a8a923f75852fd01468a'}


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def map_sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def helpers():
    directory=Path(__file__).resolve().parent
    require(sha(directory/'verify_core27_rootfused_offline.py')==ROOT_AUDITOR_SHA,'frozen rootfused auditor identity')
    require(sha(directory/'verify_core27_prefetch_r2_offline.py')==NORMAL_SHA and sha(directory/'verify_square_core27_rootpipe_offline.py')==INTEGER_SHA,'independent oracle identity')
    from . import verify_core27_rootfused_offline as parent
    require(Path(parent.__file__).resolve()==directory/'verify_core27_rootfused_offline.py','offline helper path')
    return parent,parent.normal_helpers()


def source_contract(pins,parent,normal):
    require(len(pins)==65 and all(pins.get(k)==v for k,v in EXTRA_PINS.items()),'exact65source G4 closure')
    frozen={k:v for k,v in pins.items() if k not in EXTRA_PINS}
    order=parent.source_contract(frozen,normal)
    return [x.replace(PARENT_TOP,TOP).replace('/genefer_crt3_27_pipe.sv','/genefer_crt3_27_mont_pipe.sv') for x in order]


def source_delta(members,parent):
    parent.source_delta(members)
    def text(name):return members[name].decode()
    def once(s,old,new,count=1):
        require(s.count(old)==count,'unique G4 transformation anchor');return s.replace(old,new)
    original=text('rtl/kernel/'+PARENT_TOP+'.sv')
    wanted=once(original,'module '+PARENT_TOP+' #(','module '+TOP+' #(')
    wanted=once(wanted,'genefer_crt3_27_pipe crt (','genefer_crt3_27_mont_pipe crt (')
    require(text('rtl/kernel/'+TOP+'.sv')==wanted,'exact CRT-only core delta')
    oldbench=PARENT_TOP.removeprefix('genefer_');wanted=text('rtl/tb/'+oldbench+'.cpp')
    for old,new,count in [('V'+PARENT_TOP,'V'+TOP,2),('frozen61-stage CRT, first coefficient acceptance','candidate16-stage CRT, first coefficient acceptance',1),('is RESIDUES clock63;','is RESIDUES clock18;',1),('d.crt_cycles>=63','d.crt_cycles>=18',1),('(n+15)/16+62+','(n+15)/16+17+',1)]:wanted=once(wanted,old,new,count)
    require(text('rtl/tb/'+BENCH+'.cpp')==wanted,'exact G4 bench delta')
    wanted=once(text('rtl/tb/'+oldbench+'_threaded.cpp'),'V'+PARENT_TOP,'V'+TOP)
    wanted=once(wanted,'#include "'+oldbench+'.cpp"','#include "'+BENCH+'.cpp"')
    require(text('rtl/tb/'+BENCH+'_threaded.cpp')==wanted,'exact G4 context wrapper delta')


def audit_vectors(raw,log,aw,normal):
    FIELDS=normal.FIELDS;ABORTS=normal.ABORTS;schedule=normal.schedule;radix_integer=normal.radix_integer
    require(type(aw) is int and aw in (5,16),'AW profile')
    lines=raw.splitlines();n=1<<aw
    require(lines and lines[0]==str(n) and all(lines),'vector header/blank line')
    pattern=re.compile(r'^(\S+) '+' '.join(k+r'=(\d+)' for k in FIELDS)+'$')
    metrics=[];footers=[]
    for line in log.splitlines():
        if not line.strip():continue
        match=pattern.fullmatch(line)
        if match:
            row=dict(zip(FIELDS,map(int,match.groups()[1:])),case=match[1],aw=aw,n=n)
            metrics.append(row)
        else:
            require(re.fullmatch(r'PASS n=\d+ squares=\d+ readbacks=\d+ aborts=\d+',line),'unexpected/malformed runtime log')
            footers.append(line)
    i=1;j=0;cache=0;x=None;base=None;modulus=None;pending_readback=False
    names=set();commands=Counter();aborts=[];cold=warm=0;bases=set();invalid_at=[];runs=[]
    ntt,seed_setup=schedule(aw);words=(2*aw+2)*257
    def canonical(digits,output=False):
        return digits==[-1]+[0]*(n-1) or all((0 if output else -1)<=d<base for d in digits)
    while i<len(lines):
        tokens=lines[i].split();i+=1;cmd=tokens[0];commands[cmd]+=1
        if cmd in ('LOAD','LOAD_KEEP'):
            require(len(tokens)==3 and not pending_readback,'load syntax/unobserved NOREAD chain')
            base=int(tokens[2]);require(2*n+4<base<=1000000000,'loaded base domain')
            require(i<len(lines),'truncated load');digits=list(map(int,lines[i].split()));i+=1
            require(len(digits)==n and canonical(digits),'load digit width/domain')
            modulus=pow(base,n)+1 if aw==5 else None;x=radix_integer(digits,base)%modulus if aw==5 else 0;bases.add(base)
            if cmd=='LOAD':cache=0
        elif cmd in ('RUN','RUN_NOREAD'):
            require(len(tokens)==3,'run syntax');name=tokens[1];bit=int(tokens[2])
            require(name not in names and bit in (0,1),'case/bit identity');names.add(name)
            require(x is not None and i<len(lines),'run without live input/truncated expected')
            expected=list(map(int,lines[i].split()));i+=1
            require(len(expected)==n and canonical(expected,True),'noncanonical expected digits')
            if aw==5:
                x=(x*x*(1<<bit))%modulus
                require(radix_integer(expected,base)%modulus==x,'independent integer oracle: '+name)
            require(j<len(metrics),'missing raw metric');row=metrics[j];j+=1
            require((row['case'],row['base'],row['profile_before'])==(name,base,cache),'transaction/cache order')
            require(row['readback']==int(cmd=='RUN'),'readback coverage')
            require(row['cycles']==sum(row[k] for k in ('conversion','roots','ntt','crt','carry')),'phase accounting')
            require(row['conversion']==(n+15)//16+6,'fusion conversion count')
            require((row['ntt'],row['seed_setup'])==(ntt,seed_setup),'NTT/seed schedule')
            require((row['profile_loads'],row['profile_hits'],row['profile_words'],row['roots'])==
                    ((0,1,0,0) if cache else (1,0,words,words+5)),'profile accounting')
            require(row['crt']==(n+15)//16+17+max(0,97-row['roots']-ntt),'CRT/reservation count')
            require(row['carry']==(n+15)//16+51 and row['passes']==2,'carry tail/passes')
            warm+=cache;cold+=1-cache;cache=1;pending_readback=cmd=='RUN_NOREAD'
            runs.append({'case':name,'base':base,'bit':bit,'residue':x})
        elif cmd=='ABORT':
            require(len(tokens)==3 and tokens[1] in ABORTS and int(tokens[2]) in (0,1) and x is not None and not pending_readback,'abort contract')
            require(tokens[1]!='crt-active' or n>=32,'crt-active size')
            aborts.append(tokens[1]);cache=0;x=None
        elif cmd=='BADBASE':
            require(len(tokens)==2 and not pending_readback,'BADBASE syntax')
            bad=int(tokens[1]);require(not 2*n+4<bad<=1000000000,'BADBASE is legal')
            cache=0;x=None
        elif cmd in ('BADDIGIT','BADDIGIT_AT'):
            require(len(tokens)==(4 if cmd=='BADDIGIT_AT' else 3) and not pending_readback,'BADDIGIT syntax')
            b=int(tokens[1]);bad=int(tokens[2]);at=int(tokens[3]) if cmd=='BADDIGIT_AT' else n//2
            require(2*n+4<b<=1000000000 and 0<=at<n and (bad < -1 or bad>=b),'invalid-digit case not invalid')
            if cmd=='BADDIGIT_AT':invalid_at.append((b,bad,at))
            cache=0;x=None
        else:raise ValueError('unexpected vector command: '+cmd)
    require(not pending_readback,'unobserved terminal NOREAD chain')
    require(j==len(metrics),'extra raw metrics')
    footer=f'PASS n={n} squares={j} readbacks={commands["RUN"]} aborts={commands["ABORT"]}'
    require(footers==[footer] and log.rstrip().endswith(footer),'terminal coverage footer')
    return metrics,dict(commands=dict(commands),abort_labels=aborts,cold_runs=cold,warm_runs=warm,
                        bases=sorted(bases),invalid_at=invalid_at,runs=runs)


def vector_coverage(root,report,steps,remote,normal,parent_metrics):
    """Native segment/coverage checks plus independently recomputed squareDup."""
    aw=report['aw'];n=1<<aw;name=f'vectors-aw{aw}.txt'
    raw=normal.local_file(root,name).read_bytes();lines=raw.splitlines(keepends=True)
    require(normal.digest(raw)==report['vectors']['sha256']==VECTOR_SHA[aw],'complete identical frozen vector suite')
    parts=report['segments'];require(parts and [p['index'] for p in parts]==list(range(len(parts))),'segment index coverage')
    require(len(parts)==(2 if aw==16 else 1),'exact frozen profile segmentation')
    rebuilt=lines[0];next_start=1;all_metrics=[];totals=Counter();aborts=[];invalid=[];runs=[];cold=warm=0;bases=set()
    for part in parts:
        index,start,end=part['index'],part['start'],part['end'];segment=f'segment{index}.txt'
        require(type(start) is int and type(end) is int and start==next_start and start<end<=len(lines),'contiguous segment partition')
        payload=normal.local_file(root,segment).read_bytes()
        require(normal.digest(payload)==part['sha256'] and payload==lines[0]+b''.join(lines[start:end]),'exact segment bytes/hash')
        if index:require(lines[start].startswith(b'LOAD '),'cannot split live LOAD_KEEP/NO_READ chain')
        rebuilt+=b''.join(lines[start:end]);next_start=end
        step=f'test-segment{index}'
        require(step in steps and steps[step]['command']==[str(remote),str(remote.parent/segment),'profile'],'candidate segment command')
        rows,coverage=audit_vectors(payload.decode(),normal.local_file(root,steps[step]['log']).read_text(),aw,normal)
        all_metrics+=rows;totals.update(coverage['commands']);aborts+=coverage['abort_labels'];invalid+=coverage['invalid_at'];runs+=coverage['runs']
        cold+=coverage['cold_runs'];warm+=coverage['warm_runs'];bases.update(coverage['bases'])
    require(rebuilt==raw and next_start==len(lines),'segment omission/duplication')
    require(len({r['case'] for r in all_metrics})==len(all_metrics),'duplicate case across segments')
    require(all_metrics==report['metrics'],'candidate raw/report metrics')
    expected=[dict(row,cycles=row['cycles']-45,crt=row['crt']-45) for row in parent_metrics]
    require(all_metrics==expected,'exact frozen parent metrics except CRT and total minus45')
    info=report['vectors'];require(info['seed']==20260929 and len(all_metrics)==info['squares'] and totals['RUN']==info['readbacks'],'reported seed/coverage')
    require((len(all_metrics),totals['RUN'],len(aborts))=={1:(529,522,9),5:(568,561,20),7:(12,10,0),16:(12,10,0)}[aw],'complete normal operation/readback/abort coverage')
    last=[(b,b,i) for b in (2*n+5,1000000000) for i in sorted({max(0,n-16),n-1})]
    require(info['fusion_invalid_final_row_cases']==4 and invalid[-4:]==last,'four final-row canonical-boundary errors')
    if aw in (1,5):require({'conversion','root','ntt','crt','carry','root0','root1','root2','root3'}<=set(aborts),'reset-phase coverage')
    if aw==5:
        require(all(aborts.count(x)==2 for x in ('convert-m1','convert-0','convert-p1')) and aborts.count('crt-active')==1,'conversion/carry active boundaries')
        require(all(aborts.count('profile-'+x)==1 for x in ('lastavailable','consumed','commit','check')),'profile boundary resets')
    require([c['base'] for c in info['fermat_chains']]==([2*n+6,2*n+7] if aw in (1,5) else []),'small Fermat chain cases')
    for chain in info['fermat_chains']:
        b=chain['base'];exponent=pow(b,n);selected=[r for r in runs if r['case'].startswith(f'fermat-b{b}-s')]
        require([r['bit'] for r in selected]==list(map(int,bin(exponent)[2:])) and len(selected)==chain['steps'],'Fermat exponent sequence')
        require(selected and selected[-1]['residue']==int(chain['residue_hex'],16)==pow(2,exponent,exponent+1),'independent Fermat integer result')
    if aw==16:require({r['cycles'] for r in all_metrics}=={32920,41663},'R2 full-N warm/cold cycle identity')
    return dict(operations=len(all_metrics),readbacks=totals['RUN'],no_readback_operations=totals['RUN_NOREAD'],
        cold_runs=cold,warm_runs=warm,abort_labels=aborts,bases=sorted(bases),segments=len(parts),
        final_row_invalid_cases=4,baseline_report_sha256=PARENT_REPORT_SHA[aw],baseline_metrics_sha256=map_sha(parent_metrics))


def metadata(report,manifest,manifest_sha,order):
    require(report.get('status')=='passed' and 'error' not in report,'failed/incomplete profile')
    require(report['top']==TOP and report['scope']=='Single-profile rootfused plus Montgomery CRT whole-core normal gate, exact parent-minus45 clocks','candidate top/scope')
    aw=report['aw'];require(type(aw) is int and aw in (5,16),'explicit AW profile')
    require(manifest['status']=='prepared_not_executed' and manifest['sources']==report['sources'] and
        manifest['target']==str(PurePosixPath(SNAPSHOT).parent) and manifest['top']==TOP and
        manifest['supported_aw']==[5,16] and re.fullmatch('[0-9a-f]{64}',manifest['archive_sha256']),'approved native snapshot')
    require(report['manifest_sha256']==manifest_sha and report['compiled_source_order']==order,'manifest/compiled closure binding')
    for name,wanted in {'n':1<<aw,'ntt_lanes':64,'model_threads':1,'compile_workers':2,
        'scratch_reservation_bytes':768<<20,'scratch_free_floor_bytes':2<<30,'durable_reservation_bytes':64<<20,
        'durable_free_floor_bytes':10<<30,'host_memory_floor_bytes':4<<30,
        'command_timeout_seconds':1800,'lock_wait_timeout_seconds':1800}.items():
        require(type(report[name]) is int and report[name]==wanted,'geometry/resource contract: '+name)
    limits=report['limits'];cpu=limits['cpu_max']
    require(limits['affinity']==[0,2] and 0<int(limits['memory_max_bytes'])<=6<<30 and len(cpu)==2 and
        0<int(cpu[0])<=2*int(cpu[1]) and int(cpu[1])>0 and len(limits['physical_cores'])==2 and
        len({tuple(x) for x in limits['physical_cores']})==2,'CPU/memory execution contract')
    names=['verilator-version','compiler-version','build','probe']+['test-segment'+str(i) for i in range(2 if aw==16 else 1)]
    require([s['name'] for s in report['steps']]==names,'exact stage order/coverage')
    for step in report['steps']:
        require(type(step['returncode']) is int and step['returncode']==0 and step['error'] is None,'unsuccessful command')
        require(type(step['seconds']) in (int,float) and math.isfinite(step['seconds']) and 0<=step['seconds']<=1801,'bounded duration')
    tools=report['tool_executable_sha256']
    require(len(tools)==5 and all(Path(p).is_absolute() and '..' not in Path(p).parts and
        re.fullmatch('[0-9a-f]{64}',h) for p,h in tools.items()),'recorded tool identities')
    require(isinstance(report['python_version'],str) and report['python_version'],'recorded Python version')
    scratch=PurePosixPath(report['scratch'])
    require(scratch.parent==PurePosixPath('/dev/shm') and scratch.name.startswith('gfn16-prefetch-r2-host-broadcast-crtmont-') and
            '..' not in scratch.parts and report['compiler_temporary_directory']==str(scratch/'tmp'),'isolated scratch identity')
    return {s['name']:s for s in report['steps']}


def commands(report,steps,order):
    scratch=report['scratch'];aw=report['aw']
    expected=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
        f'-GAW={aw}','-GNTT_LANES=64','-CFLAGS',' '.join(FLAGS),'--Mdir',scratch+'/build',
        *[SNAPSHOT+'/'+name for name in order],SNAPSHOT+'/rtl/tb/'+BENCH+'_threaded.cpp']
    require(steps['build']['command']==expected,'native candidate compiler argv')
    require(steps['verilator-version']['command']==['verilator','--version'] and
            steps['compiler-version']['command']==['g++','--version'],'tool-version argv')
    remote=PurePosixPath(report['executable'])
    require(remote.is_absolute() and '..' not in remote.parts and remote.name=='V'+TOP and
        remote.parent.parent==PurePosixPath(SNAPSHOT).parent.parent,'durable candidate executable path')
    require(steps['probe']['command']==[str(remote),'--runtime-probe'],'candidate probe command')
    return remote


def generated_contract(generated,log):
    top='V'+TOP
    require(all(top+x in generated for x in ('.cpp','.h','.mk')),'generated new-top closure')
    require(all('/' not in name and Path(name).suffix in ('.cpp','.h','.mk','.dat') for name in generated),'generated member types')
    require(re.search(r'unsigned\s+'+top+r'::threads\(\) const\s*\{\s*return 1;\s*\}',generated[top+'.cpp'].decode()),'generated model thread count')
    make=generated[top+'.mk'].decode();source=SNAPSHOT+'/rtl/tb/'+BENCH+'_threaded.cpp'
    require(source in make,'generated bench source rule')
    match=re.search(r'^VM_USER_CFLAGS = \\\n(.*?)(?=\n#|\Z)',make,re.M|re.S)
    require(match is not None and shlex.split(match[1].replace('\\\n',' '))==FLAGS,'exact generated compiler flags')
    rows=[shlex.split(line) for line in log.splitlines() if source in line and ' -c ' in line]
    require(len(rows)==1 and source in rows[0],'actual new-bench compilation evidence')
    require(all(rows[0].count(flag)==1 for flag in FLAGS),'actual compiler flag omission/duplication')
    require([t for t in rows[0] if t.startswith(('-DCORE27_PREFETCH_R2_RUNTIME_THREADS','-UCORE27_PREFETCH_R2_RUNTIME_THREADS'))]==[FLAGS[2]],'unexpected runtime-thread override')
    require([t for t in rows[0] if 'return-type' in t]==[FLAGS[1]],'return-type warning guard override')


def verify(root,approved_manifest_sha=MANIFEST_SHA):
    root=Path(root).resolve();parent,normal=helpers()
    manifest_path=normal.local_file(root,'approved-manifest.json')
    require(approved_manifest_sha==MANIFEST_SHA==sha(manifest_path),'externally approved frozen G4 manifest')
    manifest=json.loads(manifest_path.read_text());report=json.loads(normal.local_file(root,'report.json').read_text())
    order=source_contract(report['sources'],parent,normal)
    steps=metadata(report,manifest,approved_manifest_sha,order);remote=commands(report,steps,order);aw=report['aw']
    require(manifest['archive_sha256']==STAGE_ARCHIVE_SHA and
            manifest['compiled_source_order']==[PurePosixPath(n).name for n in order] and
            manifest['g2_sha256']==report['g2_sha256']==G2_SHA and
            manifest['parent_metrics_sha256']==PARENT_METRICS_SHA,'stage prerequisite/order binding')
    require(report['parent_report_sha256']==PARENT_REPORT_SHA[aw],'exact native rootfused parent report')
    delta=report['matched_cycle_delta']
    require(delta==dict(crt=-45,cycles=-45,all_other_fields_identical=True) and
            type(delta['crt']) is int and type(delta['cycles']) is int and delta['all_other_fields_identical'] is True,
            'declared exact cycle delta')
    artifacts=report['artifacts'];count=2 if aw==16 else 1
    wanted={'approved-manifest.json','sources.tar.gz','generated-sources.tar.gz','V'+TOP,f'vectors-aw{aw}.txt',
            'parent-metrics.json','g2-report.json',*[name+'.log' for name in steps],*[f'segment{i}.txt' for i in range(count)]}
    require(set(artifacts)==wanted,'exact native artifact roles')
    for name,value in artifacts.items():
        require(isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) and
                sha(normal.local_file(root,name))==value,'artifact hash: '+name)
    # Review attachments are inert and not native inputs; arbitrary extras are rejected.
    extras={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}-wanted-{'report.json'}
    require(all(re.fullmatch(r'(?:parent-review|independent-review|verification)(?:-[a-z0-9]+)*\.json',x) for x in extras),
            'unexpected unindexed archive content')
    for name,step in steps.items():require(step['log']==name+'.log' and artifacts[step['log']]==step['sha256'],'step log binding')
    members=normal.archive_members(normal.local_file(root,'sources.tar.gz'),report['sources']);source_delta(members,parent)
    generated=normal.archive_members(normal.local_file(root,'generated-sources.tar.gz'),report['generated_source_sha256'])
    generated_contract(generated,(root/'build.log').read_text())
    require(sha(root/('V'+TOP))==report['executable_sha256'],'candidate executable identity')
    for step,key in (('verilator-version','tool_version'),('compiler-version','compiler_version')):
        require(report[key] and report[key]==(root/(step+'.log')).read_text().strip(),'tool version record')
    probe=json.loads((root/'probe.log').read_text())
    require(probe=={'context_threads':1,'model_threads':1,'expected_threads':1} and
            all(type(x) is int for x in probe.values()),'actual runtime model/context probe')
    require(sha(root/'parent-metrics.json')==PARENT_METRICS_SHA and sha(root/'g2-report.json')==G2_SHA,
            'pinned parent metrics and qualified component receipt')
    parents=json.loads((root/'parent-metrics.json').read_text());g2=json.loads((root/'g2-report.json').read_text())
    require(set(parents)=={'5','16'} and parents[str(aw)]['report_sha256']==PARENT_REPORT_SHA[aw] and
            parents[str(aw)]['vectors']==report['vectors'],'exact already-verified parent vector metadata')
    require(g2['status']=='passed_required_mutations_and_fresh_controls' and
            g2['sources']['rtl/kernel/genefer_crt3_27_mont_pipe.sv']==EXTRA_PINS['rtl/kernel/genefer_crt3_27_mont_pipe.sv'] and
            g2['profile']['candidate_delay']==15 and g2['profile']['frozen_delay']==60,'qualified component identity/latency')
    require(report['tool_executable_sha256']==g2['tool_executable_sha256'],'recorded G2/G4 toolchain identity')
    coverage=vector_coverage(root,report,steps,remote,normal,parents[str(aw)]['metrics'])
    return dict(status='verified_g4_normal_profile',scope='Rootfused plus CRT-Montgomery whole-core native normal gate',
        aw=aw,n=1<<aw,**coverage,artifacts=len(artifacts),source_members=len(members),compiled_kernels=16,
        generated_members=len(generated),matched_cycle_delta=dict(crt=-45,cycles=-45,all_other_fields_identical=True),
        candidate_edge_delay=15,frozen_edge_delay=60,report_sha256=sha(root/'report.json'),manifest_sha256=MANIFEST_SHA,
        runner_sha256=RUNNER_SHA,verifier_sha256=sha(__file__),parent_auditor_sha256=ROOT_AUDITOR_SHA,
        integer_audit_sha256=NORMAL_SHA,radix_helper_sha256=INTEGER_SHA,g2_report_sha256=G2_SHA,
        parent_metrics_sha256=PARENT_METRICS_SHA,vector_sha256=VECTOR_SHA[aw],
        source_archive_sha256=sha(root/'sources.tar.gz'),executable_sha256=report['executable_sha256'],
        vector_oracle='fresh ordinary-integer arithmetic AW5' if aw==5 else 'exact previously verified source-bound full-N parent vector bytes; no local full-N arithmetic',
        limitations=[
            'Native candidate identities and metrics checked directly, never rewritten to impersonate an ancestor.',
            'No executable, candidate generator, RTL simulator, remote tool or full-N arithmetic is run by this audit.',
            'AW5 uses only16butterflies, not all64lanes; fullAW16 needed. Each receipt qualifies only its named normal AW profile.',
            'NOREAD intermediate states are observed only through later readback; not formal proof or exhaustive reset/mutation coverage.',
            'Archived tool hashes/generated code/build logs provide evidence consistency, not fresh remote tool rehash or compiler execution attestation.',
            'No fit, candidate clock/resource saving, board, full PRP or physical qualification.'
        ])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path)
    parser.add_argument('--manifest-sha',required=True);args=parser.parse_args()
    print(json.dumps(verify(args.root,args.manifest_sha),indent=2))
