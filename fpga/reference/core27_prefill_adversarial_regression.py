"""Source-only preparation and explicit bounded AW5 T5 adversarial gates.

One fresh mutant/control pair per invocation, or one-build targeted controls.
Passed exact normal-v2 evidence is mandatory. No automatic/native dispatch.
"""
import argparse
import ast
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

ROOT = Path('/home/jtl/gfn-fpga-lab/agent-work/core27-prefill-aw5-qualification/snapshot-v1/fpga')
DESTINATION = ROOT.parent.parent
LOCK = Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
PARENT = 'reference/core27_prefetch_r2_rootfused_crtmont_regression.py'
PARENT_SHA = '95898756fd1c8c547343341428836379e90400644659635bd7dc77010107b208'
CHECKPOINT = 'docs/briefs/replies/2026-09-30-B20260930-T5-prefill-source-preparation-v1.json'
CHECKPOINT_SHA = 'c0a6a42839f095f70c20e494b4f6398dc73b30bb7864a1f15f7946d11518a6c8'
NORMAL_REPORT = 'results/throughput-20260929/core27-prefetch-r2-rootfused-crtmont-aw5-v1/report.json'
NORMAL_REPORT_SHA = '1bc9950b438397ed2e1bcb230996b6f02d7a30d9d42d65f9d664857ed610bceb'
TARGET_VECTOR_SHA = '1080d4454da030795060b347cf1dd7f06cebae4c2451272cd6fecc01378d3603'
RUNNER = 'reference/core27_prefill_adversarial_regression.py'
PREDECESSOR_MANIFEST = 'results/throughput-20260929/core27-prefill-aw5-stage-v2/manifest.json'
PREDECESSOR_SHA = '5165293cc441dce05496b89a4cb725c00116ba46d78bf360a2b93dddc1db451d'
NORMAL_OUTPUT = Path('/home/jtl/gfn-fpga-lab/agent-work/core27-prefill-aw5-v2/normal-v2')
NORMAL_T5_REPORT = 'results/throughput-20260929/core27-prefill-aw5-normal-v2/report.json'
NORMAL_T5_SHA = 'a94f431c20319cba713df4d9e845fbd36bea237d82d355a353aff7f523ec5f5d'
EXTRA = ('rtl/tb/core27_prefill_adversarial_v1.cpp',
         'reference/core27_prefill_mutant_sources.py',
         'tests/test_core27_prefill_adversarial.py', RUNNER)
MUTATION_NAMES = ('eligibility_after_load','write_address','field_mask','final_write_count',
                  'base_tag','late_host_error','omitted_tee','corrupted_tee')
GROUPS = ('normal', 'reset-tail', 'reset-emission', 'host-error-tail', 'host-error-emission',
          'carry-error-tail', 'base-change')
GIB = 1 << 30
MIB = 1 << 20


def require(ok, why):
    if not ok: raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def compressed_executable(source, destination):
    """Preserve exact executable bytes durably without keeping an extra raw copy."""
    require(source.is_file() and not source.is_symlink() and not destination.exists(), 'fresh executable archive')
    expected = sha(source)
    with source.open('rb') as original, destination.open('xb') as target:
        with gzip.GzipFile(filename='',mode='wb',fileobj=target,mtime=0) as compressed:
            shutil.copyfileobj(original,compressed,1<<20)
    with gzip.open(destination,'rb') as stream:
        require(hashlib.file_digest(stream,'sha256').hexdigest()==expected, 'compressed executable round-trip')
    return dict(uncompressed_sha256=expected,compressed_sha256=sha(destination),
                uncompressed_bytes=source.stat().st_size,compressed_bytes=destination.stat().st_size)


def literals(path):
    result = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try: result[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError): pass
    return result


