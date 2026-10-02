"""Prepare a paired host-memory gate; explicit reviewed execution is aethia-only.

The plan is source provenance, NOT launch authorization. No project imports or
NTT transforms. One selected profile/build at a time; strict typed normal and
assertion results. All failed attempts/scratch are preserved.
"""
import argparse
import fcntl
import hashlib
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

TOP='host_broadcast_memory_pair'
SOURCE=Path('/home/jtl/gfn-fpga-lab/agent-work/host-broadcast-memory/snapshot-v1/fpga')
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
PLAN='synthesis/host_broadcast_memory_pair_plan.json'
PLAN_SHA='2815d1602fbb99cf2964ea5a16fe991851cf272d7bf54862eb0b6b3b977d6332'
PROOF='reference/core27_prefetch_r2_host_broadcast_structure.py'
PROOF_SHA='daab10e0e5b4d5976ec4f36beef2e1d8dc926b16af54a021d67212b3f8a55d8a'
ORACLE='reference/host_broadcast_memory_oracle.py'
ORACLE_SHA='4b819c0a8ac0bb4e5ad3b1202a24ac5f04c1d9b8d639c6f8a24116552485d2ff'
# Independently derived by the pinned pure host transaction oracle, not RTL.
COUNT_KEYS=('edges','read_words','written_words','vector_reads','vector_writes','masked_poison',
            'clipped','descriptor_errors','profile_checks','busy_checks','quarters','halves')
COUNTS={aw:dict(zip(COUNT_KEYS,values)) for aw,values in {
    1:(1273,225,403,143,265,134,1797,526,6,2,1,1),
    5:(1558,938,1261,85,153,220,226,728,6,2,3,1),
    8:(3656,3970,2021,162,197,1284,73,806,6,2,15,3),
    16:(611608,881483,279608,28745,28764,311364,68,799,6,2,15,3),
}.items()}
FIELDS=((104857601,4190109697),(69206017,4225761281),(67239937,4227727361))
PROFILES={(8,1),(1,1),(5,1),(8,2),(8,3),(16,1)}
COVERAGE_NOTE=('Historical source plan retained unchanged. Later local runner review also permits AW16/P1 '
               'preparation explicitly with --aw 16. First invocation remains AW8/P1; full-width execution '
               'requires its own approved manifest after smoke completion and resource review. No autonomous launch.')
FOOTER_KEYS=('aw','p','edges','read_words','written_words','vector_reads','vector_writes',
             'masked_poison','clipped','descriptor_errors','profile_checks','busy_checks','quarters','halves')
CHILD='genefer_ntt_banked27_prefetch_r2_engine'
CHILD_LINE=395
GiB=1<<30;MiB=1<<20


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def profile(aw,field):
    require(type(aw) is int and type(field) is int and (aw,field) in PROFILES,'unsupported reviewed host-only profile')
    p,q=FIELDS[field-1];return dict(aw=aw,field=field,p=p,q=q)


def expected_counts(aw,field):
    config=profile(aw,field)
    require(aw in COUNTS and ORACLE_SHA is not None,'independent counter review pending; preparation blocked')
    return dict(aw=aw,p=config['p'],**COUNTS[aw])


def check_normal(returncode,text,aw,field):
    require(type(returncode) is int and returncode==0,'normal process failed')
    match=re.fullmatch('PASS '+TOP+' '+' '.join(key+r'=(\d+)' for key in FOOTER_KEYS)+r'\n?',text)
    require(match is not None,'exact normal coverage footer')
    actual=dict(zip(FOOTER_KEYS,map(int,match.groups())))
    require(actual==expected_counts(aw,field),'independent deterministic counter mismatch')
    return actual


