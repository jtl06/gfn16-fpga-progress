"""Separate tiny signed-boundary native gate, one AW and all3 fields.

Preparation only unless explicitly dispatched by parent. Reuses exact pinned
small-cell resource/compression helpers, never its stage/execute/profile logic.
"""
import argparse
import fcntl
import gzip
import hashlib
import importlib
import importlib.util
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

ROOT=Path('/home/jtl/gfn-fpga-lab/agent-work/stream27-signed-boundary/snapshot-v1/fpga')
DESTINATION=ROOT.parent.parent
RUNNER='reference/stream27_signed_boundary_regression.py'
INFRA='reference/stream27_small_carry_regression.py'
INFRA_SHA='10aac11031f42872fb3fc0a64cbd55258ed9b708be7cc52f958056c1ebfd1709'
SOURCE='results/throughput-20260929/stream27-signed-boundary-source-v1.json'
SOURCE_SHA='c150e75a4923795bcd833ad1c22409367a29e0bf2bee8186076a06f3802b07e8'
TOP='stream27_signed_boundary_probe'
BENCH='rtl/tb/stream27_signed_boundary.cpp'
COMPILED=['rtl/kernel/genefer_digit_reduce27_pipe.sv',
          'rtl/kernel/genefer_stream27_signed_boundary_reduce27_pipe.sv','rtl/tb/'+TOP+'.sv']
EXTRA=[RUNNER,BENCH,COMPILED[-1],'reference/stream27_signed_boundary_vectors.py','tests/test_stream27_signed_boundary_native.py']
VECTOR_SHA={5:'c2208723b1ec08ca955810865588c008070e3390a6004734f9ef861c40ae64fe',
            16:'6066596729a9a1fa9650859d2e343719134eb7abb5553cba8f5c7ff1388e63ec'}
KEYS=('aw','blocks','events','accepted','responses','errors','bubbles','resets','output_idle','before_checks','edge_checks','field_checks')
GIB=1<<30;MIB=1<<20


