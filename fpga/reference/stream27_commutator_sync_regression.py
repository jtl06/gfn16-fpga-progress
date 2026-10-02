"""Prepare or explicitly run one isolated synchronous MDC commutator depth.

CPU4/6, <=2CPU/4GiB on aethia only. No automatic dispatch, fits or mutations.
Approved source hashes are checked before the first project import.
"""
import argparse
import fcntl
import gzip
import hashlib
import importlib
import json
import os
from pathlib import Path
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

ROOT=Path('/home/jtl/gfn-fpga-lab/agent-work/stream27-commutator-sync/snapshot-v1/fpga')
DESTINATION=ROOT.parent.parent
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
TOP='genefer_stream27_mdc_commutator_sync'
RTL='rtl/kernel/'+TOP+'.sv'
BENCH='rtl/tb/stream27_commutator_sync.cpp'
RUNNER='reference/stream27_commutator_sync_regression.py'
EXTRA=(RUNNER,BENCH,RTL,'reference/stream27_commutator_sync_model.py',
       'reference/stream27_commutator_sync_vectors.py','reference/stream27_commutator_sync_structure.py',
       'tests/test_stream27_commutator_sync.py','tests/test_stream27_commutator_sync_native.py')
FROZEN={'reference/__init__.py':'1c6df6d638965f2bc1c163f4e66f7f9038ebedc21e2139988aa5962c0ed47efb',
        'reference/stream_ntt_schedule.py':'03c1c855e0f6e31f0fcb85d32ed2e604a935e482dfa725d7207e635cb1e963cc',
        'reference/stream_ntt_model.py':'b8526b6174491c35b537c0287a33c7467c07fa049c7a397c1f491e56c6121b23',
        'docs/STREAM27-BLOCKCARRY-PROFILE.md':'c3c3fbe371de9bcaf1781b8175dc53c5615393c8a63c62783e81527c822c449c'}
VECTOR_SHA={1:'031f40c37919ee1adf85313a69a21089e857972af58b7372d5a1bf639467875e',
2:'d6af5102c8144eba536329d9ef82f6eff4dad2dc03d90f21f94fe44ed1981e66',
4:'7a600f89c63a9e7e4fbfd9ea66df30d148f6ac4cd281d72bf9966623c178ef06',
16:'9ebc72587ce983a64e2ee3a8340e533483f7e1c7e0b35eaf06984f77f5bdd14c',
4096:'08c2e5d550b6c71243f9d655817b3d291ec1b36be37a75c05870c2018090621f'}
GIB=1<<30
MIB=1<<20


def require(ok,why):
    if not ok:raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def source_pins(root):
    root=Path(root).resolve()
    pins=dict(FROZEN)
    for name in EXTRA:pins[name]=sha(root/name)
    for name,digest in pins.items():
        path=root/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and not path.is_symlink() and
                path.resolve().is_relative_to(root) and sha(path)==digest,'closed source identity: '+name)
    return pins


def load_project(root,pins):
    require(not any(n=='reference' or n.startswith('reference.') for n in sys.modules),'clean project namespace')
    require(source_pins(root)==pins,'pre-import drift')
    require(not any(p.suffix in ('.pyc','.so','.pyd') for p in (root/'reference').rglob('*')),'source-only imports')
    sys.dont_write_bytecode=True;sys.path.insert(0,str(root))
    vectors=importlib.import_module('reference.stream27_commutator_sync_vectors')
    structure=importlib.import_module('reference.stream27_commutator_sync_structure');structure.validate(root)
    for name,module in tuple(sys.modules.items()):
        if name=='reference' or name.startswith('reference.'):
            path=Path(module.__file__).resolve();require(path.is_relative_to(root),'external project import')
            relative=str(path.relative_to(root));require(relative in pins and sha(path)==pins[relative],'unlisted project import')
    return vectors


