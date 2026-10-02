"""Prepare candidate-helper gate; explicit reviewed --execute is aethia-only.

No project imports. This runner never selects the helper in an NTT/core or
changes a frozen source. All results require fresh executable runs, not cached
correctness. Preparation and Python tests are not RTL simulation evidence.
"""
import argparse
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

TOP='genefer_montgomery_mul27_canonical_pipe'
SOURCE=Path('/home/jtl/gfn-fpga-lab/agent-work/mont27-canonical/snapshot-v2/fpga')
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
FIELDS=((104857601,4190109697),(69206017,4225761281),(67239937,4227727361))
PINS={
 'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv':'501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b',
 'rtl/kernel/genefer_montgomery_mul27_canonical_pipe.sv':'1d29fffb22b5ab9414d83b2cdde4d4068d605b51d60bda6d7b5d47688e181352',
 'rtl/tb/montgomery27_canonical_pipe.cpp':'2dc07481ff42f258542d8576743e74b4de2d4c4c1232f5d9199dca97a7a29d84',
 'reference/montgomery27_canonical_structure.py':'9e98101e421ef347a46e2cfed4e928b92783dad5433c00232b8f9fd394f33e42',
}
GiB=1<<30;MiB=1<<20


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def source_pins(root):
    for name,h in PINS.items():
        path=root/name;require(not path.is_symlink() and sha(path)==h,'qualified source identity: '+name)
    return {**PINS,'reference/montgomery27_canonical_regression.py':sha(root/'reference/montgomery27_canonical_regression.py')}


