"""Prepare or explicitly run one bounded baseline/candidate recurrence pair.

Standard-library bootstrap verifies the approved source closure before any
project import. Preparation is local source/vector work, never a dispatch.
"""
import argparse
import fcntl
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

TOP='root_recurrence27_periodmask_pair'
RUNNER='reference/root_recurrence27_periodmask_pair_regression.py'
SOURCE=Path('/home/jtl/gfn-fpga-lab/agent-work/root-recurrence27-periodmask-pair/snapshot-v1/fpga')
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
GiB=1<<30;MiB=1<<20
FIELDS=((104857601,4190109697),(69206017,4225761281),(67239937,4227727361))
ORDER=('rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv',
       'rtl/kernel/genefer_root_recurrence27.sv',
       'rtl/kernel/genefer_root_recurrence27_periodmask.sv',
       'rtl/tb/'+TOP+'.sv','rtl/tb/'+TOP+'_threaded.cpp')
FIXED_PINS={
    "reference/__init__.py": "1c6df6d638965f2bc1c163f4e66f7f9038ebedc21e2139988aa5962c0ed47efb",
    "reference/prefetch_r2_periodmask_structure.py": "0bbe6b7fd08a8c00bcce437a10b1717b2ed16a11436ca8c7dc4846db34ef9dd1",
    "reference/root_recurrence27_periodmask_pair_structure.py": "d6f0c549b7b63beb6faeecab4801c5e1a43f619cebb5cb33e575498f4e55846e",
    "reference/root_recurrence27_periodmask_vectors.py": "fda0ee345cb1fe5577014fe32aaf98061a9964590c4b0b2eb146b1c5e1dc5a45",
    "reference/root_recurrence_proof.py": "41136efa238fed74562977010f4c91dcb073b779333400b243c48c26680f6cda",
    "rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv": "501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b",
    "rtl/kernel/genefer_ntt_banked27_prefetch_r2_engine.sv": "552d273972af97c3363b77df0798e08a962d283869bcc95159f378a0f0070b17",
    "rtl/kernel/genefer_ntt_banked27_prefetch_r2_host_broadcast_engine.sv": "0960922332ea919a72a1ee591a70006bba76af7f26bc5308b68f50e327583e29",
    "rtl/kernel/genefer_ntt_banked27_prefetch_r2_host_broadcast_periodmask_engine.sv": "ae4567612a881974577e38ff2099a0187d07a5d44ba8c34a821d696148893ba8",
    "rtl/kernel/genefer_ntt_banked27_prefetch_r2_periodmask_engine.sv": "99b56338e2d73fbb3592a72040a5919a718cd9fbec742493c2e83fbcf5624cb9",
    "rtl/kernel/genefer_root_recurrence27.sv": "c8adc265915192807efee46799a782f1649a4408313098baaed8b4a808afeb9e",
    "rtl/kernel/genefer_root_recurrence27_periodmask.sv": "47d9f7e0db2c784424d4b148760f4235baeffef08969c4e790eb3c1e32a3e389",
    "rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast.sv": "ea2b518880cb1c3191c71d35a232d2483aee82046ecd4d930d7ac7ffa07a80e1",
    "rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_periodmask.sv": "3fd005dfded5917f879b7d402228f2b32759324160e81e66bee309bf184e474b",
    "rtl/tb/root_recurrence27.cpp": "3e98fcb127349740c9fc0368ef43d557af5ca879d37887afa865ca8722ddce90",
    "rtl/tb/root_recurrence27_periodmask.cpp": "ed1ae516d8ada0d8381a07d5b261b09e92cc0c0dd926ac6b813a842494a86fae",
    "rtl/tb/root_recurrence27_periodmask_pair.cpp": "2101bf21f39c50064fbb129ff12908170c123c01204277c5fe65c5b1276fd629",
    "rtl/tb/root_recurrence27_periodmask_pair.sv": "88c5bf5125e6b0717fdec46ef638dc4cbe5c06db7952be6956e79b8ba57956c0",
    "rtl/tb/root_recurrence27_periodmask_pair_threaded.cpp": "be4e569d7ae94f075b0ba7a50d64744b156fe7f72e0bf8a285d53bd62053e173"
}
FOOTER_KEYS=('lanes','cases','runs','responses','checked_cycles','bubbles','seed_checks','aborts','rejects','pair_checks')


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def profile(lanes,field):
    require(type(lanes) is int and lanes in (16,64) and type(field) is int and field in (1,2,3),'explicit supported lane/field profile')
    p,q=FIELDS[field-1];return dict(lanes=lanes,field=field,p=p,q=q,tag_width=32)