def source_pins(root):
    root = Path(root).resolve()
    require(sha(root/PREDECESSOR_MANIFEST) == PREDECESSOR_SHA, 'exact predecessor manifest')
    predecessor = json.loads((root/PREDECESSOR_MANIFEST).read_text())
    require(predecessor['status'] == 'prepared_not_executed' and len(predecessor['sources']) == 98,
            'exact ninety-eight-source predecessor')
    pins = dict(predecessor['sources']); pins[PREDECESSOR_MANIFEST] = PREDECESSOR_SHA
    pins[NORMAL_T5_REPORT] = NORMAL_T5_SHA
    for name in EXTRA: pins[name] = sha(root/name)
    for name, digest in pins.items():
        path = root/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and
                not path.is_symlink() and path.resolve().is_relative_to(root) and sha(path) == digest,
                'source path/hash mismatch: '+name)
    validate_observer_states(root)
    return pins


def state_enum(source):
    matches = re.findall(r'typedef\s+enum\s+logic\s*\[(\d+):0\]\s*\{([^}]+)\}\s*state_t\s*;', source, re.S)
    require(len(matches) == 1, 'one explicit-width state enum')
    high, body = matches[0]
    labels = [x.strip() for x in body.split(',')]
    require(all(re.fullmatch('[A-Z][A-Z0-9_]*', x) for x in labels) and
            len(labels) == len(set(labels)), 'simple unique implicit enum values')
    return int(high)+1, dict(zip(labels, range(len(labels))))


def validate_observer_states(root):
    root = Path(root)
    core = (root/'rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill.sv').read_text()
    carry = (root/'rtl/kernel/genefer_carry_prefix_stream_precision_emit.sv').read_text()
    cw, cm = state_enum(core); ew, em = state_enum(carry)
    require(cw == ew == 4, 'exact four-bit state widths')
    expected = {'CORE_IDLE': cm['IDLE'], 'CORE_CARRY_WAIT': cm['CARRY_WAIT'],
                'CORE_PREFILL_CHECK': cm['PREFILL_CHECK'], 'CARRY_EMIT': em['EMIT']}
    require(expected == {'CORE_IDLE': 0, 'CORE_CARRY_WAIT': 11, 'CORE_PREFILL_CHECK': 13, 'CARRY_EMIT': 7},
            'frozen state enumeration mapping')
    for name in ('core27_prefill_probe_v3.sv', 'core27_prefill_tail_probe_v3.sv'):
        source = (root/'rtl/tb'/name).read_text()
        actual = {key:int(value) for key,value in re.findall(r"(CORE_IDLE|CORE_CARRY_WAIT|CORE_PREFILL_CHECK|CARRY_EMIT)=4'd(\d+)", source)}
        require(actual == expected, 'observer numeric state mapping')
        require(not re.search(r'dut\.(?:carry_unit\.)?(?:IDLE|CARRY_WAIT|PREFILL_CHECK|EMIT)\b', source),
                'hierarchical enum references forbidden')
        require('localparam logic [3:0] CORE_IDLE=' in source and '$bits(dut.state)!=4' in source,
                'explicit observer state widths')
    return expected


def compiled(root, group):
    names = literals(Path(root)/PARENT)['COMPILED_ORDER']
    replace = {'genefer_carry_prefix_stream_precision.sv': 'genefer_carry_prefix_stream_precision_emit.sv',
               'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont.sv':
               'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill.sv'}
    paths = ['rtl/kernel/'+replace.get(name, name) for name in names]
    if group == 'normal': paths += ['rtl/tb/core27_prefill_probe_v3.sv']
    else: paths += ['rtl/tb/core27_prefill_fault_bridge.sv', 'rtl/tb/core27_prefill_tail_probe_v3.sv']
    return paths


def top(group): return 'core27_prefill_probe_v3' if group == 'normal' else 'core27_prefill_tail_probe_v3'


def commands(exe, vector, group):
    require(group in GROUPS, 'explicit supported group')
    if group == 'normal': return [('normal', [str(exe), str(vector), 'profile'])]
    if group == 'base-change':
        return [(name, [str(exe), '--'+name, str(vector), 'control']) for name in ('changed-base', 'base-reject')]
    mode = '--tail-reset' if group.startswith('reset') else '--tail-carry-error' if group.startswith('carry') else '--tail-error'
    cases = [(age, 'final') for age in range(7)] if group.endswith('tail') else [(0, row) for row in ('first', 'middle')]
    return [(f'{group}-{row}-e{age}', [str(exe), mode, str(vector), str(age), row, 'control']) for age, row in cases]


