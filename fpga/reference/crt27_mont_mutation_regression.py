"""Separate G2 negative controls, fresh paired controls and canonical guards.

The frozen positive runner/bench/candidate are never edited. This successor
reuses the approved read-only million-case vectors without a durable copy.
Each required mutant is followed by a fresh source-matched passing build/run.
"""
import argparse
import fcntl
import hashlib
import io
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
import types

RUNNER='reference/crt27_mont_mutation_regression.py'
POSITIVE='reference/crt27_mont_regression.py'
POSITIVE_SHA='c1a2af418bd615d7af5e1d495d22b071dfbb2013022b8a92e96c03d7654c80aa'
POSITIVE_MANIFEST_SHA='814055f825fcafedc2caaf43ae8f034f0822eebdff562e8732d340d21fbc08a4'
POSITIVE_STAGE_ARCHIVE_SHA='9196801f0dadbfba0bfe5aa3aca7404dfb197b156df1c9da4d40e4da19edfc53'
POSITIVE_REPORT_SHA='0de1c9265012e430c3af8e1d4992538ba25f62c13021ed9eb7ab88dde980a3fd'
ANSWER='docs/briefs/2026-09-30-answers-B20260930.md'
ANSWER_SHA='1745c17b26b9953c49761a3a7eaf338a6c865e34e5f17d4241f53e942f757e6c'
SOURCE=Path('/home/jtl/gfn-fpga-lab/agent-work/crt27-mont/snapshot-v2/fpga')
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
POSITIVE_ROOT=SOURCE.parent.parent/'positive-v1'
VECTOR=POSITIVE_ROOT/'vectors.txt'
VECTOR_SHA='8ffb02df5fc819ac47c4ab06713c4b2ed0669cb3323a418905d0fe938ea58167'
VECTOR_BYTES=75776289
CANDIDATE='rtl/kernel/genefer_crt3_27_mont_pipe.sv'
CANDIDATE_SHA='8bb5b62423c1f61e069f131b5d393dd3dbc84d05348fc1945f6e9c419c104c58'
GiB=1<<30;MiB=1<<20
MUTATIONS=('cb-off-one','center-ge','t2m3-removed')


def require(ok,message):
    if not ok:raise ValueError(message)


def digest(data):return hashlib.sha256(data).hexdigest()


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def helper(root):
    """Load only the SHA-pinned source helper, never pycache/project imports."""
    path=Path(root)/POSITIVE;require(not path.is_symlink() and sha(path)==POSITIVE_SHA,'frozen positive helper pin')
    module=types.ModuleType('crt27_mont_positive_frozen');module.__file__=str(path.resolve());module.__package__=''
    sys.dont_write_bytecode=True
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    return module


def source_pins(root):
    root=Path(root).resolve();p=helper(root);pins=dict(p.FIXED_PINS)
    pins[POSITIVE]=POSITIVE_SHA;pins[ANSWER]=ANSWER_SHA;pins[RUNNER]=sha(root/RUNNER)
    for name,value in pins.items():
        path=root/name
        require(not path.is_symlink() and path.resolve().is_relative_to(root) and sha(path)==value,'source drift: '+name)
    require(len(pins)==11 and pins[CANDIDATE]==CANDIDATE_SHA,'eleven-source successor closure')
    return pins,p


def once(text,old,new):
    require(text.count(old)==1,'unique mutation anchor: '+old);return text.replace(old,new)


def omit_constant_checker(text):
    begin='    // CRT27_CONSTANT_CHECK_BEGIN\n';end='    // CRT27_CONSTANT_CHECK_END\n'
    require(text.count(begin)==text.count(end)==1,'exact constant-check fence')
    first=text.index(begin);last=text.index(end)+len(end)
    require(first<last and '$fatal(1,"CRT27 Montgomery constants")' in text[first:last],'constant-check block identity')
    return text[:first]+'    // G2 arithmetic sensitivity only: constant checker omitted in this control/mutant pair.\n'+text[last:]


