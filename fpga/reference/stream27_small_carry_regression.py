"""Prepare or explicitly run one tiny AW5/AW16 small-carry native gate.

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

ROOT=Path('/home/jtl/gfn-fpga-lab/agent-work/stream27-small-carry/snapshot-v1/fpga')
DESTINATION=ROOT.parent.parent
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
TOP='genefer_stream27_blockcarry_small_cell'
RTL='rtl/kernel/'+TOP+'.sv'
BENCH='rtl/tb/stream27_small_carry.cpp'
RUNNER='reference/stream27_small_carry_regression.py'
SOURCE_RECEIPT='docs/briefs/replies/2026-09-30-B20260930S-S3-small-carry-source-v1.json'
SOURCE_SHA='fdbf0f7fdeacd438ba5f273bdaf1d1bef5dbad7c4861f108c7f79f4495328809'
REVIEW='results/throughput-20260929/stream27-small-carry-independent-review-v1.json'
REVIEW_SHA='ec90595c3017051baf88382d4e9ec2b7c6eb27f0ebcd0f6574a6dfc33bc5c483'
EXTRA=(RUNNER,BENCH,'reference/stream27_small_carry_vectors.py','tests/test_stream27_small_carry_native.py')
VECTOR_SHA={5:'0ab447e8dbc987358912d6cd1e61e3d4b0381832dccede241b93e59f438c7b6e',
            16:'9335778f652256650b93a0690b89d4ae5531cc993026043a8706319ffc788a4e'}
GIB=1<<30
MIB=1<<20


def require(ok,why):
    if not ok:raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def source_pins(root):
    root=Path(root).resolve()
    require(sha(root/SOURCE_RECEIPT)==SOURCE_SHA and sha(root/REVIEW)==REVIEW_SHA,'approved component source/review')
    receipt=json.loads((root/SOURCE_RECEIPT).read_text())
    pins={**receipt['authority_and_proof_sha256'],**receipt['new_sources_sha256'],
          SOURCE_RECEIPT:SOURCE_SHA,REVIEW:REVIEW_SHA,
          'reference/__init__.py':'1c6df6d638965f2bc1c163f4e66f7f9038ebedc21e2139988aa5962c0ed47efb',
          'reference/stream_ntt_model.py':'b8526b6174491c35b537c0287a33c7467c07fa049c7a397c1f491e56c6121b23'}
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
    vectors=importlib.import_module('reference.stream27_small_carry_vectors')
    structure=importlib.import_module('reference.stream27_small_carry_structure');structure.validate(root)
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
         archive_sha256=sha(out/'source.tar.gz'),supported_aw=[5,16],p=8,payload_w=16,
         vector_sha256={str(k):v for k,v in VECTOR_SHA.items()},compiled=[RTL],bench=BENCH,
         limits=dict(cpus=[4,6],cpu_quota=2,memory_bytes=4*GIB,command_seconds=300,total_seconds=900),
         limitation='Tiny component only; no full field, physical clock or board claim; one AW per invocation.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(files=len(pins),manifest_sha256=sha(out/'manifest.json'),archive_sha256=sha(out/'source.tar.gz'))))
    return manifest


def verify_manifest(root,path,digest,aw):
    require(type(aw) is int and aw in (5,16),'explicit component profile')
    require(re.fullmatch('[0-9a-f]{64}',digest) is not None and sha(path)==digest,'approved manifest SHA')
    manifest=json.loads(path.read_text());pins=source_pins(root)
    require(manifest['status']=='prepared_not_executed' and manifest['target']==str(ROOT) and manifest['top']==TOP and
            manifest['sources']==pins and manifest['supported_aw']==[5,16] and manifest['p']==8 and manifest['payload_w']==16 and
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
    lines=re.findall(r'^SMALL_CARRY_PASS (.*)$',output,re.M)
    require(len(lines)==1,'one component footer')
    fields=[x.split('=',1) for x in lines[0].split()]
    require(all(len(x)==2 for x in fields) and len({x[0] for x in fields})==len(fields),'unique component footer fields')
    actual={k:int(v) for k,v in fields}
    keys=('aw','p','events','good','errors','bubbles','resets','feedback','carry_mask','before_checks','edge_checks')
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


def execute(aw,out,path,digest):
    require(__debug__ and socket.gethostname()=='aethia','aethia with assertions only')
    root=Path(__file__).resolve().parents[1]
    require(root==ROOT and root.resolve()==ROOT,'fixed fresh component snapshot')
    require(out.resolve().parent==DESTINATION and not out.exists(),'fresh component result path')
    require(LOCK.is_file() and LOCK.resolve()==LOCK,'existing shared compiler lock')
    manifest,pins=verify_manifest(root,path,digest,aw);vectors=load_project(root,pins);limits=execution_limits()
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(4*GIB,4*GIB))
    out.mkdir();scratch=Path(tempfile.mkdtemp(prefix='gfn16-scell-',dir='/dev/shm'));os.chmod(scratch,0o700)
    temporary=scratch/'tmp';temporary.mkdir();started=time.monotonic()
    report=dict(status='running',aw=aw,p=8,payload_w=16,top=TOP,sources=pins,manifest_sha256=digest,
        limits=limits,compile_workers=2,model_threads=1,compiled=[RTL],bench=BENCH,steps=[],artifacts={},scratch=str(scratch),
        command_timeout_seconds=300,total_budget_seconds=900,lock_wait_seconds=300,
        scratch_reservation_bytes=256*MIB,scratch_free_floor_bytes=2*GIB,durable_reservation_bytes=32*MIB,
        durable_free_floor_bytes=10*GIB,host_memory_floor_bytes=4*GIB,cleanup='All scratch/evidence retained; no deletion.',
        limitation='One small-cell component profile only; no field/whole-core/physical clock claim.')
    def remember(p):report['artifacts'][str(p.relative_to(out))]=sha(p)
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def guard():
        require(time.monotonic()-started<900,'overall component timeout')
        require(shutil.disk_usage(scratch).free>=2*GIB+max(0,256*MIB-allocated(scratch)),'tmpfs reservation/floor')
        require(shutil.disk_usage(out).free>=10*GIB+max(0,32*MIB-allocated(out)),'durable reservation/floor')
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=4*GIB,'host memory floor')
    def recheck():require(verify_manifest(root,path,digest,aw)[1]==pins,'approved source drift')
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
        text,expected=vectors.corpus(aw);require(expected['sha256']==VECTOR_SHA[aw],'approved independent oracle corpus')
        vector=out/'vectors.txt';vector.write_text(text);remember(vector);report['vectors']=expected
        require(sha(vector)==VECTOR_SHA[aw],'durable corpus identity')
        build=scratch/'build'
        command=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
                 f'-GAW={aw}','-GP=8','-GPAYLOAD_W=16','-CFLAGS',f'-std=c++17 -Werror=return-type -DSCELL_AW={aw}',
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
        report['status']='passed_small_carry_component_profile'
    except BaseException as error:report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:save()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',type=Path);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--aw',type=int,choices=(5,16));parser.add_argument('--output',type=Path)
    parser.add_argument('--manifest',type=Path);parser.add_argument('--manifest-sha')
    args=parser.parse_args()
    if args.prepare:
        require(not args.execute and args.aw is None and not any((args.output,args.manifest,args.manifest_sha)),'exclusive prepare mode')
        prepare(args.prepare.resolve())
    else:
        require(args.execute and args.aw and args.output and args.manifest and args.manifest_sha,'explicit single-profile execution')
        execute(args.aw,args.output.resolve(),args.manifest.resolve(),args.manifest_sha)


if __name__=='__main__':main()