def load_project(root, pins):
    require(not any(n == 'reference' or n.startswith('reference.') for n in sys.modules), 'clean project import namespace')
    require(source_pins(root) == pins, 'pre-import drift')
    require(not any(p.suffix in ('.pyc','.so','.pyd') for p in (root/'reference').rglob('*')), 'source-only imports')
    sys.dont_write_bytecode = True; sys.path.insert(0, str(root))
    baseline = importlib.import_module('reference.core27_prefetch_r2_regression')
    normal = importlib.import_module('reference.core27_prefill_aw5_v2_regression')
    recipe = importlib.import_module('reference.core27_prefill_mutant_sources')
    vectors = importlib.import_module('reference.core27_prefill_target_vectors')
    require(recipe.NAMES == MUTATION_NAMES, 'exact eight mutation names')
    require(recipe.bridge((root/recipe.CORE).read_text()) == (root/recipe.BRIDGE).read_text(), 'exact fault bridge')
    for name, module in tuple(sys.modules.items()):
        if name == 'reference' or name.startswith('reference.'):
            path = Path(module.__file__).resolve()
            require(path.is_relative_to(root), 'external project import')
            relative = str(path.relative_to(root))
            require(relative in pins and sha(path) == pins[relative], 'unlisted imported source: '+name)
    return baseline, normal, recipe, vectors


def prepare(out):
    root = Path(__file__).resolve().parents[1]; pins = source_pins(root)
    require(not out.exists(), 'fresh stage directory'); out.mkdir(parents=True)
    with tarfile.open(out/'source.tar.gz', 'x:gz') as tar:
        for name in sorted(pins): tar.add(root/name, arcname='fpga/'+name, recursive=False)
    require(source_pins(root) == pins, 'prepare source drift')
    manifest = dict(status='prepared_not_executed', target=str(ROOT), sources=pins,
                    archive_sha256=sha(out/'source.tar.gz'), aw=5,
                    modes=['targeted-controls','one-mutant-pair'], mutations=list(MUTATION_NAMES),
                    compiled=compiled(root,'reset-tail'), observer_state_mapping=validate_observer_states(root),
                    prerequisite_manifest_sha256=PREDECESSOR_SHA,
                    prerequisite_report_sha256=NORMAL_T5_SHA,
                    limitation='Requires independently approved passed AW5 normal-v2 report. One fresh pair per invocation; no cache reuse, AW16 or physical action.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(files=len(pins),manifest_sha256=sha(out/'manifest.json'),archive_sha256=sha(out/'source.tar.gz'))))
    return manifest


def verify_manifest(root, path, digest):
    require(re.fullmatch('[0-9a-f]{64}',digest) is not None and sha(path)==digest, 'approved manifest identity')
    manifest = json.loads(path.read_text()); pins=source_pins(root)
    require(manifest['status']=='prepared_not_executed' and manifest['target']==str(ROOT) and manifest['aw']==5 and
            manifest['modes']==['targeted-controls','one-mutant-pair'] and manifest['mutations']==list(MUTATION_NAMES) and
            manifest['sources']==pins and manifest['compiled']==compiled(root,'reset-tail') and
            manifest['observer_state_mapping']==validate_observer_states(root) and
            manifest['prerequisite_manifest_sha256']==PREDECESSOR_SHA and
            manifest['prerequisite_report_sha256']==NORMAL_T5_SHA, 'approved exact qualification snapshot')
    return manifest,pins


def normal_prerequisite(root, path, digest, baseline, normal):
    require(path == NORMAL_OUTPUT/'report.json' and path.resolve()==path and
            digest==NORMAL_T5_SHA and sha(path)==digest, 'approved exact normal report path/hash')
    report=json.loads(path.read_text())
    prior=json.loads((root/PREDECESSOR_MANIFEST).read_text())
    require(report['status']=='passed_aw5_group_only' and report['group']=='normal' and report['aw']==5 and
            report['top']=='core27_prefill_probe_v3' and report['sources']==prior['sources'] and
            report['manifest_sha256']==PREDECESSOR_SHA and report['model_threads']==1 and report['compile_workers']==2,
            'passed source-matched normal-v2 prerequisite')
    require([x['name'] for x in report['steps']]==['verilator-version','compiler-version','build','probe','normal'] and
            all(x['returncode']==0 and x['error'] is None for x in report['steps']), 'successful normal native steps')
    for name,value in report['artifacts'].items():
        artifact=path.parent/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and not artifact.is_symlink() and
                artifact.resolve().is_relative_to(path.parent) and sha(artifact)==value, 'normal artifact closure')
    parent=json.loads((root/NORMAL_REPORT).read_text())
    baseline.check_probe((path.parent/'probe.log').read_text(),1)
    rows=normal.check_normal((path.parent/'normal.log').read_text(),parent)
    require(rows==report['metrics'] and report['vectors']==parent['vectors'], 'normal actual-output replay')
    return report