def vectors(p,q):
    require((p,q) in FIELDS,'supported field required')
    R=1<<32;rinv=pow(R,-1,p);rng=random.Random(0x270ca11+p);rows=[];branches=[0,0]
    def emit(reset,valid,a,b):
        value=a*b*rinv%p
        if reset and valid:
            require(0<=a<p and 0<=b<p,'vector canonical domain')
            t=a*b;multiple=(t*q)%R
            branches[int(t//R < (multiple*p)//R)]+=1
        rows.append((int(reset),int(valid),a,b,value))
    emit(0,1,R-1,R-1)
    edges=sorted({0,1,2,p//2-1,p//2,p//2+1,p-3,p-2,p-1,(1<<26)-1,1<<26,(1<<26)+1,R%p})
    for a in edges:
        for b in edges:emit(1,1,a,b)
    for index in range(30000):
        reset=index%251!=250;valid=index%7!=6
        a,b=(rng.randrange(p),rng.randrange(p)) if reset and valid else (rng.randrange(R),rng.randrange(R))
        emit(reset,valid,a,b)
    # An isolated token canceled before/at/after each possible result edge.
    for age in range(4):
        emit(0,0,R-1,R-1);emit(1,1,p-1,p-1)
        for _ in range(age):emit(1,0,R-1,R-1)
        emit(0,1,R-1,R-1)
        for _ in range(5):emit(1,0,R-1,R-1)
        for _ in range(8):emit(1,1,rng.randrange(p),rng.randrange(p))
    # Sustained II1 with every occupancy followed by a reset and refill.
    for depth in range(1,5):
        for j in range(depth):emit(1,1,p-1-j,p-2-j)
        emit(0,1,R-1,R-1)
        for _ in range(8):emit(1,1,rng.randrange(p),rng.randrange(p))
    for _ in range(8):emit(1,0,R-1,R-1)
    pending={};checked=canceled=holds=0;high_bit=False
    for clock,(reset,valid,a,b,value) in enumerate(rows):
        if not reset:canceled+=len(pending);pending.clear()
        elif valid:pending[clock+3]=value
        expected=pending.pop(clock,None)
        if expected is None:holds+=1
        else:checked+=1;high_bit|=bool(expected&(1<<26))
    require(not pending and checked>1000 and min(branches)>0 and high_bit,'vector coverage/drain')
    payload=''.join(' '.join(map(str,row))+'\n' for row in rows)
    summary=dict(p=p,q=q,checked=checked,canceled=canceled,hold_checks=holds,cycles=len(rows),
                 correction_branch_accepts=branches,reset_ages=[0,1,2,3],reset_occupancies=[1,2,3,4],
                 result_bit26_witness=True,random_rows=30000)
    return payload,summary


def check_normal(returncode,output,summary):
    require(type(returncode) is int and returncode==0,'normal command failure')
    expected='PASS P={p} checked={checked} canceled={canceled} hold_checks={hold_checks} cycles={cycles}'.format(**summary)
    require(output.strip()==expected,'normal arithmetic/latency/hold coverage footer')


def assertion_rejection(returncode,output,message,source):
    if type(returncode) is not int or returncode not in (-6,1,134):return False
    marker='$fatal(1,"'+message+'");'
    lines=source.splitlines()
    matches=[i+1 for i,line in enumerate(lines) if marker in line]
    if len(matches)!=1:return False
    filename=r'(?:'+re.escape(str(SOURCE/'rtl/kernel'))+r'/)?'+re.escape(TOP)+r'\.sv'
    location=filename+':'+str(matches[0])
    primary=(r'\[\d+\] %(?:Error|Fatal): '+location+
             r': Assertion failed in TOP\.'+re.escape(TOP)+r'(?:\.\w+)*: '+re.escape(message))
    trailer=r'%Error: '+location+r': Verilog \$stop'
    output_lines=[line for line in output.splitlines() if line]
    if not output_lines or re.fullmatch(primary,output_lines.pop(0)) is None:return False
    if output_lines and re.fullmatch(trailer,output_lines[0]):output_lines.pop(0)
    if output_lines and output_lines[0]=='Aborting...':output_lines.pop(0)
    return not output_lines


def allocated(root):
    total=0
    for directory,_,names in os.walk(root):
        for name in names:
            try:total+=(Path(directory)/name).lstat().st_blocks*512
            except FileNotFoundError:continue
    return total


def execution_limits():
    group=next(line.split('::',1)[1] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
    cgroup=Path('/sys/fs/cgroup')/group.lstrip('/')
    memory=(cgroup/'memory.max').read_text().strip();cpu=(cgroup/'cpu.max').read_text().split()
    require(memory!='max' and 0<int(memory)<=6*GiB,'aggregate memory cap required')
    require(len(cpu)==2 and cpu[0]!='max' and 0<int(cpu[0])<=2*int(cpu[1]),'aggregate CPU quota required')
    affinity=sorted(os.sched_getaffinity(0));require(affinity==[0,2],'reviewed physical CPU0/2 allocation')
    cores=[]
    for number in affinity:
        path=Path(f'/sys/devices/system/cpu/cpu{number}/topology')
        cores.append(tuple(int((path/key).read_text()) for key in ('physical_package_id','core_id')))
    require(len(set(cores))==2,'distinct physical cores required')
    return dict(cgroup=group,memory_max_bytes=int(memory),cpu_max=cpu,affinity=affinity,physical_cores=cores)


def prepare(out):
    root=Path(__file__).resolve().parents[1];pins=source_pins(root)
    out.mkdir(parents=True,exist_ok=False)
    with tarfile.open(out/'sources.tar.gz','x:gz') as tar:
        for name in pins:tar.add(root/name,arcname='fpga/'+name,recursive=False)
    manifest=dict(status='prepared_not_executed',source_root=str(SOURCE),sources=pins,
                  archive_sha256=sha(out/'sources.tar.gz'),scope='Standalone canonical-output Montgomery helper only',
                  limitation='No transfer/build/simulation/fit/integration. Coordinate with parent before any remote launch.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def execute(out,manifest_path,manifest_sha):
    require(__debug__ and socket.gethostname()=='aethia','explicit aethia execution with assertions required')
    root=Path(__file__).resolve().parents[1]
    require(root==SOURCE and root.resolve()==SOURCE and LOCK.resolve()==LOCK and LOCK.is_file(),'fixed snapshot/lock identity')
    require(re.fullmatch('[0-9a-f]{64}',manifest_sha) and sha(manifest_path)==manifest_sha,'approved manifest identity')
    manifest=json.loads(manifest_path.read_text());pins=source_pins(root)
    require(manifest['status']=='prepared_not_executed' and manifest['source_root']==str(SOURCE) and manifest['sources']==pins,'pre-import source manifest')
    require(out.resolve().parent==SOURCE.parent.parent and not out.exists(),'fresh isolated evidence directory')
    limits=execution_limits();resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(6*GiB,6*GiB))
    out.mkdir();scratch=Path(tempfile.mkdtemp(prefix='gfn16-mont27-canonical-',dir='/dev/shm'));os.chmod(scratch,0o700)
    tmp=scratch/'tmp';tmp.mkdir();rtl=root/'rtl/kernel'/(TOP+'.sv');bench=root/'rtl/tb/montgomery27_canonical_pipe.cpp'
    report=dict(status='running',sources=pins,limits=limits,scratch=str(scratch),compiler_temporary_directory=str(tmp),
                manifest_sha256=manifest_sha,steps=[],vectors={},builds=[],artifacts={},fields=list(FIELDS),
                stages=4,initiation_interval=1,compile_workers=2,model_threads=1,radix_bits=32,
                durable_reservation_bytes=32*MiB,durable_free_floor_bytes=10*GiB,scratch_reservation_bytes=512*MiB,
                scratch_free_floor_bytes=2*GiB,host_memory_floor_bytes=4*GiB,command_timeout_seconds=300,
                lock_wait_timeout_seconds=900,cleanup='No scratch/evidence deletion; preserve failed attempts.')
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def remember(path):report['artifacts'][str(path.relative_to(out))]=sha(path)
    def recheck():require(source_pins(root)==pins,'source drift')
    def guard():
        require(shutil.disk_usage(out).free>=10*GiB+max(0,32*MiB-allocated(out)),'durable reservation/floor')
        require(shutil.disk_usage(scratch).free>=2*GiB+max(0,512*MiB-allocated(scratch)),'tmpfs reservation/floor')
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=4*GiB,'host available memory floor')
    env={k:v for k,v in os.environ.items() if k not in ('MAKEFLAGS','MFLAGS','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS',
        'CC','CXX','AR','OBJCACHE','OPT_FAST','OPT_SLOW','OPT_GLOBAL','TMPDIR','TMP','TEMP') and not k.startswith('NTT_')}
    env.update(TMPDIR=str(tmp),TMP=str(tmp),TEMP=str(tmp))
    def run(name,command,rejection=None):
        guard();log=out/(name+'.log');begin=time.monotonic();failure=None
        with log.open('x') as stream:
            proc=subprocess.Popen(command,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while proc.poll() is None:
                    guard();require(time.monotonic()-begin<300,'command timeout');time.sleep(1)
            except BaseException as error:
                failure=error
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proc.wait()
        remember(log);text=log.read_text()
        report['steps'].append(dict(name=name,command=command,returncode=proc.returncode,error=repr(failure) if failure else None,
                                   seconds=time.monotonic()-begin,log=log.name,sha256=sha(log),expected_assertion=rejection));save()
        if failure:raise failure
        require(proc.returncode==0 if rejection is None else assertion_rejection(proc.returncode,text,rejection,rtl.read_text()),'unexpected command result: '+name)
        guard();return proc.returncode,text
    def build(name,p,q):
        directory=scratch/name
        command=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
                 '--Mdir',str(directory),f'-GP={p}',f'-GQ={q}',str(rtl),str(bench)]
        with LOCK.open('r') as lock:
            deadline=time.monotonic()+900
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:guard();require(time.monotonic()<deadline,'compile lock wait timeout');time.sleep(1)
            recheck();run('build-'+name,command)
        executable=out/('V'+TOP+'-'+name);shutil.copy2(directory/('V'+TOP),executable);remember(executable)
        require(sha(executable)==sha(directory/('V'+TOP)),'durable model copy')
        generated={x.name:sha(x) for x in directory.iterdir() if x.is_file() and x.suffix in ('.cpp','.h','.mk','.dat')}
        archive=out/(name+'-generated.tar.gz')
        with tarfile.open(archive,'x:gz') as tar:
            for relative in sorted(generated):tar.add(directory/relative,arcname=relative,recursive=False)
        remember(archive);report['builds'].append(dict(name=name,p=p,q=q,executable=executable.name,sha256=sha(executable),generated_sources=generated))
        return executable
    try:
        guard();recheck();save()
        paths=[Path(sys.executable).resolve()]
        for name in ('g++','verilator'):
            found=shutil.which(name);require(found is not None,'required tool '+name);paths.append(Path(found).resolve())
        report['tool_executable_sha256']={str(p):sha(p) for p in paths};report['python_version']=sys.version
        for name in ('verilator','g++'):_,report[name+'_version']=run(name+'-version',[name,'--version'])
        shutil.copyfile(manifest_path,out/'approved-manifest.json');remember(out/'approved-manifest.json')
        with tarfile.open(out/'sources.tar.gz','x:gz') as tar:
            for name in pins:tar.add(root/name,arcname=name,recursive=False)
        remember(out/'sources.tar.gz')
        for index,(p,q) in enumerate(FIELDS):
            payload,summary=vectors(p,q);path=out/f'vectors-p{index+1}.txt';path.write_text(payload);remember(path)
            report['vectors'][str(p)]={**summary,'sha256':sha(path)}
            exe=build(f'p{index+1}',p,q)
            _,probe=run(f'probe-p{index+1}',[str(exe),'--runtime-probe'])
            actual=json.loads(probe);require(actual==dict(context_threads=1,model_threads=1,expected_threads=1) and all(type(x) is int for x in actual.values()),'runtime probe')
            rc,text=run(f'normal-p{index+1}',[str(exe),str(path),str(p)]);check_normal(rc,text,summary)
            for label,a,b in (('lhs-P',p,1),('rhs-P',1,p),('wide-lhs',1<<27,1),('wide-rhs',1,0xffffffff)):
                run(f'reject-p{index+1}-{label}',[str(exe),'reject',str(p),str(a),str(b)],'noncanonical Montgomery27 input')
        for name,p,q,message in (('unsupported-modulus',3,4294967295,'unsupported sparse Montgomery27 modulus'),
                                 ('invalid-inverse',FIELDS[0][0],FIELDS[0][1]^2,'invalid sparse Montgomery inverse')):
            exe=build(name,p,q);run('reject-'+name,[str(exe),'reject',str(p)],message)
        recheck();guard()
        require(all(sha(out/name)==h for name,h in report['artifacts'].items()),'durable artifact drift')
        require(all(sha(p)==h for p,h in report['tool_executable_sha256'].items()),'tool identity drift')
        report.update(status='passed_standalone_helper',limitation='Standalone legal-domain pipeline and retained assertion gate only; no NTT integration, resource, timing or full PRP claim.')
    except BaseException as error:report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:save()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--prepare',type=Path);group.add_argument('--execute',action='store_true')
    parser.add_argument('--output',type=Path);parser.add_argument('--manifest',type=Path);parser.add_argument('--manifest-sha')
    args=parser.parse_args()
    if args.prepare:
        require(args.output is None and args.manifest is None and args.manifest_sha is None,'prepare-only arguments')
        print(json.dumps(prepare(args.prepare.resolve()),indent=2))
    else:
        require(args.output and args.manifest and args.manifest_sha,'explicit execution paths and approved manifest hash')
        execute(args.output.resolve(),args.manifest.resolve(),args.manifest_sha)


if __name__=='__main__':main()