def derivative(text,name):
    require(digest(text.encode())==CANDIDATE_SHA,'frozen candidate derivative identity')
    if name=='cb-off-one':
        control=omit_constant_checker(text)
        mutant=once(control,"localparam logic [31:0] CB=32'd62755090;","localparam logic [31:0] CB=32'd62755091;")
        return dict(control=control,mutant=mutant,omitted_constant_checker=True,
            category='arithmetic_mismatch',expected=['CRT27_MONT_ARITHMETIC_SIGN_MISMATCH'])
    if name=='center-ge':
        mutant=once(text,'wire signed [95:0] centered_work=value>(MODULUS>>1) ?',
                         'wire signed [95:0] centered_work=value>=(MODULUS>>1) ?')
        return dict(control=text,mutant=mutant,omitted_constant_checker=False,
            category='arithmetic_mismatch',expected=['CRT27_MONT_ARITHMETIC_SIGN_MISMATCH'])
    if name=='t2m3-removed':
        mutant=once(text,'wire [26:0] t2_mod3=t2[26:0]>=P3 ? t2[26:0]-P3 : t2[26:0];',
                         'wire [26:0] t2_mod3=t2[26:0];')
        return dict(control=text,mutant=mutant,omitted_constant_checker=False,
            category='internal_bound_rejection',expected=['CRT27 t2_mod3 bound','noncanonical Montgomery27 input'])
    raise ValueError('explicit required mutation name')


def typed_rejection(returncode,text,wanted):
    require(type(returncode) is int and returncode!=0,'negative control unexpectedly passed')
    matched=[token for token in wanted if token in text]
    require(matched,'negative failed without expected typed diagnosis')
    return matched


def prepare(out):
    require(__debug__,'assertions required');root=Path(__file__).resolve().parents[1]
    require(not (root/'docs/briefs/PAUSE').exists(),'advisor protocol PAUSE')
    pins,p=source_pins(root);stage=root/'results/throughput-20260929/crt27-mont-positive-stage-v1'
    require(sha(stage/'manifest.json')==POSITIVE_MANIFEST_SHA and sha(stage/'source.tar.gz')==POSITIVE_STAGE_ARCHIVE_SHA,'frozen positive stage provenance')
    previous=json.loads((stage/'manifest.json').read_text());base=dict(pins);base.pop(RUNNER);base.pop(ANSWER)
    require(previous['sources']==base and previous['vectors']['sha256']==VECTOR_SHA and previous['vectors']['bytes']==VECTOR_BYTES,
            'original nine-source/vector closure')
    text=(root/CANDIDATE).read_text();derivatives={}
    for name in MUTATIONS:
        row=derivative(text,name);derivatives[name]={key:value for key,value in row.items() if key not in ('control','mutant')}
        derivatives[name].update(control_sha256=digest(row['control'].encode()),mutant_sha256=digest(row['mutant'].encode()))
    out.mkdir(parents=True,exist_ok=False)
    with tarfile.open(out/'source.tar.gz','x:gz') as tar:
        for name in pins:tar.add(root/name,arcname='fpga/'+name,recursive=False)
    shutil.copyfile(stage/'manifest.json',out/'approved-positive-manifest.json')
    manifest=dict(status='prepared_required_mutations_not_executed',source_root=str(SOURCE),sources=pins,top=p.TOP,profile=p.PROFILE,
        compiled_source_order=list(p.ORDER),positive_manifest_sha256=POSITIVE_MANIFEST_SHA,positive_report_sha256=POSITIVE_REPORT_SHA,
        reused_vector_path=str(VECTOR),vectors=previous['vectors'],required_mutations=derivatives,
        archive_sha256=sha(out/'source.tar.gz'),
        limitation='Local preparation only. Reuse read-only approved vectors; three typed negatives and fresh same-source controls required. No fit/whole-core/clock/board/PRP qualification.')
    require(source_pins(root)[0]==pins,'preparation source drift')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest


def execute(out,manifest_path,manifest_sha):
    require(__debug__ and socket.gethostname()=='aethia','explicit aethia execution with assertions')
    root=Path(__file__).resolve().parents[1]
    require(root==SOURCE and root.resolve()==SOURCE and LOCK.resolve()==LOCK and LOCK.is_file(),'fixed successor source/shared lock')
    require(out.resolve().parent==SOURCE.parent.parent and not out.exists(),'fresh isolated successor output')
    require(re.fullmatch('[0-9a-f]{64}',manifest_sha) and sha(manifest_path)==manifest_sha,'externally approved successor manifest')
    pins,p=source_pins(root);manifest=json.loads(manifest_path.read_text())
    require(manifest['status']=='prepared_required_mutations_not_executed' and manifest['source_root']==str(SOURCE) and manifest['sources']==pins and
        manifest['top']==p.TOP and manifest['profile']==p.PROFILE and manifest['compiled_source_order']==list(p.ORDER) and
        manifest['positive_manifest_sha256']==POSITIVE_MANIFEST_SHA and manifest['positive_report_sha256']==POSITIVE_REPORT_SHA and
        manifest['reused_vector_path']==str(VECTOR),'approved successor/parent/profile binding')
    require(not VECTOR.is_symlink() and VECTOR.resolve()==VECTOR and VECTOR.is_file() and VECTOR.stat().st_size==VECTOR_BYTES and sha(VECTOR)==VECTOR_SHA,
            'approved reused immutable vector input')
    parent_report=POSITIVE_ROOT/'report.json';parent_manifest=POSITIVE_ROOT/'approved-manifest.json'
    require(sha(parent_report)==POSITIVE_REPORT_SHA and sha(parent_manifest)==POSITIVE_MANIFEST_SHA,'original native positive receipts')
    prior=json.loads(parent_report.read_text());approved=json.loads(parent_manifest.read_text());base=dict(pins);base.pop(RUNNER);base.pop(ANSWER)
    require(prior['status']=='passed_positive_only_mutations_pending' and prior['sources']==base and approved['sources']==base and
        prior['normal_counts']==approved['vectors']['counts'] and manifest['vectors']==approved['vectors'],'source-linked positive/coverage receipts')
    limits=p.execution_limits();resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(6*GiB,6*GiB))
    out.mkdir();scratch=Path(tempfile.mkdtemp(prefix='gfn16-crt27-mont-neg-',dir='/dev/shm'));os.chmod(scratch,0o700);tmp=scratch/'tmp';tmp.mkdir()
    report=dict(status='running_mutation_controls',scope='CRT27 required typed negatives plus freshly rebuilt unequal-latency paired controls',
        sources=pins,top=p.TOP,profile=p.PROFILE,manifest_sha256=manifest_sha,limits=limits,scratch=str(scratch),compiler_temporary_directory=str(tmp),
        steps=[],artifacts={},builds={},mutations={},input_rejections=[],derived_sources={},compile_workers=2,model_threads=1,
        scratch_reservation_bytes=768*MiB,scratch_free_floor_bytes=2*GiB,durable_reservation_bytes=64*MiB,durable_free_floor_bytes=10*GiB,
        host_memory_floor_bytes=4*GiB,command_timeout_seconds=1800,lock_wait_timeout_seconds=1800,
        reused_inputs={str(VECTOR):VECTOR_SHA,str(parent_report):POSITIVE_REPORT_SHA,str(parent_manifest):POSITIVE_MANIFEST_SHA},
        vectors=approved['vectors'],cleanup='Nothing deleted; retain every failed mutant source/log/executable/generated-source archive and scratch.',
        limitation='Standalone paired two-state CRT component, one atomic27 profile. Reset/hold/latency and named mutation sensitivity only; no exhaustive formal proof, physical/whole-core/board/PRP qualification.')
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def remember(path):report['artifacts'][str(path.relative_to(out))]=sha(path)
    def recheck():
        require(source_pins(root)[0]==pins,'successor source drift')
        require(all(not Path(name).is_symlink() and sha(name)==value for name,value in report['reused_inputs'].items()),'reused input drift')
    def guard():
        require(not (root/'docs/briefs/PAUSE').exists(),'advisor protocol PAUSE')
        require(shutil.disk_usage(out).free>=10*GiB+max(0,64*MiB-p.allocated(out)),'durable reservation/floor')
        require(shutil.disk_usage(scratch).free>=2*GiB+max(0,768*MiB-p.allocated(scratch)),'tmpfs reservation/floor')
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=4*GiB,'host memory floor')
    env={k:v for k,v in os.environ.items() if k not in ('MAKEFLAGS','MFLAGS','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS','CC','CXX','AR','OBJCACHE',
        'OPT_FAST','OPT_SLOW','OPT_GLOBAL','TMPDIR','TMP','TEMP','VERILATOR_BIN','VERILATOR_ROOT','VERILATOR_FLAGS','VLT_FLAGS','PYTHONPATH','PYTHONHOME') and not k.startswith('NTT_')}
    env.update(TMPDIR=str(tmp),TMP=str(tmp),TEMP=str(tmp))
    def run(name,command,expected=None):
        guard();recheck();log=out/(name+'.log');begin=time.monotonic();failure=None
        with log.open('x') as stream:
            process=subprocess.Popen(command,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while process.poll() is None:guard();require(time.monotonic()-begin<1800,'command timeout');time.sleep(1)
            except BaseException as error:
                failure=error
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait()
        remember(log);text=log.read_text();step=dict(name=name,command=command,returncode=process.returncode,error=repr(failure) if failure else None,
            seconds=time.monotonic()-begin,log=log.name,sha256=sha(log),expected_typed_rejection=expected)
        report['steps'].append(step);save();print(name,process.returncode,flush=True)
        if failure:raise failure
        if expected is None:require(process.returncode==0,'command failed: '+name)
        else:step['matched_typed_rejections']=typed_rejection(process.returncode,text,expected);save()
        guard();recheck();return text
    def materialize(name,text):
        path=out/(name+'.sv');path.write_text(text);remember(path);report['derived_sources'][path.name]=sha(path);return path
    def build(name,candidate):
        directory=scratch/('build-'+name);command=p.compile_command(root,directory)
        original=str(root/CANDIDATE);require(command.count(original)==1,'unique compiled candidate input')
        command[command.index(original)]=str(candidate)
        with LOCK.open('r') as lock:
            deadline=time.monotonic()+1800
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:guard();require(time.monotonic()<deadline,'bounded compile lock wait');time.sleep(1)
            run('build-'+name,command)
        exe=out/('V'+p.TOP+'-'+name);shutil.copy2(directory/('V'+p.TOP),exe);remember(exe)
        require(sha(exe)==sha(directory/('V'+p.TOP)),'durable executable copy')
        generated={file.name:sha(file) for file in directory.iterdir() if file.is_file() and file.suffix in ('.cpp','.h','.mk','.dat')}
        archive=out/('generated-'+name+'.tar.gz')
        with tarfile.open(archive,'x:gz') as tar:
            for member in sorted(generated):tar.add(directory/member,arcname=member,recursive=False)
        remember(archive);report['builds'][name]=dict(candidate=str(candidate),candidate_sha256=sha(candidate),
            executable=str(exe),executable_sha256=sha(exe),generated_source_sha256=generated,generated_archive=archive.name)
        save();return exe
    try:
        guard();recheck();save();tools=[Path(sys.executable).resolve()]
        for tool in ('g++','verilator','make'):
            found=shutil.which(tool);require(found is not None,'missing '+tool);tools.append(Path(found).resolve())
        verilator_bin=tools[2].parent/'verilator_bin';require(verilator_bin.is_file(),'fixed companion verilator_bin');tools.append(verilator_bin.resolve())
        report['tool_executable_sha256']={str(path):sha(path) for path in tools};report['python_version']=sys.version
        for name,old in prior['tool_executable_sha256'].items():require(report['tool_executable_sha256'].get(name)==old,'matched parent tool identity')
        for tool in ('verilator','g++','make'):report[tool+'_version']=run(tool+'-version',[tool,'--version']).strip()
        report['verilator_bin_version']=run('verilator-bin-version',[str(verilator_bin),'--version']).strip()
        shutil.copyfile(manifest_path,out/'approved-manifest.json');remember(out/'approved-manifest.json')
        shutil.copyfile(parent_manifest,out/'approved-positive-manifest.json');remember(out/'approved-positive-manifest.json')
        with tarfile.open(out/'sources.tar.gz','x:gz') as tar:
            for name in pins:tar.add(root/name,arcname=name,recursive=False)
        remember(out/'sources.tar.gz');text=(root/CANDIDATE).read_text()
        # Fresh pristine primary supplies isolated canonical guard coverage.
        pristine=build('pristine',root/CANDIDATE);report['probe']=p.check_probe(run('probe-pristine',[str(pristine),'--runtime-probe']))
        report['pristine_counts']=p.check_normal(run('normal-pristine',[str(pristine),'--normal',str(VECTOR)]),approved['vectors'])
        for role in ('baseline','candidate'):
            for port,prime in enumerate(p.PRIMES):
                for value in (prime,prime+1,1<<27,0x80000001,0xffffffff):
                    name=f'reject-{role}-p{port}-{value}'
                    run(name,[str(pristine),'--reject',role,str(port),str(value)],['noncanonical CRT27 input'])
                    report['input_rejections'].append(dict(role=role,port=port,value=value,step=name))
        # Optional active constant guard: distinct from arithmetic sensitivity.
        active_mutant=once(text,"localparam logic [31:0] CB=32'd62755090;","localparam logic [31:0] CB=32'd62755091;")
        active_path=materialize('mutant-active-cb-guard',active_mutant);active=build('active-cb-guard',active_path)
        run('reject-active-cb-guard',[str(active),'--runtime-probe'],['CRT27 Montgomery constants'])
        report['active_constant_guard']='typed constant identity rejection; not an arithmetic mismatch'
        for name in MUTATIONS:
            row=derivative(text,name);declaration=manifest['required_mutations'][name]
            require(declaration==dict(omitted_constant_checker=row['omitted_constant_checker'],category=row['category'],expected=row['expected'],
                control_sha256=digest(row['control'].encode()),mutant_sha256=digest(row['mutant'].encode())),'approved mutation/control transformation')
            mutant_path=materialize('mutant-'+name,row['mutant']);mutant=build('mutant-'+name,mutant_path)
            run('reject-'+name,[str(mutant),'--normal',str(VECTOR)],row['expected'])
            # A newly built same-guard control follows every typed failure.
            control_path=materialize('control-'+name,row['control']);control=build('control-'+name,control_path)
            probe=p.check_probe(run('probe-control-'+name,[str(control),'--runtime-probe']))
            counts=p.check_normal(run('normal-control-'+name,[str(control),'--normal',str(VECTOR)]),approved['vectors'])
            report['mutations'][name]=dict(category=row['category'],omitted_constant_checker=row['omitted_constant_checker'],
                mutant_sha256=sha(mutant_path),control_sha256=sha(control_path),fresh_control_probe=probe,fresh_control_counts=counts,
                negative_step='reject-'+name,control_step='normal-control-'+name)
            save()
        require(set(report['mutations'])==set(MUTATIONS) and len(report['input_rejections'])==30,'all required negative/control/input coverage')
        recheck();guard();require(all(sha(out/name)==value for name,value in report['artifacts'].items()),'durable artifact drift')
        require(all(sha(path)==value for path,value in report['tool_executable_sha256'].items()),'tool identity drift')
        report['status']='passed_required_mutations_and_fresh_controls'
    except BaseException as error:report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:save()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',type=Path);mode.add_argument('--execute',action='store_true');parser.add_argument('--output',type=Path)
    parser.add_argument('--manifest',type=Path);parser.add_argument('--manifest-sha');args=parser.parse_args()
    require(not (Path(__file__).resolve().parents[1]/'docs/briefs/PAUSE').exists(),'advisor protocol PAUSE')
    if args.prepare:
        require(args.output is None and args.manifest is None and args.manifest_sha is None,'prepare-only arguments')
        result=prepare(args.prepare.resolve());print(json.dumps(dict(status=result['status'],sources=len(result['sources']),reused_vector_path=result['reused_vector_path'],
            archive_sha256=result['archive_sha256'],mutations=result['required_mutations']),indent=2))
    else:
        require(args.output and args.manifest and args.manifest_sha,'explicit execution arguments');execute(args.output.resolve(),args.manifest.resolve(),args.manifest_sha)
