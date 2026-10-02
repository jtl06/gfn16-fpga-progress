"""Frozen positive G2 stage: direct CRT oracle and unequal-latency native pair.

This early stage is deliberately partial: required mutation negatives run in
a separately named, source-pinned successor. No positive-only result is G2
qualification. Local preparation executes ordinary Python, never HDL.
"""
import argparse
from collections import Counter,deque
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import re
import resource
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time

TOP='crt3_27_mont_pair'
RUNNER='reference/crt27_mont_regression.py'
SOURCE=Path('/home/jtl/gfn-fpga-lab/agent-work/crt27-mont/snapshot-v1/fpga')
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
GiB=1<<30;MiB=1<<20
PRIMES=(104857601,69206017,67239937);M=487945222748036195811329;HALF=M//2
PROFILE=dict(candidate_delay=15,candidate_stages=16,frozen_delay=60,frozen_stages=61,coefficient_bits=96,random_cases=1000000,seed=20260930)
ORDER=('rtl/kernel/genefer_mod64_pipe.sv','rtl/kernel/genefer_crt3_27_pipe.sv',
       'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv','rtl/kernel/genefer_crt3_27_mont_pipe.sv',
       'rtl/tb/'+TOP+'.sv','rtl/tb/'+TOP+'.cpp')
FIXED_PINS={
 'rtl/kernel/genefer_mod64_pipe.sv':'e582dba87dce51794a38039fd02574f443c53750bcafc8fcb1f4d0d50fc60839',
 'rtl/kernel/genefer_crt3_27_pipe.sv':'279c6c8c3185eeaaa505283f858fd04904c6daccd30720f6b3bf78e14a6fa160',
 'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv':'501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b',
 'rtl/kernel/genefer_crt3_27_mont_pipe.sv':'8bb5b62423c1f61e069f131b5d393dd3dbc84d05348fc1945f6e9c419c104c58',
 'rtl/tb/crt3_27_mont_pair.sv':'a449b4c4474a582207580db9e4ebc983aadc4edbf4402fd475812d7f511e3c1a',
 'rtl/tb/crt3_27_mont_pair.cpp':'415c313a549aa3fe387af84eec23a6860ced0be72fa56fe73908d7d903751ef6',
 'docs/briefs/crt27_mont_oracle.py':'1b211c9c83b86b2427e2e605d53d376af863cd143775ea5894673c4001a55757',
 'docs/briefs/2026-09-30-codex-handoff.md':'486aee63bacaa895041736af6d7bf7e51ba2e87e5ac5c820230e84f90b85fa8d'}
FOOTER_KEYS=('cycles','accepted','baseline_checked','candidate_checked','matched','baseline_canceled','candidate_canceled',
             'hold_checks','async_checks','port_checks','resets','bubbles','discarded_partial')