def prepare(out):
    root=Path(__file__).resolve().parents[1];pins=source_pins(root)
    require(not out.exists(),'fresh component stage');out.mkdir(parents=True)
    with tarfile.open(out/'source.tar.gz','x:gz') as tar:
        for name in sorted(pins):tar.add(root/name,arcname='fpga/'+name,recursive=False)
    require(source_pins(root)==pins,'source drift during staging')
    manifest=dict(status='prepared_not_executed',target=str(ROOT),top=TOP,sources=pins,
         archive_sha256=sha(out/'source.tar.gz'),supported_depth=[1,2,4,16,4096],contexts=2,payload_w=16,
         vector_sha256={str(k):v for k,v in VECTOR_SHA.items()},compiled=[RTL],bench=BENCH,
         limits=dict(cpus=[4,6],cpu_quota=2,memory_bytes=4*GIB,command_seconds=300,total_seconds=900),
         limitation='Synchronous pair only; no RAM inference or full field, physical clock or board claim; one depth per invocation.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(files=len(pins),manifest_sha256=sha(out/'manifest.json'),archive_sha256=sha(out/'source.tar.gz'))))
    return manifest


def verify_manifest(root,path,digest,depth):
    require(type(depth) is int and depth in (1,2,4,16,4096),'explicit component profile')
    require(re.fullmatch('[0-9a-f]{64}',digest) is not None and sha(path)==digest,'approved manifest SHA')
    manifest=json.loads(path.read_text());pins=source_pins(root)
    require(manifest['status']=='prepared_not_executed' and manifest['target']==str(ROOT) and manifest['top']==TOP and
            manifest['sources']==pins and manifest['supported_depth']==[1,2,4,16,4096] and manifest['contexts']==2 and manifest['payload_w']==16 and
            manifest['compiled']==[RTL] and manifest['bench']==BENCH and
            manifest['vector_sha256']=={str(k):v for k,v in VECTOR_SHA.items()} and
            manifest['limits']==dict(cpus=[4,6],cpu_quota=2,memory_bytes=4*GIB,command_seconds=300,total_seconds=900),
            'exact component manifest contract')
    return manifest,pins


def check_probe(output):
    value=json.loads(output.strip())
    require(value==dict(context_threads=1,model_threads=1,expected_threads=1),'explicit model/context thread probe')
    return value


def check_output(output,expected):
    lines=re.findall(r'^COMM_SYNC_PASS (.*)$',output,re.M)
    require(len(lines)==1,'one component footer')
    fields=[x.split('=',1) for x in lines[0].split()]
    require(all(len(x)==2 for x in fields) and len({x[0] for x in fields})==len(fields),'unique component footer fields')
    actual={k:int(v) for k,v in fields}
    keys=('depth','frame_ticks','events','valid','errors','resets','before_checks','edge_checks')
    require(actual=={k:expected[k] for k in keys},'complete component coverage and edge accounting')
    return actual


def execution_limits():
    group=next(line.split('::',1)[1] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
    directory=Path('/sys/fs/cgroup')/group.lstrip('/')
    memory=(directory/'memory.max').read_text().strip();quota=(directory/'cpu.max').read_text().split()
    require(memory!='max' and int(memory)<=4*GIB,'aggregate4GiB cap')
    require(len(quota)==2 and quota[0]!='max' and int(quota[0])<=2*int(quota[1]),'aggregate2CPU quota')
    cpus=sorted(os.sched_getaffinity(0));require(cpus==[4,6],'disjoint reserved CPU4/6')
    cores=[]
    for cpu in cpus:
        path=Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        cores.append(tuple(int((path/name).read_text()) for name in ('physical_package_id','core_id')))
    require(len(set(cores))==2,'distinct physical cores')
    return dict(cgroup=group,memory_max=int(memory),cpu_max=quota,affinity=cpus,physical_cores=cores)


def allocated(path):
    total=0
    for directory,_,names in os.walk(path):
        for name in names:
            try:total+=(Path(directory)/name).lstat().st_blocks*512
            except FileNotFoundError:continue
    return total


def archive_executable(source,target):
    require(source.is_file() and not source.is_symlink() and not target.exists(),'fresh executable compression')
    identity=sha(source)
    with source.open('rb') as original,target.open('xb') as output:
        with gzip.GzipFile(filename='',fileobj=output,mode='wb',mtime=0) as zipped:shutil.copyfileobj(original,zipped,1<<20)
    with gzip.open(target,'rb') as stream:require(hashlib.file_digest(stream,'sha256').hexdigest()==identity,'executable gzip round-trip')
    return dict(executable_sha256=identity,gzip_sha256=sha(target),raw_bytes=source.stat().st_size,gzip_bytes=target.stat().st_size)


def execute(depth,out,path,digest):
    require(__debug__ and socket.gethostname()=='aethia','aethia with assertions only')
    root=Path(__file__).resolve().parents[1]
    require(root==ROOT and root.resolve()==ROOT,'fixed fresh component snapshot')
    require(out.resolve().parent==DESTINATION and not out.exists(),'fresh component result path')
    require(LOCK.is_file() and LOCK.resolve()==LOCK,'existing shared compiler lock')
    manifest,pins=verify_manifest(root,path,digest,depth);vectors=load_project(root,pins);limits=execution_limits()
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(4*GIB,4*GIB))
    out.mkdir();scratch=Path(tempfile.mkdtemp(prefix='gfn16-comm-',dir='/dev/shm'));os.chmod(scratch,0o700)
    temporary=scratch/'tmp';temporary.mkdir();started=time.monotonic()
    report=dict(status='running',depth=depth,frame_ticks=max(8,2*depth),contexts=2,payload_w=16,top=TOP,sources=pins,manifest_sha256=digest,
        limits=limits,compile_workers=2,model_threads=1,compiled=[RTL],bench=BENCH,steps=[],artifacts={},scratch=str(scratch),
        command_timeout_seconds=300,total_budget_seconds=900,lock_wait_seconds=300,
        scratch_reservation_bytes=256*MIB,scratch_free_floor_bytes=2*GIB,durable_reservation_bytes=32*MIB,
        durable_free_floor_bytes=10*GIB,host_memory_floor_bytes=4*GIB,cleanup='All scratch/evidence retained; no deletion.',
        limitation='One synchronous commutator depth only; no field/whole-core/physical clock claim.')
    def remember(p):report['artifacts'][str(p.relative_to(out))]=sha(p)
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def guard():
        require(time.monotonic()-started<900,'overall component timeout')
        require(shutil.disk_usage(scratch).free>=2*GIB+max(0,256*MIB-allocated(scratch)),'tmpfs reservation/floor')
        require(shutil.disk_usage(out).free>=10*GIB+max(0,32*MIB-allocated(out)),'durable reservation/floor')
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=4*GIB,'host memory floor')
    def recheck():require(verify_manifest(root,path,digest,depth)[1]==pins,'approved source drift')
    env={k:v for k,v in os.environ.items() if k not in ('MAKEFLAGS','MFLAGS','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS','CC','CXX',
         'AR','OBJCACHE','OPT_FAST','OPT_SLOW','OPT_GLOBAL','TMPDIR','TMP','TEMP') and not k.startswith('NTT_')}
    env.update(TMPDIR=str(temporary),TMP=str(temporary),TEMP=str(temporary),CCACHE_DISABLE='1')
    def run(name,argv):
        guard();recheck();log=out/(name+'.log');before=time.monotonic();failure=None
        with log.open('x') as stream:
            child=subprocess.Popen(argv,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while child.poll() is None:
                    guard();require(time.monotonic()-before<300,'component command timeout');time.sleep(.25)
            except BaseException as error:
                failure=error
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                child.wait()
        remember(log);report['steps'].append(dict(name=name,command=argv,returncode=child.returncode,
            seconds=time.monotonic()-before,error=repr(failure) if failure else None,log=log.name,sha256=sha(log)))
        save()
        if failure:raise failure
        require(child.returncode==0,name+' failed');guard();return log.read_text()
    try:
        guard();recheck();tools=[Path(sys.executable).resolve()]
        for name in ('g++','verilator','verilator_bin','make'):
            found=shutil.which(name);require(found is not None,'missing '+name);tools.append(Path(found).resolve())
        report['tool_sha256']={str(p):sha(p) for p in tools};report['python_version']=sys.version
        report['verilator_version']=run('verilator-version',['verilator','--version']).strip()
        report['compiler_version']=run('compiler-version',['g++','--version']).strip()
        shutil.copyfile(path,out/'approved-manifest.json');remember(out/'approved-manifest.json')
        with tarfile.open(out/'sources.tar.gz','x:gz') as tar:
            for name in sorted(pins):tar.add(root/name,arcname=name,recursive=False)
        remember(out/'sources.tar.gz')
        text,expected=vectors.corpus(depth);require(expected['sha256']==VECTOR_SHA[depth],'approved independent oracle corpus')
        vector=out/'vectors.txt';vector.write_text(text);remember(vector);report['vectors']=expected
        require(sha(vector)==VECTOR_SHA[depth],'durable corpus identity')
        build=scratch/'build'
        command=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
                 f'-GDEPTH={depth}',f'-GFRAME_T={max(8,2*depth)}','-GCONTEXTS=2','-GPAYLOAD_W=16','-CFLAGS',f'-std=c++17 -Werror=return-type -DCOMM_DEPTH={depth}',
                 '--Mdir',str(build),str(root/RTL),str(root/BENCH)]
        with LOCK.open('r') as lock:
            deadline=time.monotonic()+300
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:guard();require(time.monotonic()<deadline,'component compile lock timeout');time.sleep(.25)
            run('build',command)
        exe=build/('V'+TOP);archive=out/'model.gz';report['executable']=str(exe)
        report['executable_identity']=archive_executable(exe,archive);remember(archive)
        generated={p.name:sha(p) for p in build.iterdir() if p.is_file() and p.suffix in ('.cpp','.h','.mk','.dat')}
        with tarfile.open(out/'generated-sources.tar.gz','x:gz') as tar:
            for name in sorted(generated):tar.add(build/name,arcname=name,recursive=False)
        report['generated_source_sha256']=generated;remember(out/'generated-sources.tar.gz')
        report['probe']=check_probe(run('probe',[str(exe),'--runtime-probe']))
        report['coverage']=check_output(run('test',[str(exe),str(vector)]),expected)
        recheck();guard()
        require(sha(exe)==report['executable_identity']['executable_sha256'],'native model drift')
        with gzip.open(archive,'rb') as stream:
            require(hashlib.file_digest(stream,'sha256').hexdigest()==sha(exe),'durable executable identity')
        require(all(sha(out/name)==value for name,value in report['artifacts'].items()),'artifact drift')
        require(all(sha(p)==value for p,value in report['tool_sha256'].items()),'toolchain drift')
        report['status']='passed_synchronous_commutator_component_depth'
    except BaseException as error:report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:save()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',type=Path);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--depth',type=int,choices=(1,2,4,16,4096));parser.add_argument('--output',type=Path)
    parser.add_argument('--manifest',type=Path);parser.add_argument('--manifest-sha')
    args=parser.parse_args()
    if args.prepare:
        require(not args.execute and args.depth is None and not any((args.output,args.manifest,args.manifest_sha)),'exclusive prepare mode')
        prepare(args.prepare.resolve())
    else:
        require(args.execute and args.depth and args.output and args.manifest and args.manifest_sha,'explicit single-profile execution')
        execute(args.depth,args.output.resolve(),args.manifest.resolve(),args.manifest_sha)


if __name__=='__main__':main()