def source_pins(root):
    root=Path(root).resolve();pins=dict(FIXED_PINS);pins[RUNNER]=sha(root/RUNNER)
    for name,digest in pins.items():
        path=root/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and not path.is_symlink() and
                path.resolve().is_relative_to(root) and sha(path)==digest,'pinned source changed: '+name)
    return pins


def load_project(root,pins,isolated=False):
    root=Path(root).resolve()
    require(source_pins(root)==pins,'pre-import source drift')
    if isolated:
        require(not __package__ and not any(n=='reference' or n.startswith('reference.') for n in sys.modules),'direct execution before project imports')
        require(not any(p.suffix in ('.pyc','.so','.pyd') for p in (root/'reference').rglob('*')),'source-only snapshot')
    sys.dont_write_bytecode=True;sys.pycache_prefix=None;sys.path.insert(0,str(root))
    structure=importlib.import_module('reference.root_recurrence27_periodmask_pair_structure')
    vectors=importlib.import_module('reference.root_recurrence27_periodmask_vectors')
    for name,module in tuple(sys.modules.items()):
        if name=='reference' or name.startswith('reference.'):
            path=Path(module.__file__).resolve()
            require(path.is_relative_to(root),'project import outside snapshot')
            relative=str(path.relative_to(root))
            require(relative in pins and sha(path)==pins[relative],'unlisted imported module: '+name)
    structure.validate_files(root)
    return vectors


def check_probe(text,config):
    actual=json.loads(text);wanted=dict(context_threads=1,model_threads=1,lanes=config['lanes'],p=config['p'],q=config['q'])
    require(actual==wanted and all(type(value) is int for value in actual.values()),'compiled model/context/parameter probe')
    return actual


def check_normal(text,config,coverage):
    match=re.fullmatch('PASS '+' '.join(key+r'=(\d+)' for key in FOOTER_KEYS)+r'\n?',text)
    require(match is not None,'exact component footer')
    row=dict(zip(FOOTER_KEYS,map(int,match.groups())))
    wanted=dict(lanes=config['lanes'],cases=coverage['case_count'],runs=coverage['runs'],
                responses=coverage['responses'],aborts=coverage['aborts'],rejects=coverage['rejects'])
    require(all(row[key]==value for key,value in wanted.items()),'complete case/response/reset/rejection coverage')
    require(row['checked_cycles']==row['responses']+row['bubbles']+4*row['runs'],'exact per-run drain cycle accounting')
    require(row['bubbles']>0 and row['seed_checks']>0 and row['pair_checks']>=2*row['checked_cycles'],'bubbles/seed/paired-output coverage')
    return row


def compile_command(root,build,config):
    flags=f"-std=c++17 -DTEST_LANES={config['lanes']} -DTEST_P={config['p']}u"
    return ['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
            f"-GLANES={config['lanes']}",f"-GP={config['p']}",f"-GQ={config['q']}",'-GTAG_W=32',
            '-CFLAGS',flags,'--Mdir',str(build),*[str(root/name) for name in ORDER]]


def verify_manifest(root,path,digest,config):
    require(re.fullmatch('[0-9a-f]{64}',digest) and sha(path)==digest,'externally approved manifest SHA')
    manifest=json.loads(path.read_text());pins=source_pins(root)
    require(manifest['status']=='prepared_not_executed' and manifest['source_root']==str(SOURCE) and
            manifest['sources']==pins and manifest['compiled_source_order']==list(ORDER) and
            manifest['profile']==config and manifest['top']==TOP,'approved source/profile contract')
    require(manifest['vectors']['case_count']==322 and manifest['vectors']['legal_periods']==[0]+[1<<i for i in range(17)],'full geometry/period suite')
    return manifest,pins