def illegal_cases(aw):
    require(type(aw) is int and aw in (1,5,8,16),'illegal-subprocess geometry')
    return [(instance,kind,payload,quarter) for instance in ('baseline','candidate')
            for kind in ('scalar','vector') for payload in ('p','highbit','u32max')
            for quarter in ([0] if kind=='scalar' else range(min(4,((1<<aw)+15)//16)))]


def assertion_rejection(returncode,text,case):
    if type(returncode) is not int or returncode not in (1,-6,134):return False
    instance,kind,payload,quarter=case
    if instance not in ('baseline','candidate') or kind not in ('scalar','vector') or payload not in ('p','highbit','u32max') or type(quarter) is not int or not 0<=quarter<4:return False
    lines=[line for line in text.splitlines() if line]
    marker=f'EXPECT_CANONICAL_ASSERT instance={instance} kind={kind} payload={payload} quarter={quarter}'
    if not lines or lines.pop(0)!=marker:return False
    filename=r'(?:'+re.escape(str(SOURCE/'rtl/kernel'))+r'/)?'+re.escape(CHILD)+r'\.sv'
    location=filename+':'+str(CHILD_LINE)
    number=0 if instance=='baseline' else 1
    hierarchy=f'TOP.{TOP}.instances[{number}].{instance}.dut.child.memories[{quarter*16}]'
    primary=(r'\[\d+\] %(?:Error|Fatal): '+location+r': Assertion failed in '+re.escape(hierarchy)+
             r': noncanonical NTT27 data write')
    if not lines or re.fullmatch(primary,lines.pop(0)) is None:return False
    if lines and re.fullmatch(r'%Error: '+location+r': Verilog \$stop',lines[0]):lines.pop(0)
    if lines and lines[0]=='Aborting...':lines.pop(0)
    return not lines


def check_probe(text,config):
    actual=json.loads(text)
    wanted=dict(context_threads=1,model_threads=1,aw=config['aw'],p=config['p'],q=config['q'])
    require(actual==wanted and all(type(value) is int for value in actual.values()),'compiled parameter/thread probe')


def source_pins(root):
    require(not (root/PLAN).is_symlink() and sha(root/PLAN)==PLAN_SHA,'approved source plan identity')
    plan=json.loads((root/PLAN).read_text());order=plan['compile_contract']['source_order']
    require(plan['top']==TOP and len(order)==10 and len(set(order))==10 and set(order)==set(plan['source_sha256']),'ten-source compiled closure')
    pins=dict(plan['source_sha256'])
    require(ORACLE_SHA is not None,'counter oracle review pending')
    pins.update({PLAN:PLAN_SHA,PROOF:PROOF_SHA,ORACLE:ORACLE_SHA})
    for name,h in pins.items():
        path=root/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and not path.is_symlink() and
                path.resolve().is_relative_to(root.resolve()) and sha(path)==h,'pinned source changed: '+name)
    marker='$fatal(1,"noncanonical NTT27 data write");'
    child=(root/'rtl/kernel'/(CHILD+'.sv')).read_text().splitlines()
    require(marker in child[CHILD_LINE-1] and sum(marker in line for line in child)==1,'assertion source line/identity')
    runner='reference/host_broadcast_memory_pair_regression.py';pins[runner]=sha(root/runner)
    return plan,order,pins


def compile_command(root,build,config,order):
    aw,p,q=config['aw'],config['p'],config['q']
    flags=f'-std=c++17 -DHOST_BROADCAST_AW={aw} -DHOST_BROADCAST_P={p}u -DHOST_BROADCAST_Q={q}u'
    return ['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',TOP,
            f'-GAW={aw}',f'-GP={p}',f'-GQ={q}','-CFLAGS',flags,'--Mdir',str(build),*[str(root/name) for name in order]]


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
    require(len(cpu)==2 and cpu[0]!='max' and 0<int(cpu[0])<=2*int(cpu[1]),'<=200% aggregate CPU')
    affinity=sorted(os.sched_getaffinity(0));require(affinity==[0,2],'reviewed CPU0/2 allocation')
    cores=[]
    for number in affinity:
        topology=Path(f'/sys/devices/system/cpu/cpu{number}/topology')
        cores.append(tuple(int((topology/key).read_text()) for key in ('physical_package_id','core_id')))
    require(len(set(cores))==2,'distinct physical CPUs')
    return dict(cgroup=group,memory_max_bytes=int(memory),cpu_max=cpu,affinity=affinity,physical_cores=cores)


def prepare(out,aw=8,field=1):
    root=Path(__file__).resolve().parents[1];config=profile(aw,field);counts=expected_counts(aw,field)
    _,order,pins=source_pins(root);out.mkdir(parents=True,exist_ok=False)
    with tarfile.open(out/'sources.tar.gz','x:gz') as tar:
        for name in pins:tar.add(root/name,arcname='fpga/'+name,recursive=False)
    manifest=dict(status='prepared_not_executed',source_root=str(SOURCE),sources=pins,plan_sha256=PLAN_SHA,
                  compiled_source_order=order,profile=config,expected_counts=counts,archive_sha256=sha(out/'sources.tar.gz'),
                  runner_coverage_annotation=COVERAGE_NOTE,
                  limitation='Source preparation is not authorization to transfer or launch; standalone host-memory equivalence only.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest


def execute(out,manifest_path,manifest_sha,aw=8,field=1):
    require(__debug__ and socket.gethostname()=='aethia','explicit aethia execution with assertions')
    root=Path(__file__).resolve().parents[1]
    require(root==SOURCE and root.resolve()==SOURCE and LOCK.resolve()==LOCK and LOCK.is_file(),'fixed source snapshot/compile lock')
    require(re.fullmatch('[0-9a-f]{64}',manifest_sha) and sha(manifest_path)==manifest_sha,'explicit reviewed manifest SHA')
    manifest=json.loads(manifest_path.read_text());config=profile(aw,field);_,order,pins=source_pins(root)
    require(manifest['status']=='prepared_not_executed' and manifest['source_root']==str(SOURCE) and
            manifest['sources']==pins and manifest['plan_sha256']==PLAN_SHA and manifest['compiled_source_order']==order and
            manifest['profile']==config and manifest['expected_counts']==expected_counts(aw,field) and
            manifest['runner_coverage_annotation']==COVERAGE_NOTE,'approved preparation/profile mismatch')
    require(out.resolve().parent==SOURCE.parent.parent and not out.exists(),'fresh isolated durable evidence')
    limits=execution_limits();resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(6*GiB,6*GiB))
    out.mkdir();scratch=Path(tempfile.mkdtemp(prefix='gfn16-host-broadcast-memory-',dir='/dev/shm'));os.chmod(scratch,0o700)
    tmp=scratch/'tmp';tmp.mkdir()
    report=dict(status='running',scope='Standalone paired host-memory equivalence; no completed NTT operation',
                profile=config,sources=pins,compiled_source_order=order,manifest_sha256=manifest_sha,plan_sha256=PLAN_SHA,
                runner_coverage_annotation=COVERAGE_NOTE,
                limits=limits,scratch=str(scratch),compiler_temporary_directory=str(tmp),steps=[],artifacts={},
                expected_counts=expected_counts(aw,field),normal_counts=None,illegal_cases=[list(c) for c in illegal_cases(aw)],
                compile_workers=2,model_threads=1,scratch_reservation_bytes=768*MiB,scratch_free_floor_bytes=2*GiB,
                durable_reservation_bytes=64*MiB,durable_free_floor_bytes=10*GiB,host_memory_floor_bytes=4*GiB,
                command_timeout_seconds=1800,lock_wait_timeout_seconds=1800,cleanup='Nothing deleted; preserve failed evidence and scratch.')
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def remember(path):report['artifacts'][str(path.relative_to(out))]=sha(path)
    def recheck():require(source_pins(root)[2]==pins,'source drift')
    def guard():
        require(shutil.disk_usage(out).free>=10*GiB+max(0,64*MiB-allocated(out)),'durable reservation/floor')
        require(shutil.disk_usage(scratch).free>=2*GiB+max(0,768*MiB-allocated(scratch)),'tmpfs reservation/floor')
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=4*GiB,'host memory floor')
    env={k:v for k,v in os.environ.items() if k not in ('MAKEFLAGS','MFLAGS','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS',
        'CC','CXX','AR','OBJCACHE','OPT_FAST','OPT_SLOW','OPT_GLOBAL','TMPDIR','TMP','TEMP') and not k.startswith('NTT_')}
    env.update(TMPDIR=str(tmp),TMP=str(tmp),TEMP=str(tmp))
    def run(name,command,assert_case=None):
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
        remember(log);text=log.read_text()
        report['steps'].append(dict(name=name,command=command,returncode=process.returncode,error=repr(failure) if failure else None,
            seconds=time.monotonic()-begin,log=log.name,sha256=sha(log),assertion_case=list(assert_case) if assert_case else None));save()
        if failure:raise failure
        require(process.returncode==0 if assert_case is None else assertion_rejection(process.returncode,text,assert_case),'unexpected process result: '+name)
        guard();return process.returncode,text
    try:
        guard();recheck();save()
        paths=[Path(sys.executable).resolve()]
        for tool in ('g++','verilator'):
            found=shutil.which(tool);require(found is not None,'missing tool: '+tool);paths.append(Path(found).resolve())
        report['tool_executable_sha256']={str(p):sha(p) for p in paths};report['python_version']=sys.version
        for tool in ('verilator','g++'):_,report[tool+'_version']=run(tool+'-version',[tool,'--version'])
        shutil.copyfile(manifest_path,out/'approved-manifest.json');remember(out/'approved-manifest.json')
        shutil.copyfile(root/PLAN,out/'source-plan.json');remember(out/'source-plan.json')
        with tarfile.open(out/'sources.tar.gz','x:gz') as tar:
            for name in pins:tar.add(root/name,arcname=name,recursive=False)
        remember(out/'sources.tar.gz');build=scratch/'build'
        with LOCK.open('r') as lock:
            deadline=time.monotonic()+1800
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:guard();require(time.monotonic()<deadline,'bounded compiler lock wait');time.sleep(1)
            recheck();run('build',compile_command(root,build,config,order))
        exe=out/('V'+TOP);shutil.copy2(build/exe.name,exe);remember(exe)
        require(sha(exe)==sha(build/exe.name),'durable executable copy')
        report['executable_sha256']=sha(exe);report['executable']=str(exe)
        generated={p.name:sha(p) for p in build.iterdir() if p.is_file() and p.suffix in ('.cpp','.h','.mk','.dat')}
        with tarfile.open(out/'generated-sources.tar.gz','x:gz') as tar:
            for name in sorted(generated):tar.add(build/name,arcname=name,recursive=False)
        report['generated_source_sha256']=generated;remember(out/'generated-sources.tar.gz')
        _,probe=run('probe',[str(exe),'--runtime-probe']);check_probe(probe,config)
        rc,normal=run('normal',[str(exe)]);report['normal_counts']=check_normal(rc,normal,aw,field);save()
        for case in illegal_cases(aw):
            name='reject-'+'-'.join(map(str,case));run(name,[str(exe),'--illegal',*map(str,case)],case)
        recheck();guard();require(all(sha(out/name)==h for name,h in report['artifacts'].items()),'durable artifact drift')
        require(all(sha(p)==h for p,h in report['tool_executable_sha256'].items()),'tool identity drift')
        report.update(status='passed_host_memory_pair',limitation='One AW/field host-memory/profile/abort profile; no completed arithmetic/NTT transform, integrated core, timing/resource or PRP qualification.')
    except BaseException as error:report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:save()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare',type=Path);mode.add_argument('--execute',action='store_true')
    parser.add_argument('--aw',type=int,default=8);parser.add_argument('--field',type=int,default=1)
    parser.add_argument('--output',type=Path);parser.add_argument('--manifest',type=Path);parser.add_argument('--manifest-sha')
    args=parser.parse_args()
    if args.prepare:
        require(args.output is None and args.manifest is None and args.manifest_sha is None,'prepare-only arguments')
        print(json.dumps(prepare(args.prepare.resolve(),args.aw,args.field),indent=2))
    else:
        require(args.output and args.manifest and args.manifest_sha,'explicit execute paths and approved manifest hash')
        execute(args.output.resolve(),args.manifest.resolve(),args.manifest_sha,args.aw,args.field)