TERMS=tuple((M//p)*pow(M//p,-1,p) for p in PRIMES)


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def source_pins(root):
    root=Path(root).resolve();pins=dict(FIXED_PINS);pins[RUNNER]=sha(root/RUNNER)
    for name,value in pins.items():
        path=root/name
        require(not path.is_symlink() and path.resolve().is_relative_to(root) and sha(path)==value,'source pin drift: '+name)
    return pins


def direct_crt(residues):
    require(len(residues)==3 and all(type(r) is int and 0<=r<p for r,p in zip(residues,PRIMES)),'canonical direct CRT inputs')
    value=sum(r*t for r,t in zip(residues,TERMS))%M
    return value-M if value>HALF else value


class EventCounts:
    """Independent due-event accounting; does not model candidate arithmetic."""
    def __init__(self):
        self.row=dict.fromkeys(FOOTER_KEYS,0);self.queues=(deque(),deque())

    def reset(self):
        row=self.row;row['baseline_canceled']+=len(self.queues[0]);row['candidate_canceled']+=len(self.queues[1])
        row['discarded_partial']+=len(self.queues[0])
        for queue in self.queues:queue.clear()
        row['resets']+=1;row['async_checks']+=4;row['port_checks']+=4

    def step(self,valid):
        row=self.row;clock=row['cycles']
        if valid:
            row['accepted']+=1
            for queue,delay in zip(self.queues,(60,15)):queue.append(clock+delay)
        else:row['bubbles']+=1
        emitted=[]
        for queue,key in zip(self.queues,('baseline_checked','candidate_checked')):
            fire=bool(queue and queue[0]==clock)
            if fire:queue.popleft();row[key]+=1
            emitted.append(fire)
        # Candidate is earlier in every uninterrupted epoch; a baseline output
        # therefore completes the same input ID's already observed pair.
        row['matched']+=int(emitted[0]);row['hold_checks']+=2-sum(emitted);row['port_checks']+=4;row['cycles']+=1


def write_vectors(path,random_cases=1000000):
    require(__debug__ and type(random_cases) is int and random_cases>=0,'assertions and integer random count')
    rng=random.Random(20260930);events=EventCounts();categories=Counter();ages=[]
    with Path(path).open('x') as stream:
        stream.write('CRT27_MONT_V1 candidate_delay=15 frozen_delay=60 coefficient_bits=96\n')
        def reset():stream.write('RESET\n');events.reset()
        def step(valid,residues,label):
            require(type(valid) is bool and len(residues)==3 and all(type(v) is int and 0<=v<=0xffffffff for v in residues),'vector word format')
            expected=direct_crt(residues) if valid else 0
            stream.write('STEP '+str(int(valid))+' '+' '.join(map(str,residues))+' '+str(expected)+'\n')
            events.step(valid);categories[label]+=1
        def integer(value,label):step(True,tuple(value%p for p in PRIMES),label)
        def drain():
            for _ in range(64):step(False,(0xffffffff,0x80000001,1<<27),'drain')
        reset()
        edges=[sorted({0,1,2,p//2-1,p//2,p//2+1,p-2,p-1}) for p in PRIMES]
        edges[0]=sorted(set(edges[0])|{PRIMES[1]-1,PRIMES[1],PRIMES[1]+1,PRIMES[2]-1,PRIMES[2],PRIMES[2]+1})
        for r1 in edges[0]:
            for r2 in edges[1]:
                for r3 in edges[2]:step(True,(r1,r2,r3),'cross_edges')
        for value in (0,1,-1,2,-2,HALF-1,HALF,HALF+1,-HALF-1,-HALF,-HALF+1,M-1,M,M+1,-M-1,-M,-M+1):integer(value,'center')
        # Construct canonical external triples with specified Garner t2 near
        # P3. This proves the one-subtraction t2m3 branch is actually reached.
        for r1 in (0,1,PRIMES[2]-1,PRIMES[2],PRIMES[0]-1):
            for t2 in (0,1,PRIMES[2]-1,PRIMES[2],PRIMES[2]+1,PRIMES[1]-2,PRIMES[1]-1):
                r2=(r1+PRIMES[0]*t2)%PRIMES[1]
                for r3 in (0,1,PRIMES[2]-1):step(True,(r1,r2,r3),'t2m3_witness')
        drain()
        for _ in range(random_cases):
            step(True,tuple(rng.randrange(p) for p in PRIMES),'random_accepted')
            if rng.randrange(5)==0:
                for _ in range(1+rng.randrange(3)):step(False,tuple(rng.randrange(1<<32) for _ in PRIMES),'random_bubble')
        drain()
        for age in range(61):
            reset();integer(HALF-age,'age_input')
            for _ in range(age):step(False,(0xffffffff,0xffffffff,0xffffffff),'age_bubble')
            reset();ages.append(age)
            for offset in range(16):integer(HALF-offset-1,'age_recovery')
            drain()
        for index in range(4096):
            if index%101==100:reset()
            valid=rng.randrange(4)!=0
            residues=tuple(rng.randrange(p) for p in PRIMES) if valid else tuple(rng.randrange(1<<32) for _ in PRIMES)
            step(valid,residues,'reset_stress_valid' if valid else 'reset_stress_bubble')
        drain()
    require(not any(events.queues),'complete vector drain')
    return dict(sha256=sha(path),bytes=Path(path).stat().st_size,seed=20260930,random_accepted=random_cases,
                categories=dict(categories),reset_ages=ages,counts=events.row,
                oracle='Direct ordinary-integer CRT sum; no candidate Montgomery/Garner expression.')


def check_probe(text):
    row=json.loads(text);wanted=dict(context_threads=1,model_threads=1,candidate_delay=15,frozen_delay=60,
        coefficient_bits=96,p1=PRIMES[0],p2=PRIMES[1],p3=PRIMES[2])
    require(row==wanted and all(type(v) is int for v in row.values()),'compiled latency/profile/context probe')
    return row


def check_normal(text,coverage):
    match=re.fullmatch('PASS '+' '.join(key+r'=(\d+)' for key in FOOTER_KEYS)+r'\n?',text)
    require(match is not None,'one exact positive footer');row=dict(zip(FOOTER_KEYS,map(int,match.groups())))
    require(row==coverage['counts'] and all(type(v) is int for v in coverage['counts'].values()),'independent complete event counters')
    require(coverage['random_accepted']==1000000 and row['matched']>=1000000 and coverage['reset_ages']==list(range(61)),
            'million accepted random triples and every pipeline reset age')
    return row


def compile_command(root,build):
    return ['verilator','--cc','--exe','--build','-j','2','--threads','1','--assert','--top-module',TOP,
        '-GCANDIDATE_DELAY=15','-GFROZEN_DELAY=60','-CFLAGS',
        '-std=c++17 -Werror=return-type -DCRT27_CANDIDATE_DELAY=15 -DCRT27_FROZEN_DELAY=60',
        '--Mdir',str(build),*[str(Path(root)/name) for name in ORDER]]


def prepare(out):
    require(__debug__,'assertions required');root=Path(__file__).resolve().parents[1];pins=source_pins(root)
    out.mkdir(parents=True,exist_ok=False);coverage=write_vectors(out/'vectors.txt')
    require(source_pins(root)==pins,'preparation source drift')
    with tarfile.open(out/'source.tar.gz','x:gz') as tar:
        for name in pins:tar.add(root/name,arcname='fpga/'+name,recursive=False)
    manifest=dict(status='prepared_positive_only_not_executed',source_root=str(SOURCE),top=TOP,profile=PROFILE,
        sources=pins,compiled_source_order=list(ORDER),vectors=coverage,archive_sha256=sha(out/'source.tar.gz'),
        limitation='Partial positive G2 only; all required mutation negatives/fresh controls pending. No component fit, whole-core, clock, board or PRP qualification.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest


def allocated(root):
    total=0
    for directory,_,names in os.walk(root):
        for name in names:
            try:total+=(Path(directory)/name).lstat().st_blocks*512
            except FileNotFoundError:continue
    return total


def execution_limits():
    group=next(line.split('::',1)[1] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
    directory=Path('/sys/fs/cgroup')/group.lstrip('/');memory=(directory/'memory.max').read_text().strip();cpu=(directory/'cpu.max').read_text().split()
    require(memory!='max' and 0<int(memory)<=6*GiB,'finite <=6GiB aggregate memory')
    require(len(cpu)==2 and cpu[0]!='max' and int(cpu[1])>0 and 0<int(cpu[0])<=2*int(cpu[1]),'finite <=200% aggregate CPU')
    affinity=sorted(os.sched_getaffinity(0));require(affinity==[0,2],'reviewed CPU0/2 allocation');cores=[]
    for number in affinity:
        topology=Path(f'/sys/devices/system/cpu/cpu{number}/topology');cores.append(tuple(int((topology/key).read_text()) for key in ('physical_package_id','core_id')))
    require(len(set(cores))==2,'two physical cores');return dict(cgroup=group,memory_max_bytes=int(memory),cpu_max=cpu,affinity=affinity,physical_cores=cores)


def execute(out,manifest_path,manifest_sha):
    require(__debug__ and socket.gethostname()=='aethia','explicit aethia execution with assertions')
    root=Path(__file__).resolve().parents[1]
    require(root==SOURCE and root.resolve()==SOURCE and LOCK.resolve()==LOCK and LOCK.is_file(),'fixed source and shared lock')
    require(out.resolve().parent==SOURCE.parent.parent and not out.exists(),'fresh isolated output')
    require(re.fullmatch('[0-9a-f]{64}',manifest_sha) and sha(manifest_path)==manifest_sha,'externally approved manifest bytes')
    manifest=json.loads(manifest_path.read_text());pins=source_pins(root)
    require(manifest['status']=='prepared_positive_only_not_executed' and manifest['sources']==pins and manifest['source_root']==str(SOURCE) and
        manifest['profile']==PROFILE and manifest['top']==TOP and manifest['compiled_source_order']==list(ORDER),'positive snapshot contract')
    limits=execution_limits();resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(6*GiB,6*GiB))
    out.mkdir();scratch=Path(tempfile.mkdtemp(prefix='gfn16-crt27-mont-',dir='/dev/shm'));os.chmod(scratch,0o700);tmp=scratch/'tmp';tmp.mkdir()
    report=dict(status='running_positive_only',scope='Unequal-latency paired CRT27 component positive stream only',top=TOP,profile=PROFILE,
        sources=pins,compiled_source_order=list(ORDER),manifest_sha256=manifest_sha,limits=limits,scratch=str(scratch),compiler_temporary_directory=str(tmp),
        steps=[],artifacts={},compile_workers=2,model_threads=1,scratch_reservation_bytes=768*MiB,scratch_free_floor_bytes=2*GiB,
        durable_reservation_bytes=192*MiB,durable_free_floor_bytes=10*GiB,host_memory_floor_bytes=4*GiB,command_timeout_seconds=1800,lock_wait_timeout_seconds=1800,
        cleanup='Nothing deleted; preserve failed evidence and scratch.',limitation='Required mutation negatives/fresh controls pending. Positive-only is not complete G2. No fit/clock/whole-core/board/PRP claim.')
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def remember(path):report['artifacts'][str(path.relative_to(out))]=sha(path)
    def guard():
        require(not (root/'docs/briefs/PAUSE').exists(),'advisor protocol PAUSE')
        require(shutil.disk_usage(out).free>=10*GiB+max(0,192*MiB-allocated(out)),'durable reservation/floor')
        require(shutil.disk_usage(scratch).free>=2*GiB+max(0,768*MiB-allocated(scratch)),'tmpfs reservation/floor')
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=4*GiB,'host memory floor')
    env={k:v for k,v in os.environ.items() if k not in ('MAKEFLAGS','MFLAGS','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS','CC','CXX','AR','OBJCACHE',
        'OPT_FAST','OPT_SLOW','OPT_GLOBAL','TMPDIR','TMP','TEMP') and not k.startswith('NTT_')}
    env.update(TMPDIR=str(tmp),TMP=str(tmp),TEMP=str(tmp))
    def run(name,command):
        guard();log=out/(name+'.log');begin=time.monotonic();failure=None
        with log.open('x') as stream:
            process=subprocess.Popen(command,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while process.poll() is None:guard();require(time.monotonic()-begin<1800,'command timeout');time.sleep(1)
            except BaseException as error:
                failure=error
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait()
        remember(log);report['steps'].append(dict(name=name,command=command,returncode=process.returncode,error=repr(failure) if failure else None,
            seconds=time.monotonic()-begin,log=log.name,sha256=sha(log)));save();print(name,process.returncode,flush=True)
        if failure:raise failure
        require(process.returncode==0,'command failed: '+name);guard();return log.read_text()
    try:
        guard();require(source_pins(root)==pins,'pre-run source drift');save()
        paths=[Path(sys.executable).resolve()]
        for tool in ('g++','verilator'):
            path=shutil.which(tool);require(path is not None,'missing '+tool);paths.append(Path(path).resolve())
        report['tool_executable_sha256']={str(path):sha(path) for path in paths};report['python_version']=sys.version
        for tool in ('verilator','g++'):report[tool+'_version']=run(tool+'-version',[tool,'--version']).strip()
        oracle=run('g1-oracle',[sys.executable,'-B',str(root/'docs/briefs/crt27_mont_oracle.py')])
        require(oracle=='C2=12212947 (0xba5ad3) CA=28766354 (0x1b6f092) CB=62755090 (0x3bd9112) P12=7256776917385217\nPASS 300775 cases\n','exact G1 oracle')
        shutil.copyfile(manifest_path,out/'approved-manifest.json');remember(out/'approved-manifest.json')
        with tarfile.open(out/'sources.tar.gz','x:gz') as tar:
            for name in pins:tar.add(root/name,arcname=name,recursive=False)
        remember(out/'sources.tar.gz');report['vectors']=write_vectors(out/'vectors.txt');remember(out/'vectors.txt')
        require(report['vectors']==manifest['vectors'],'fresh direct-CRT vectors differ from approved stage');guard();build=scratch/'build'
        with LOCK.open('r') as lock:
            deadline=time.monotonic()+1800
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:guard();require(time.monotonic()<deadline,'bounded compile lock wait');time.sleep(1)
            require(source_pins(root)==pins,'compile source drift');run('build',compile_command(root,build))
        exe=out/('V'+TOP);shutil.copy2(build/exe.name,exe);remember(exe)
        require(sha(exe)==sha(build/exe.name),'executable copy');report['executable_sha256']=sha(exe);report['executable']=str(exe)
        generated={p.name:sha(p) for p in build.iterdir() if p.is_file() and p.suffix in ('.cpp','.h','.mk','.dat')}
        with tarfile.open(out/'generated-sources.tar.gz','x:gz') as tar:
            for name in sorted(generated):tar.add(build/name,arcname=name,recursive=False)
        report['generated_source_sha256']=generated;remember(out/'generated-sources.tar.gz')
        report['probe']=check_probe(run('probe',[str(exe),'--runtime-probe']))
        report['normal_counts']=check_normal(run('normal',[str(exe),'--normal',str(out/'vectors.txt')]),report['vectors'])
        require(source_pins(root)==pins,'post-run source drift');guard()
        require(all(sha(out/name)==value for name,value in report['artifacts'].items()),'artifact drift')
        require(all(sha(path)==value for path,value in report['tool_executable_sha256'].items()),'tool identity drift')
        report['status']='passed_positive_only_mutations_pending'
    except BaseException as error:report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:save()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',type=Path);mode.add_argument('--execute',action='store_true');parser.add_argument('--output',type=Path)
    parser.add_argument('--manifest',type=Path);parser.add_argument('--manifest-sha');args=parser.parse_args()
    require(not (Path(__file__).resolve().parents[1]/'docs/briefs/PAUSE').exists(),'advisor protocol PAUSE')
    if args.prepare:
        require(args.output is None and args.manifest is None and args.manifest_sha is None,'prepare-only arguments')
        result=prepare(args.prepare.resolve());print(json.dumps(dict(status=result['status'],sources=len(result['sources']),vectors=result['vectors']),indent=2))
    else:
        require(args.output and args.manifest and args.manifest_sha,'explicit execution arguments');execute(args.output.resolve(),args.manifest.resolve(),args.manifest_sha)