def prepare(out,lanes=64,field=1):
    require(__debug__,'assertions required for ordinary-integer oracle')
    root=Path(__file__).resolve().parents[1];config=profile(lanes,field);pins=source_pins(root)
    vectors=load_project(root,pins);out.mkdir(parents=True,exist_ok=False)
    coverage=vectors.write_vectors(out/'vectors.txt',lanes,field)
    require(source_pins(root)==pins,'preparation source drift')
    with tarfile.open(out/'source.tar.gz','x:gz') as tar:
        for name in pins:tar.add(root/name,arcname='fpga/'+name,recursive=False)
    manifest=dict(status='prepared_not_executed',source_root=str(SOURCE),sources=pins,
        compiled_source_order=list(ORDER),top=TOP,profile=config,vectors=coverage,
        archive_sha256=sha(out/'source.tar.gz'),
        limitation='Local source/vector preparation only. Explicit reviewed native dispatch required; standalone component, not whole-core or physical qualification.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def allocated(root):
    total=0
    for directory,_,names in os.walk(root):
        for name in names:
            try:total+=(Path(directory)/name).lstat().st_blocks*512
            except FileNotFoundError:continue
    return total


def execution_limits():
    group=next(line.split('::',1)[1] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
    directory=Path('/sys/fs/cgroup')/group.lstrip('/')
    memory=(directory/'memory.max').read_text().strip();cpu=(directory/'cpu.max').read_text().split()
    require(memory!='max' and 0<int(memory)<=6*GiB,'finite <=6GiB aggregate memory')
    require(len(cpu)==2 and cpu[0]!='max' and int(cpu[1])>0 and 0<int(cpu[0])<=2*int(cpu[1]),'<=200% aggregate CPU')
    affinity=sorted(os.sched_getaffinity(0));require(affinity==[0,2],'reviewed physical CPU0/2 allocation')
    cores=[]
    for number in affinity:
        topology=Path(f'/sys/devices/system/cpu/cpu{number}/topology')
        cores.append(tuple(int((topology/key).read_text()) for key in ('physical_package_id','core_id')))
    require(len(set(cores))==2,'distinct physical CPUs')
    return dict(cgroup=group,memory_max_bytes=int(memory),cpu_max=cpu,affinity=affinity,physical_cores=cores)


def execute(out,manifest_path,manifest_sha,lanes=64,field=1):
    require(__debug__ and socket.gethostname()=='aethia','explicit aethia execution with assertions')
    root=Path(__file__).resolve().parents[1]
    require(root==SOURCE and root.resolve()==SOURCE and LOCK.resolve()==LOCK and LOCK.is_file(),'fixed snapshot and shared compile lock')
    require(out.resolve().parent==SOURCE.parent.parent and not out.exists(),'fresh isolated durable output')
    config=profile(lanes,field);manifest,pins=verify_manifest(root,manifest_path,manifest_sha,config)
    vectors=load_project(root,pins,isolated=True);limits=execution_limits()
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(6*GiB,6*GiB))
    out.mkdir();scratch=Path(tempfile.mkdtemp(prefix='gfn16-periodmask-pair-',dir='/dev/shm'));os.chmod(scratch,0o700)
    tmp=scratch/'tmp';tmp.mkdir()
    report=dict(status='running',scope='Standalone baseline/candidate recurrence paired output and cycle equivalence',
        profile=config,top=TOP,sources=pins,compiled_source_order=list(ORDER),manifest_sha256=manifest_sha,
        limits=limits,scratch=str(scratch),compiler_temporary_directory=str(tmp),steps=[],artifacts={},
        compile_workers=2,model_threads=1,scratch_reservation_bytes=768*MiB,scratch_free_floor_bytes=2*GiB,
        durable_reservation_bytes=64*MiB,durable_free_floor_bytes=10*GiB,host_memory_floor_bytes=4*GiB,
        command_timeout_seconds=1800,lock_wait_timeout_seconds=1800,cleanup='Nothing deleted; retain failed evidence and scratch.',
        limitation='One component lane/field profile only. No whole-core integration, mutation qualification, FPGA fit, clock improvement or PRP claim.')
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def remember(path):report['artifacts'][str(path.relative_to(out))]=sha(path)
    def recheck():require(source_pins(root)==pins,'source drift')
    def guard():
        require(shutil.disk_usage(out).free>=10*GiB+max(0,64*MiB-allocated(out)),'durable reservation/floor')
        require(shutil.disk_usage(scratch).free>=2*GiB+max(0,768*MiB-allocated(scratch)),'tmpfs reservation/floor')
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=4*GiB,'host memory floor')
    env={k:v for k,v in os.environ.items() if k not in ('MAKEFLAGS','MFLAGS','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS',
        'CC','CXX','AR','OBJCACHE','OPT_FAST','OPT_SLOW','OPT_GLOBAL','TMPDIR','TMP','TEMP') and not k.startswith('NTT_')}
    env.update(TMPDIR=str(tmp),TMP=str(tmp),TEMP=str(tmp))
    def run(name,command):
        guard();log=out/(name+'.log');begin=time.monotonic();failure=None
        with log.open('x') as stream:
            process=subprocess.Popen(command,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while process.poll() is None:
                    guard();require(time.monotonic()-begin<1800,'command timeout');time.sleep(1)
            except BaseException as error:
                failure=error
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait()
        remember(log);report['steps'].append(dict(name=name,command=command,returncode=process.returncode,
            error=repr(failure) if failure else None,seconds=time.monotonic()-begin,log=log.name,sha256=sha(log)))
        save();print(name,process.returncode,flush=True)
        if failure:raise failure
        require(process.returncode==0,'command failed: '+name);guard();return log.read_text()
    try:
        guard();recheck();save()
        paths=[Path(sys.executable).resolve()]
        for tool in ('g++','verilator'):
            found=shutil.which(tool);require(found is not None,'missing tool: '+tool);paths.append(Path(found).resolve())
        report['tool_executable_sha256']={str(path):sha(path) for path in paths};report['python_version']=sys.version
        for tool in ('verilator','g++'):report[tool+'_version']=run(tool+'-version',[tool,'--version']).strip()
        shutil.copyfile(manifest_path,out/'approved-manifest.json');remember(out/'approved-manifest.json')
        with tarfile.open(out/'sources.tar.gz','x:gz') as tar:
            for name in pins:tar.add(root/name,arcname=name,recursive=False)
        remember(out/'sources.tar.gz')
        report['vectors']=vectors.write_vectors(out/'vectors.txt',lanes,field);remember(out/'vectors.txt')
        require(report['vectors']==manifest['vectors'],'regenerated independent vectors differ from approved bytes/coverage')
        guard();build=scratch/'build'
        with LOCK.open('r') as lock:
            deadline=time.monotonic()+1800
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:guard();require(time.monotonic()<deadline,'bounded compiler lock wait');time.sleep(1)
            recheck();run('build',compile_command(root,build,config))
        exe=out/('V'+TOP);shutil.copy2(build/exe.name,exe);remember(exe)
        require(sha(exe)==sha(build/exe.name),'durable executable copy');report['executable_sha256']=sha(exe);report['executable']=str(exe)
        generated={p.name:sha(p) for p in build.iterdir() if p.is_file() and p.suffix in ('.cpp','.h','.mk','.dat')}
        with tarfile.open(out/'generated-sources.tar.gz','x:gz') as tar:
            for name in sorted(generated):tar.add(build/name,arcname=name,recursive=False)
        report['generated_source_sha256']=generated;remember(out/'generated-sources.tar.gz')
        report['probe']=check_probe(run('probe',[str(exe),'--runtime-probe']),config)
        report['normal_counts']=check_normal(run('normal',[str(exe),str(out/'vectors.txt')]),config,report['vectors'])
        recheck();guard()
        require(all(sha(out/name)==digest for name,digest in report['artifacts'].items()),'durable artifact drift')
        require(all(sha(path)==digest for path,digest in report['tool_executable_sha256'].items()),'tool identity drift')
        report['status']='passed_component_pair'
    except BaseException as error:report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:save()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare',type=Path);mode.add_argument('--execute',action='store_true')
    parser.add_argument('--lanes',type=int,choices=(16,64),default=64);parser.add_argument('--field',type=int,choices=(1,2,3),default=1)
    parser.add_argument('--output',type=Path);parser.add_argument('--manifest',type=Path);parser.add_argument('--manifest-sha')
    args=parser.parse_args()
    if args.prepare:
        require(args.output is None and args.manifest is None and args.manifest_sha is None,'prepare-only arguments')
        result=prepare(args.prepare.resolve(),args.lanes,args.field)
        print(json.dumps(dict(status=result['status'],files=len(result['sources']),vector_sha256=result['vectors']['sha256'],
                             manifest_sha256=sha(args.prepare.resolve()/'manifest.json'),cases=result['vectors']['case_count']),indent=2))
    else:
        require(args.output and args.manifest and args.manifest_sha,'explicit execution paths and reviewed manifest SHA')
        execute(args.output.resolve(),args.manifest.resolve(),args.manifest_sha,args.lanes,args.field)
