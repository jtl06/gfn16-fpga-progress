"""Prepare or explicitly execute the first bounded rowcompact reset-probe batch.

Standard-library source bootstrap; no HDL tools during preparation. Frozen
probe/normal/proposal sources remain unchanged. This executor cannot launch the
remaining 56 cases or mutants; they require another reviewed batch.
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

TOP='rowcompact_reset_probe'
RUNNER='reference/rowcompact_reset_probe_regression.py'
TEST='tests/test_rowcompact_reset_probe_regression.py'
PROPOSAL='synthesis/rowcompact_reset_probe_dispatch_proposal.json'
PROPOSAL_SHA='3f41718866789929de7ca3ad97dd72e861da7b98712a29edf3d5849bf00a571a'
SOURCE=Path('/home/jtl/gfn-fpga-lab/agent-work/rowcompact-reset-probe/snapshot-v1/fpga')
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
GiB=1<<30;MiB=1<<20
BATCH=tuple(dict(kind=kind,variant=variant,age=age,bit=0)
            for kind in ('bf','mul') for variant in (0,1) for age in (0,6))
COUNTS=dict(bf=2097152,mul=196608,bf_nonzero=2093056,mul_nonzero=196224)
LIMITATION=('Eight targeted AW16/L64 reset cases at bit0, ages0/6 only, first forward DIF stage and initial rooted pre-MUL. '
            'Not the full64-case matrix, E7 committed-write, bit1, checker-sensitivity mutant, every-stage, physical or clock qualification.')


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def proposal(root):
    path=Path(root)/PROPOSAL
    require(not path.is_symlink() and sha(path)==PROPOSAL_SHA,'frozen dispatch proposal identity')
    return json.loads(path.read_text())


def source_pins(root):
    root=Path(root).resolve();p=proposal(root);pins=dict(p['sources'])
    pins.update({PROPOSAL:PROPOSAL_SHA,RUNNER:sha(root/RUNNER),TEST:sha(root/TEST)})
    require(len(pins)==68,'exact source closure')
    for name,digest in pins.items():
        path=root/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and not path.is_symlink() and
                path.resolve().is_relative_to(root) and sha(path)==digest,'pinned source changed: '+name)
    return pins


def load_project(root,pins,isolated=False):
    root=Path(root).resolve();require(source_pins(root)==pins,'pre-import source drift')
    if isolated:
        require(not __package__ and not any(n=='reference' or n.startswith('reference.') for n in sys.modules),
                'direct execution before project imports')
        require(not any(p.suffix in ('.pyc','.so','.pyd') for p in (root/'reference').rglob('*')),
                'source-only snapshot')
    sys.dont_write_bytecode=True;sys.pycache_prefix=None;sys.path.insert(0,str(root))
    structure=importlib.import_module('reference.rowcompact_reset_probe_structure')
    for name,module in tuple(sys.modules.items()):
        if name=='reference' or name.startswith('reference.'):
            path=Path(module.__file__).resolve()
            require(path.is_relative_to(root),'project import outside snapshot')
            relative=str(path.relative_to(root))
            require(relative in pins and sha(path)==pins[relative],'unlisted project import')
    structure.validate_files(root)
    require(all(case in structure.matrix() for case in BATCH) and structure.expected_counts()==COUNTS,
            'reviewed batch and shadow counters')
    return structure


def compile_command(root,build):
    p=proposal(root)
    return ['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
            '-GAW=16','-GNTT_LANES=64','-CFLAGS','-std=c++17 -Werror=return-type',
            '--Mdir',str(build),*[str(root/name) for name in p['compiled_source_order']]]


def check_probe(text):
    actual=json.loads(text);wanted=dict(context_threads=1,model_threads=1,aw=16,lanes=64)
    require(actual==wanted and all(type(value) is int for value in actual.values()),
            'compiled model/context/profile probe')
    return actual


def case_name(case):
    require(case in BATCH,'only first reviewed eight cases')
    return '{kind}-v{variant}-age{age}-bit{bit}'.format(**case)


def check_case(text,case):
    name=case_name(case);kind=case['kind'];variant=case['variant'];age=case['age']
    bank=(2 if variant==0 else 0) if kind=='bf' else 64*variant
    row=256 if kind=='bf' else 1;group=variant if kind=='bf' else 2+variant
    lines=text.splitlines();require(len(lines)==9,'exact single-case evidence line count')
    accept=re.fullmatch(f'ACCEPT kind={kind} variant={variant} bank={bank} row={row} group={group} edge=([0-9]+)',lines[0])
    require(accept is not None,'actual E0 target evidence')
    accept_edge=int(accept[1]);require(65536<accept_edge<200000,'bounded accepted request edge')
    pre=[]
    for field in range(3):
        match=re.fullmatch(f'PRE_RESET field={field} age={age} committed=0 bf_checks=([0-9]+) mul_checks=([0-9]+) bf_nonzero=([0-9]+) mul_nonzero=([0-9]+)',lines[1+field])
        require(match is not None,'each field target age and uncommitted classification')
        values=list(map(int,match.groups()))
        require(values[2]<=values[0] and values[3]<=values[1] and values[0]<=COUNTS['bf'] and values[1]<=COUNTS['mul'],
                'pre-reset shadow bounds')
        pre.append(dict(zip(COUNTS,values)))
    require(lines[4]=='RESET async=1 quiet_edges=8 writes=0','asynchronous reset and write quarantine')
    for field in range(3):
        require(lines[5+field]==f'SHADOW field={field} '+' '.join(f'{key}={value}' for key,value in COUNTS.items()),
                'exact per-field BF/MUL/nonzero shadow execution counts')
    match=re.fullmatch(f'PASS reset_probe kind={kind} variant={variant} age={age} bit=0 readbacks=65536 recovery_cycles=41708 edges=([0-9]+)',lines[8])
    require(match is not None,'full cold recovery and readback footer')
    edges=int(match[1])
    # Accepted E0 plus age advances, eight quiet edges, load+idle, start,
    # 41708 operation edges, 65536 readbacks and final idle.
    require(edges==accept_edge+age+172791 and edges<=500000,'exact post-accept edge accounting')
    return dict(case=name,accept_edge=accept_edge,edges=edges,pre_reset=pre,shadow_per_field=COUNTS,
                readbacks=65536,recovery_cycles=41708)


def verify_manifest(root,path,digest):
    require(re.fullmatch('[0-9a-f]{64}',digest) is not None and sha(path)==digest,'externally approved manifest SHA')
    manifest=json.loads(path.read_text());pins=source_pins(root);p=proposal(root)
    require(manifest['status']=='prepared_not_executed' and manifest['source_root']==str(SOURCE) and
            manifest['sources']==pins and manifest['compiled_source_order']==p['compiled_source_order'] and
            manifest['top']==TOP and manifest['batch']==list(BATCH) and manifest['eventual_matrix_cases']==64 and
            manifest['profile']==dict(aw=16,lanes=64,fields=3) and manifest['vector']==p['vector'] and
            manifest['proposal_sha256']==PROPOSAL_SHA,'approved snapshot/batch contract')
    return manifest,pins


def prepare(out):
    require(__debug__,'assertions required')
    root=Path(__file__).resolve().parents[1];pins=source_pins(root);p=proposal(root)
    load_project(root,pins);vector=root/p['vector']['path']
    require(not vector.is_symlink() and sha(vector)==p['vector']['sha256'],'frozen ordinary-integer vector identity')
    out.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(vector,out/'vectors-aw16.txt')
    require(sha(out/'vectors-aw16.txt')==p['vector']['sha256'],'staged vector identity')
    with tarfile.open(out/'source.tar.gz','x:gz') as tar:
        for name in pins:tar.add(root/name,arcname='fpga/'+name,recursive=False)
    require(source_pins(root)==pins,'preparation source drift')
    manifest=dict(status='prepared_not_executed',source_root=str(SOURCE),sources=pins,
        compiled_source_order=p['compiled_source_order'],top=TOP,profile=dict(aw=16,lanes=64,fields=3),
        proposal_sha256=PROPOSAL_SHA,batch=list(BATCH),eventual_matrix_cases=64,vector=p['vector'],
        archive_sha256=sha(out/'source.tar.gz'),limitation=LIMITATION,
        build_timeout_seconds=1800,case_timeout_seconds=300,batch_timeout_seconds=2400,
        full_matrix_qualified=False,mutant_sensitivity_qualified=False,native_reset_qualified=False)
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


def execute(out,manifest_path,manifest_sha):
    require(__debug__ and socket.gethostname()=='aethia','explicit aethia execution with assertions')
    root=Path(__file__).resolve().parents[1]
    require(root==SOURCE and root.resolve()==SOURCE and LOCK.resolve()==LOCK and LOCK.is_file(),'fixed snapshot and shared compile lock')
    require(out.resolve().parent==SOURCE.parent.parent and not out.exists(),'fresh isolated durable output')
    manifest,pins=verify_manifest(root,manifest_path,manifest_sha)
    load_project(root,pins,isolated=True);limits=execution_limits()
    vector=manifest_path.parent/'vectors-aw16.txt'
    require(not vector.is_symlink() and sha(vector)==manifest['vector']['sha256'],'approved vector payload')
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(6*GiB,6*GiB))
    out.mkdir();scratch=Path(tempfile.mkdtemp(prefix='gfn16-rowcompact-reset-probe-v1-',dir='/dev/shm'));os.chmod(scratch,0o700)
    tmp=scratch/'tmp';tmp.mkdir()
    report=dict(status='running',scope='Simulation-only first eight rowcompact targeted reset cases',
        profile=manifest['profile'],top=TOP,sources=pins,compiled_source_order=manifest['compiled_source_order'],manifest_sha256=manifest_sha,
        limits=limits,scratch=str(scratch),compiler_temporary_directory=str(tmp),steps=[],artifacts={},
        compile_workers=2,model_threads=1,scratch_reservation_bytes=768*MiB,scratch_free_floor_bytes=2*GiB,
        durable_reservation_bytes=64*MiB,durable_free_floor_bytes=10*GiB,host_memory_floor_bytes=4*GiB,
        build_timeout_seconds=1800,case_timeout_seconds=300,batch_timeout_seconds=2400,lock_wait_timeout_seconds=1800,cleanup='Nothing deleted; retain failed evidence and scratch.',
        limitation=LIMITATION,batch=list(BATCH),case_results=[],eventual_matrix_cases=64,
        full_matrix_qualified=False,mutant_sensitivity_qualified=False,native_reset_qualified=False)
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def remember(path):report['artifacts'][str(path.relative_to(out))]=sha(path)
    def recheck():
        require(source_pins(root)==pins,'source drift')
        require(sha(manifest_path)==manifest_sha and sha(vector)==manifest['vector']['sha256'],'approved input drift')
    def guard():
        require(shutil.disk_usage(out).free>=10*GiB+max(0,64*MiB-allocated(out)),'durable reservation/floor')
        require(shutil.disk_usage(scratch).free>=2*GiB+max(0,768*MiB-allocated(scratch)),'tmpfs reservation/floor')
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=4*GiB,'host memory floor')
    env={k:v for k,v in os.environ.items() if k not in ('MAKEFLAGS','MFLAGS','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS',
        'CC','CXX','AR','OBJCACHE','OPT_FAST','OPT_SLOW','OPT_GLOBAL','TMPDIR','TMP','TEMP') and not k.startswith('NTT_')}
    env.update(TMPDIR=str(tmp),TMP=str(tmp),TEMP=str(tmp))
    def run(name,command,timeout=1800,deadline=None):
        guard();log=out/(name+'.log');begin=time.monotonic();failure=None
        with log.open('x') as stream:
            process=subprocess.Popen(command,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while process.poll() is None:
                    guard();require(time.monotonic()-begin<timeout and (deadline is None or time.monotonic()<deadline),'command timeout');time.sleep(1)
            except BaseException as error:
                failure=error
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait()
        remember(log);report['steps'].append(dict(name=name,command=command,returncode=process.returncode,
            error=repr(failure) if failure else None,seconds=time.monotonic()-begin,log=log.name,sha256=sha(log)))
        save();print(name,process.returncode,flush=True)
        if failure:raise failure
        require(process.returncode==0,'command failed: '+name)
        require(time.monotonic()-begin<=timeout and (deadline is None or time.monotonic()<=deadline),'completed after command/batch deadline')
        guard();return log.read_text()
    try:
        guard();recheck();save()
        paths=[Path(sys.executable).resolve()]
        for tool in ('g++','verilator','verilator_bin','make'):
            found=shutil.which(tool);require(found is not None,'missing tool: '+tool);paths.append(Path(found).resolve())
        report['tool_executable_sha256']={str(path):sha(path) for path in paths};report['python_version']=sys.version
        for tool in ('verilator','g++'):report[tool+'_version']=run(tool+'-version',[tool,'--version']).strip()
        shutil.copyfile(manifest_path,out/'approved-manifest.json');remember(out/'approved-manifest.json')
        with tarfile.open(out/'sources.tar.gz','x:gz') as tar:
            for name in pins:tar.add(root/name,arcname=name,recursive=False)
        remember(out/'sources.tar.gz')
        shutil.copyfile(vector,out/'vectors-aw16.txt');remember(out/'vectors-aw16.txt')
        require(sha(out/'vectors-aw16.txt')==manifest['vector']['sha256'],'durable vector identity')
        guard();build=scratch/'build'
        with LOCK.open('r') as lock:
            deadline=time.monotonic()+1800
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:guard();require(time.monotonic()<deadline,'bounded compiler lock wait');time.sleep(1)
            recheck();run('build',compile_command(root,build))
        exe=out/('V'+TOP);shutil.copy2(build/exe.name,exe);remember(exe)
        require(sha(exe)==sha(build/exe.name),'durable executable copy');report['executable_sha256']=sha(exe);report['executable']=str(exe)
        generated={p.name:sha(p) for p in build.iterdir() if p.is_file() and p.suffix in ('.cpp','.h','.mk','.dat')}
        with tarfile.open(out/'generated-sources.tar.gz','x:gz') as tar:
            for name in sorted(generated):tar.add(build/name,arcname=name,recursive=False)
        report['generated_source_sha256']=generated;remember(out/'generated-sources.tar.gz')
        require(any('compact row write address mismatch' in (build/name).read_text(errors='replace')
                    for name in generated if name.endswith('.cpp')),'generated shadow guard diagnostic absent')
        report['probe']=check_probe(run('probe',[str(exe),'--runtime-probe'],timeout=30))
        deadline=time.monotonic()+2400
        for case in BATCH:
            recheck()
            require(time.monotonic()<deadline,'bounded eight-case batch deadline')
            command=[str(exe),str(out/'vectors-aw16.txt'),case['kind'],str(case['variant']),str(case['age']),str(case['bit'])]
            result=check_case(run(case_name(case),command,timeout=300,deadline=deadline),case)
            report['case_results'].append(result);save()
        require(len(report['case_results'])==8,'complete eight-case batch')
        recheck();guard()
        require(all(sha(out/name)==digest for name,digest in report['artifacts'].items()),'durable artifact drift')
        require(all(sha(path)==digest for path,digest in report['tool_executable_sha256'].items()),'tool identity drift')
        report['status']='passed_first_eight_targeted_reset_cases'
        report['listed_eight_reset_cases_qualified']=True
    except BaseException as error:report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:save()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',type=Path);mode.add_argument('--execute',action='store_true')
    parser.add_argument('--output',type=Path);parser.add_argument('--manifest',type=Path);parser.add_argument('--manifest-sha')
    args=parser.parse_args()
    if args.prepare:
        require(args.output is None and args.manifest is None and args.manifest_sha is None,'prepare-only arguments')
        result=prepare(args.prepare.resolve())
        print(json.dumps(dict(status=result['status'],files=len(result['sources']),cases=len(result['batch']),
                              manifest_sha256=sha(args.prepare.resolve()/'manifest.json')),indent=2))
    else:
        require(args.output and args.manifest and args.manifest_sha,'explicit paths and reviewed manifest SHA')
        execute(args.output.resolve(),args.manifest.resolve(),args.manifest_sha)