def suite_commands(exe, vector, normal):
    result=[]
    for group in GROUPS:
        if group!='normal': result.append((group,normal.commands(exe,vector,group)))
    result.append(('reload-control',[('reload-control',[str(exe),'--reload-control',str(vector),'control'])]))
    require(all(len(cases)<=7 for _,cases in result), 'bounded seven cases per group')
    return result


def execute(out, path, digest, normal_path, normal_sha, mutation=None):
    require(__debug__ and socket.gethostname()=='aethia', 'aethia with assertions only')
    root=Path(__file__).resolve().parents[1]
    require(root==ROOT and root.resolve()==ROOT, 'fixed isolated qualification snapshot')
    require(out.resolve().parent==DESTINATION and not out.exists(), 'fresh qualification output')
    require(LOCK.is_file() and LOCK.resolve()==LOCK, 'shared compiler lock')
    require(mutation is None or mutation in MUTATION_NAMES, 'one explicit mutation')
    manifest,pins=verify_manifest(root,path,digest)
    baseline,normal,recipe,vectors=load_project(root,pins)
    prerequisite=normal_prerequisite(root,normal_path,normal_sha,baseline,normal)
    limits=baseline.execution_limits()
    require(limits['affinity']==[0,2] and len({tuple(x) for x in limits['physical_cores']})==2, 'separate physical CPUs0/2')
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(6*GIB,6*GIB))
    out.mkdir();scratch=Path(tempfile.mkdtemp(prefix='gfn16-t5-adversarial-',dir='/dev/shm'));os.chmod(scratch,0o700)
    temporary=scratch/'tmp';temporary.mkdir()
    started=time.monotonic()
    reserve=(1536 if mutation else 768)*MIB
    # Two compressed executables plus two generated-source archives fit in a
    # conservative32MiB reservation; the independent10GiB floor still applies.
    durable_reserve=32*MIB
    report=dict(status='running',mode='one-mutant-pair' if mutation else 'targeted-controls',mutation=mutation,
                aw=5,n=32,top='core27_prefill_tail_probe_v3',sources=pins,manifest_sha256=digest,
                prerequisite_normal_sha256=normal_sha,prerequisite_manifest_sha256=PREDECESSOR_SHA,
                limits=limits,compile_workers=2,model_threads=1,steps=[],artifacts={},builds={},groups=[],
                scratch=str(scratch),scratch_reservation_bytes=reserve,durable_reservation_bytes=durable_reserve,
                scratch_free_floor_bytes=2*GIB,durable_free_floor_bytes=10*GIB,host_memory_floor_bytes=4*GIB,
                command_timeout_seconds=1800,total_budget_seconds=3600,lock_wait_timeout_seconds=1800,
                cleanup='All scratch and failed evidence retained; no deletion.',
                limitation='AW5 only; middle emission aliases final. No AW16, physical or full-PRP claim.')
    def remember(p):report['artifacts'][str(p.relative_to(out))]=sha(p)
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def guard():
        require(time.monotonic()-started<3600, 'total gate time budget')
        require(shutil.disk_usage(out).free>=10*GIB+max(0,durable_reserve-baseline.allocated_bytes(out)), 'durable reservation/floor')
        require(shutil.disk_usage(scratch).free>=2*GIB+max(0,reserve-baseline.allocated_bytes(scratch)), 'tmpfs reservation/floor')
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=4*GIB, 'host memory floor')
    def recheck():
        require(verify_manifest(root,path,digest)[1]==pins and sha(normal_path)==normal_sha, 'source/prerequisite drift')
    env={k:v for k,v in os.environ.items() if k not in ('MAKEFLAGS','MFLAGS','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS',
         'CC','CXX','AR','OBJCACHE','OPT_FAST','OPT_SLOW','OPT_GLOBAL','TMPDIR','TMP','TEMP') and not k.startswith('NTT_')}
    env.update(TMPDIR=str(temporary),TMP=str(temporary),TEMP=str(temporary),CCACHE_DISABLE='1')
    def run(name,argv,abort_expected=False):
        guard();recheck();log=out/(name+'.log');before=time.monotonic();failure=None
        with log.open('x') as stream:
            child=subprocess.Popen(argv,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while child.poll() is None:
                    guard();require(time.monotonic()-before<1800,'command timeout');time.sleep(1)
            except BaseException as error:
                failure=error
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                child.wait()
        remember(log);report['steps'].append(dict(name=name,command=argv,returncode=child.returncode,
            seconds=time.monotonic()-before,error=repr(failure) if failure else None,log=log.name,sha256=sha(log)))
        save()
        if failure:raise failure
        require(child.returncode==(-6 if abort_expected else 0), 'unexpected native return code: '+name)
        guard();return log.read_text(),child.returncode
    def build_role(role,derived):
        # Every role uses a fresh directory. No predecessor or other-pair object
        # files, generated C++, model executable, or build-cache hits are reused.
        build=scratch/('build-'+role);require(not build.exists(),'fresh per-role build directory')
        overlay=out/('derived-'+role);overlay.mkdir()
        derived_sha={}
        for relative,source in derived.items():
            target=overlay/relative;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(source);remember(target);derived_sha[relative]=sha(target)
        sources=[overlay/name if name in derived else root/name for name in compiled(root,'reset-tail')]
        argv=['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module','core27_prefill_tail_probe_v3',
              '-GAW=5','-GNTT_LANES=64','-CFLAGS','-std=c++17 -Werror=return-type',
              '--Mdir',str(build),*map(str,sources),str(root/'rtl/tb/core27_prefill_adversarial_v1.cpp')]
        with LOCK.open('r') as lock:
            deadline=time.monotonic()+1800
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:guard();require(time.monotonic()<deadline,'compile lock timeout');time.sleep(1)
            run('build-'+role,argv)
        exe=build/'Vcore27_prefill_tail_probe_v3'
        executable_archive=out/('model-'+role+'.gz')
        executable_identity=compressed_executable(exe,executable_archive);remember(executable_archive)
        generated={p.name:sha(p) for p in build.iterdir() if p.is_file() and p.suffix in ('.cpp','.h','.mk','.dat')}
        archive=out/('generated-'+role+'.tar.gz')
        with tarfile.open(archive,'x:gz') as tar:
            for name in sorted(generated):tar.add(build/name,arcname=name,recursive=False)
        remember(archive)
        baseline.check_probe(run('probe-'+role,[str(exe),'--runtime-probe'])[0],1)
        report['builds'][role]=dict(derived_sources=derived_sha,compiled_source_order=[str(p) for p in sources],
             executable=str(exe),executable_sha256=sha(exe),executable_archive=executable_archive.name,
             executable_archive_identity=executable_identity,generated_source_sha256=generated,
             generated_archive=archive.name,fresh_build_directory=str(build))
        save();return exe
    try:
        guard();recheck()
        tools=[Path(sys.executable).resolve()]
        for name in ('g++','verilator','verilator_bin','make'):
            found=shutil.which(name);require(found is not None,'missing '+name);tools.append(Path(found).resolve())
        report['tool_sha256']={str(p):sha(p) for p in tools};report['python_version']=sys.version
        report['verilator_version']=run('verilator-version',['verilator','--version'])[0].strip()
        report['compiler_version']=run('compiler-version',['g++','--version'])[0].strip()
        shutil.copyfile(path,out/'approved-manifest.json');remember(out/'approved-manifest.json')
        shutil.copyfile(normal_path,out/'prerequisite-normal-report.json');remember(out/'prerequisite-normal-report.json')
        with tarfile.open(out/'sources.tar.gz','x:gz') as tar:
            for name in sorted(pins):tar.add(root/name,arcname=name,recursive=False)
        remember(out/'sources.tar.gz')
        vector=out/'vectors.txt';vector.write_text(vectors.target_vectors(5));remember(vector)
        require(sha(vector)==TARGET_VECTOR_SHA,'approved direct integer target vectors')
        if mutation:
            control,mutant,contract=recipe.pair_sources(root,mutation)
            report['mutation_contract']=contract
            control_exe=build_role('fresh-control',control)
            control_argv=recipe.command(control_exe,vector,mutation)
            control_output,_=run('fresh-control',control_argv)
            report['fresh_control']=recipe.check_footer(control_output,control_argv)
            mutant_exe=build_role('mutant',mutant)
            mutant_argv=recipe.command(mutant_exe,vector,mutation)
            require(control_argv[1:]==mutant_argv[1:],'identical control/mutant case and vectors')
            mutant_output,code=run('mutant',mutant_argv,abort_expected=True)
            report['typed_rejection']=recipe.check_fatal(mutant_output,code,contract)
            report['status']='passed_one_mutant_and_fresh_control'
        else:
            # Original unmodified core/carry plus exact zero-capable fault
            # bridge. One executable, independently recorded bounded groups.
            original={recipe.CORE:(root/recipe.CORE).read_text(),recipe.CARRY:(root/recipe.CARRY).read_text(),
                      recipe.BRIDGE:(root/recipe.BRIDGE).read_text()}
            exe=build_role('targeted-controls',original)
            for group,cases in suite_commands(exe,vector,normal):
                evidence=dict(name=group,cases=[])
                for name,argv in cases:
                    output,_=run(name,argv)
                    evidence['cases'].append(dict(name=name,command=argv,footer=recipe.check_footer(output,argv)))
                report['groups'].append(evidence);save()
            require(len(report['groups'])==7 and sum(len(x['cases']) for x in report['groups'])==28,
                    'complete bounded targeted suite')
            report['status']='passed_aw5_targeted_controls_only'
        recheck();guard()
        require(normal_prerequisite(root,normal_path,normal_sha,baseline,normal)==prerequisite,'normal evidence drift')
        require(all(sha(out/name)==value for name,value in report['artifacts'].items()),'durable artifact drift')
        for build in report['builds'].values():
            require(sha(build['executable'])==build['executable_sha256'],'native model drift')
            with gzip.open(out/build['executable_archive'],'rb') as stream:
                require(hashlib.file_digest(stream,'sha256').hexdigest()==build['executable_sha256'],
                        'durable executable decompressed identity')
        require(all(sha(p)==value for p,value in report['tool_sha256'].items()),'toolchain drift')
    except BaseException as error:
        report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:save()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',type=Path);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--targeted-controls',action='store_true');parser.add_argument('--mutation',choices=MUTATION_NAMES)
    parser.add_argument('--output',type=Path);parser.add_argument('--manifest',type=Path);parser.add_argument('--manifest-sha')
    parser.add_argument('--normal-report',type=Path);parser.add_argument('--normal-sha')
    args=parser.parse_args()
    if args.prepare:
        require(not args.execute and not any((args.targeted_controls,args.mutation,args.output,args.manifest,
            args.manifest_sha,args.normal_report,args.normal_sha)), 'exclusive preparation mode')
        prepare(args.prepare.resolve())
    else:
        require(args.execute and bool(args.targeted_controls)!=bool(args.mutation) and args.output and args.manifest and
                args.manifest_sha and args.normal_report and args.normal_sha,'one explicit mode and approved normal prerequisite')
        execute(args.output.resolve(),args.manifest.resolve(),args.manifest_sha,
                args.normal_report.resolve(),args.normal_sha,args.mutation)


if __name__=='__main__':main()