def require(ok,why):
    if not ok:raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def load_infrastructure(root):
    path=root/INFRA;require(sha(path)==INFRA_SHA,'frozen tiny resource helper')
    spec=importlib.util.spec_from_file_location('_sbred_frozen_native_infrastructure',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    require(Path(module.__file__).resolve()==path.resolve(),'infrastructure path')
    return module


def source_pins(root):
    root=Path(root).resolve();require(sha(root/SOURCE)==SOURCE_SHA,'source receipt')
    receipt=json.loads((root/SOURCE).read_text())
    pins={**receipt['source_sha256'],SOURCE:SOURCE_SHA,INFRA:INFRA_SHA,
        'reference/__init__.py':'1c6df6d638965f2bc1c163f4e66f7f9038ebedc21e2139988aa5962c0ed47efb'}
    for name in EXTRA:pins[name]=sha(root/name)
    for name,value in pins.items():
        p=root/name;require(not Path(name).is_absolute() and '..' not in Path(name).parts and
            not p.is_symlink() and p.resolve().is_relative_to(root) and sha(p)==value,'closed source '+name)
    return pins


def load_project(root,pins):
    require(not any(n=='reference' or n.startswith('reference.') for n in sys.modules),'clean project namespace')
    require(source_pins(root)==pins and not any(p.suffix in ('.pyc','.so','.pyd') for p in (root/'reference').rglob('*')),'source-only bootstrap')
    sys.dont_write_bytecode=True;sys.path.insert(0,str(root))
    vectors=importlib.import_module('reference.stream27_signed_boundary_vectors')
    structure=importlib.import_module('reference.stream27_signed_boundary_structure');structure.validate(root)
    for name,module in tuple(sys.modules.items()):
        if name=='reference' or name.startswith('reference.'):
            path=Path(module.__file__).resolve();require(path.is_relative_to(root),'external project import')
            relative=str(path.relative_to(root));require(relative in pins and sha(path)==pins[relative],'unlisted project import')
    return vectors


def prepare(out):
    root=Path(__file__).resolve().parents[1];require(not (root/'docs/briefs/PAUSE').exists(),'advisor PAUSE')
    pins=source_pins(root);require(not out.exists(),'fresh stage');out.mkdir(parents=True)
    with tarfile.open(out/'source.tar.gz','x:gz') as tar:
        for name in sorted(pins):tar.add(root/name,arcname='fpga/'+name,recursive=False)
    require(source_pins(root)==pins,'source drift during staging')
    manifest=dict(status='prepared_not_executed',target=str(ROOT),top=TOP,sources=pins,archive_sha256=sha(out/'source.tar.gz'),
        supported_aw=[5,16],blocks=8,payload_w=16,fields=[104857601,69206017,67239937],latency=4,
        compiled=COMPILED,bench=BENCH,vector_sha256={str(k):v for k,v in VECTOR_SHA.items()},
        limits=dict(cpus=[4,6],cpu_quota=2,memory_bytes=4*GIB,command_seconds=300,total_seconds=900),
        limitation='One AW per invocation; all3 fields. No native result, compiled mutations, field integration or physical clock claim.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(files=len(pins),manifest_sha256=sha(out/'manifest.json'),archive_sha256=sha(out/'source.tar.gz'))))
    return manifest


def verify_manifest(root,path,digest,aw):
    require(type(aw) is int and aw in (5,16),'exact AW5/AW16')
    require(re.fullmatch('[0-9a-f]{64}',digest) and sha(path)==digest,'approved manifest SHA')
    m=json.loads(path.read_text());pins=source_pins(root)
    require(m['status']=='prepared_not_executed' and m['target']==str(ROOT) and m['top']==TOP and m['sources']==pins and
        m['supported_aw']==[5,16] and m['blocks']==8 and m['payload_w']==16 and m['fields']==[104857601,69206017,67239937] and
        m['latency']==4 and m['compiled']==COMPILED and m['bench']==BENCH and
        m['vector_sha256']=={str(k):v for k,v in VECTOR_SHA.items()} and
        m['limits']==dict(cpus=[4,6],cpu_quota=2,memory_bytes=4*GIB,command_seconds=300,total_seconds=900),'exact staged gate contract')
    return m,pins


def check_output(output,expected):
    lines=re.findall(r'^SIGNED_BOUNDARY_PASS (.*)$',output,re.M);require(len(lines)==1,'one typed footer')
    pairs=[word.split('=',1) for word in lines[0].split()]
    require(all(len(pair)==2 for pair in pairs) and len({pair[0] for pair in pairs})==len(pairs),'unique footer fields')
    actual={k:int(v) for k,v in pairs};require(actual=={k:expected[k] for k in KEYS},'all output/edge counters')
    return actual


def execute(aw,out,path,digest):
    require(__debug__ and socket.gethostname()=='aethia','aethia with assertions only')
    root=Path(__file__).resolve().parents[1];require(root==ROOT and root.resolve()==ROOT,'fixed isolated snapshot')
    require(out.resolve().parent==DESTINATION and not out.exists(),'fresh result path')
    manifest,pins=verify_manifest(root,path,digest,aw);infra=load_infrastructure(root);vectors=load_project(root,pins)
    require(infra.LOCK.is_file() and infra.LOCK.resolve()==infra.LOCK,'shared compile lock')
    limits=infra.execution_limits();resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(4*GIB,4*GIB))
    out.mkdir();scratch=Path(tempfile.mkdtemp(prefix='gfn16-sbred-',dir='/dev/shm'));os.chmod(scratch,0o700)
    temporary=scratch/'tmp';temporary.mkdir();started=time.monotonic()
    report=dict(status='running',aw=aw,blocks=8,fields=manifest['fields'],payload_w=16,latency=4,top=TOP,
        sources=pins,manifest_sha256=digest,limits=limits,compile_workers=2,model_threads=1,compiled=COMPILED,bench=BENCH,
        steps=[],artifacts={},scratch=str(scratch),command_timeout_seconds=300,total_budget_seconds=900,lock_wait_seconds=300,
        scratch_reservation_bytes=256*MIB,scratch_free_floor_bytes=2*GIB,durable_reservation_bytes=32*MIB,durable_free_floor_bytes=10*GIB,
        host_memory_floor_bytes=4*GIB,cleanup='All scratch and failed evidence retained; no deletion.',
        limitation='One AW/all3-field signed reduction component only; no compiled mutation, whole field/core or clock claim.')
    def remember(p):report['artifacts'][str(p.relative_to(out))]=sha(p)
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def guard():
        require(time.monotonic()-started<900,'total time budget')
        require(shutil.disk_usage(scratch).free>=2*GIB+max(0,256*MIB-infra.allocated(scratch)),'tmpfs reservation/floor')
        require(shutil.disk_usage(out).free>=10*GIB+max(0,32*MIB-infra.allocated(out)),'durable reservation/floor')
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=4*GIB,'host memory floor')
    def recheck():require(verify_manifest(root,path,digest,aw)[1]==pins,'source drift')
    env={k:v for k,v in os.environ.items() if k not in ('MAKEFLAGS','MFLAGS','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS','CC','CXX',
        'AR','OBJCACHE','OPT_FAST','OPT_SLOW','OPT_GLOBAL','TMPDIR','TMP','TEMP') and not k.startswith('NTT_')}
    env.update(TMPDIR=str(temporary),TMP=str(temporary),TEMP=str(temporary),CCACHE_DISABLE='1')
    def run(name,argv):
        guard();recheck();log=out/(name+'.log');begin=time.monotonic();failure=None
        with log.open('x') as stream:
            child=subprocess.Popen(argv,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while child.poll() is None:guard();require(time.monotonic()-begin<300,'command timeout');time.sleep(.25)
            except BaseException as error:
                failure=error
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                child.wait()
        remember(log);report['steps'].append(dict(name=name,command=argv,returncode=child.returncode,seconds=time.monotonic()-begin,
            log=log.name,sha256=sha(log),error=repr(failure) if failure else None));save()
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
        remember(out/'sources.tar.gz');text,expected=vectors.corpus(aw)
        require(expected['sha256']==VECTOR_SHA[aw] and expected['typed_coverage']['reset_ages']==31 and
            expected['typed_coverage']['negative_zero_inputs']>0 and expected['typed_coverage']['int_min_rejections']>0,'frozen typed corpus')
        vector=out/'vectors.txt';vector.write_text(text);remember(vector);report['vectors']=expected
        require(sha(vector)==VECTOR_SHA[aw],'durable vector identity')
        build=scratch/'build';command=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
            f'-GAW={aw}','-CFLAGS',f'-std=c++17 -Werror=return-type -DSBRED_AW={aw}','--Mdir',str(build),
            *[str(root/name) for name in COMPILED],str(root/BENCH)]
        with infra.LOCK.open('r') as lock:
            deadline=time.monotonic()+300
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:guard();require(time.monotonic()<deadline,'compile lock timeout');time.sleep(.25)
            run('build',command)
        exe=build/('V'+TOP);zipped=out/'model.gz';report['executable']=str(exe)
        report['executable_identity']=infra.archive_executable(exe,zipped);remember(zipped)
        generated={p.name:sha(p) for p in build.iterdir() if p.is_file() and p.suffix in ('.cpp','.h','.mk','.dat')}
        with tarfile.open(out/'generated-sources.tar.gz','x:gz') as tar:
            for name in sorted(generated):tar.add(build/name,arcname=name,recursive=False)
        report['generated_source_sha256']=generated;remember(out/'generated-sources.tar.gz')
        report['probe']=infra.check_probe(run('probe',[str(exe),'--runtime-probe']))
        report['coverage']=check_output(run('test',[str(exe),str(vector)]),expected)
        guard();recheck();require(sha(exe)==report['executable_identity']['executable_sha256'],'native model drift')
        with gzip.open(zipped,'rb') as f:require(hashlib.file_digest(f,'sha256').hexdigest()==sha(exe),'durable executable identity')
        require(all(sha(out/name)==value for name,value in report['artifacts'].items()),'artifact drift')
        require(all(sha(p)==value for p,value in report['tool_sha256'].items()),'toolchain drift')
        report['status']='passed_signed_boundary_component_profile'
    except BaseException as error:report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:save()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',type=Path);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--aw',type=int,choices=(5,16));parser.add_argument('--output',type=Path);parser.add_argument('--manifest',type=Path);parser.add_argument('--manifest-sha')
    args=parser.parse_args()
    if args.prepare:
        require(not args.execute and args.aw is None and not any((args.output,args.manifest,args.manifest_sha)),'exclusive prepare mode')
        prepare(args.prepare.resolve())
    else:
        require(args.execute and args.aw and args.output and args.manifest and args.manifest_sha,'explicit single-profile execution')
        execute(args.aw,args.output.resolve(),args.manifest.resolve(),args.manifest_sha)
