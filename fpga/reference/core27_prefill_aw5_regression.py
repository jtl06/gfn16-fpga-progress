"""Prepare or explicitly run one bounded AW5-first T5 gate group on aethia.

No automatic dispatch, AW16, mutation execution, cloud or physical action.
Every source is verified against the approved manifest before project imports.
"""
import argparse
import ast
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

ROOT = Path('/home/jtl/gfn-fpga-lab/agent-work/core27-prefill-aw5/snapshot-v1/fpga')
DESTINATION = ROOT.parent.parent
LOCK = Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
PARENT = 'reference/core27_prefetch_r2_rootfused_crtmont_regression.py'
PARENT_SHA = '95898756fd1c8c547343341428836379e90400644659635bd7dc77010107b208'
CHECKPOINT = 'docs/briefs/replies/2026-09-30-B20260930-T5-prefill-source-preparation-v1.json'
CHECKPOINT_SHA = 'c0a6a42839f095f70c20e494b4f6398dc73b30bb7864a1f15f7946d11518a6c8'
NORMAL_REPORT = 'results/throughput-20260929/core27-prefetch-r2-rootfused-crtmont-aw5-v1/report.json'
NORMAL_REPORT_SHA = '1bc9950b438397ed2e1bcb230996b6f02d7a30d9d42d65f9d664857ed610bceb'
TARGET_VECTOR_SHA = '1080d4454da030795060b347cf1dd7f06cebae4c2451272cd6fecc01378d3603'
RUNNER = 'reference/core27_prefill_aw5_regression.py'
EXTRA = (
    'rtl/tb/core27_prefill_probe_v2.sv', 'rtl/tb/core27_prefill_normal_v2.cpp',
    'rtl/tb/core27_prefill_normal_v2_threaded.cpp', 'rtl/tb/core27_prefill_fault_bridge.sv',
    'rtl/tb/core27_prefill_tail_probe.sv', 'rtl/tb/core27_prefill_tail.cpp',
    'reference/core27_prefill_target_vectors.py', 'reference/core27_prefill_qualification_mutations.py',
    'tests/test_core27_prefill_qualification.py',
    RUNNER,
)
GROUPS = ('normal', 'reset-tail', 'reset-emission', 'host-error-tail', 'host-error-emission',
          'carry-error-tail', 'base-change')
GIB = 1 << 30
MIB = 1 << 20


def require(ok, why):
    if not ok: raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def literals(path):
    result = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try: result[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError): pass
    return result


def source_pins(root):
    root = Path(root).resolve()
    require(sha(root/PARENT) == PARENT_SHA, 'reviewed parent runner identity')
    require(sha(root/CHECKPOINT) == CHECKPOINT_SHA, 'frozen T5 checkpoint identity')
    pins = dict(literals(root/PARENT)['FIXED_PINS'])
    pins[PARENT] = PARENT_SHA
    checkpoint = json.loads((root/CHECKPOINT).read_text())
    pins.update({name.removeprefix('fpga/'): digest for name, digest in checkpoint['files'].items()})
    pins[CHECKPOINT] = CHECKPOINT_SHA
    pins[NORMAL_REPORT] = NORMAL_REPORT_SHA
    pins.update(literals(root/'reference/core27_prefill_structure.py')['PARENT_REVIEWS'])
    for name in EXTRA: pins[name] = sha(root/name)
    for name, digest in pins.items():
        path = root/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and
                not path.is_symlink() and path.resolve().is_relative_to(root) and sha(path) == digest,
                'source path/hash mismatch: '+name)
    return pins


def compiled(root, group):
    names = literals(Path(root)/PARENT)['COMPILED_ORDER']
    replace = {'genefer_carry_prefix_stream_precision.sv': 'genefer_carry_prefix_stream_precision_emit.sv',
               'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont.sv':
               'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill.sv'}
    paths = ['rtl/kernel/'+replace.get(name, name) for name in names]
    if group == 'normal': paths += ['rtl/tb/core27_prefill_probe_v2.sv']
    else: paths += ['rtl/tb/core27_prefill_fault_bridge.sv', 'rtl/tb/core27_prefill_tail_probe.sv']
    return paths


def top(group): return 'core27_prefill_probe_v2' if group == 'normal' else 'core27_prefill_tail_probe'


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
    require(not any(p.suffix in ('.pyc', '.so', '.pyd') for p in (root/'reference').rglob('*')), 'source-only imports')
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    baseline = importlib.import_module('reference.core27_prefetch_r2_regression')
    structure = importlib.import_module('reference.core27_prefill_structure')
    vectors = importlib.import_module('reference.core27_prefill_target_vectors')
    structure.validate_files(root)
    for name, module in tuple(sys.modules.items()):
        if name == 'reference' or name.startswith('reference.'):
            path = Path(module.__file__).resolve()
            require(path.is_relative_to(root), 'external project import')
            relative = str(path.relative_to(root))
            require(relative in pins and sha(path) == pins[relative], 'unlisted imported source: '+name)
    return baseline, vectors


def prepare(out):
    root = Path(__file__).resolve().parents[1]
    pins = source_pins(root)
    require(not out.exists(), 'fresh stage directory')
    out.mkdir(parents=True)
    archive = out/'source.tar.gz'
    with tarfile.open(archive, 'x:gz') as tar:
        for name in sorted(pins): tar.add(root/name, arcname='fpga/'+name, recursive=False)
    require(source_pins(root) == pins, 'prepare source drift')
    manifest = dict(status='prepared_not_executed', target=str(ROOT), sources=pins,
                    groups=list(GROUPS), aw=5, archive_sha256=sha(archive),
                    compiled={g: compiled(root, g) for g in GROUPS},
                    qualification='Normal and targeted controls only; eight mutant native gates remain separate. AW16 not authorized by this runner.')
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(files=len(pins), manifest_sha256=sha(out/'manifest.json'), archive_sha256=sha(archive))))
    return manifest


def verify_manifest(root, path, digest, group):
    require(re.fullmatch('[0-9a-f]{64}', digest) is not None and sha(path) == digest, 'approved manifest identity')
    manifest = json.loads(path.read_text())
    require(manifest['status'] == 'prepared_not_executed' and manifest['target'] == str(ROOT) and
            manifest['groups'] == list(GROUPS) and manifest['aw'] == 5 and group in GROUPS, 'fixed AW5 gate profile')
    pins = source_pins(root)
    require(manifest['sources'] == pins, 'approved source closure')
    require(manifest['compiled'] == {g: compiled(root, g) for g in GROUPS}, 'exact compiled order')
    return manifest, pins


def check_normal(output, parent):
    rows = []
    for line in output.splitlines():
        if ' cycles=' not in line: continue
        label, *tokens = line.split()
        row = dict(token.split('=', 1) for token in tokens)
        rows.append(dict(case=label, aw=5, n=32, **{k: int(v) for k, v in row.items()}))
    require(len(rows) == len(parent['metrics']) == 568, 'all normal operations')
    for row, old in zip(rows, parent['metrics']):
        require(row['case'] == old['case'], 'ordered operation identity')
        require(row['prefill_before'] in (0, 1) and row['prefill_after'] == 1, 'image eligibility evidence')
        expected = dict(old, conversion=0 if row['prefill_before'] else old['conversion'], carry=old['carry']+5)
        expected['cycles'] = old['cycles']+5-(old['conversion'] if row['prefill_before'] else 0)
        require({k: row[k] for k in old} == expected, 'matched T5 source-predicted phase delta')
    require('PASS n=32 squares=568 readbacks=561 aborts=20' in output, 'exact normal footer')
    return rows


def execute(out, path, digest, group):
    require(__debug__ and socket.gethostname() == 'aethia', 'aethia with assertions only')
    root = Path(__file__).resolve().parents[1]
    require(root == ROOT and root.resolve() == ROOT, 'fixed isolated snapshot path')
    require(out.resolve().parent == DESTINATION and not out.exists(), 'fresh isolated output path')
    require(LOCK.is_file() and LOCK.resolve() == LOCK, 'shared compiler lock')
    manifest, pins = verify_manifest(root, path, digest, group)
    baseline, vectors = load_project(root, pins)
    limits = baseline.execution_limits()
    require(limits['affinity'] == [0, 2] and len({tuple(x) for x in limits['physical_cores']}) == 2, 'two separate physical CPUs 0/2')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (6*GIB, 6*GIB))
    out.mkdir(); scratch = Path(tempfile.mkdtemp(prefix='gfn16-t5-aw5-', dir='/dev/shm')); os.chmod(scratch, 0o700)
    temporary = scratch/'tmp'; temporary.mkdir()
    started = time.monotonic()
    report = dict(status='running', group=group, aw=5, sources=pins, manifest_sha256=digest, limits=limits,
                  top=top(group), compiled=compiled(root, group), steps=[], artifacts={}, scratch=str(scratch),
                  command_timeout_seconds=1800, total_budget_seconds=3600, scratch_reservation_bytes=768*MIB,
                  scratch_free_floor_bytes=2*GIB, durable_reservation_bytes=64*MIB, durable_free_floor_bytes=10*GIB,
                  host_memory_floor_bytes=4*GIB, compile_workers=2, model_threads=1, cleanup='Scratch retained; no deletion.',
                  limitation='Single AW5 group only; not full T5 qualification, AW16, fit, clock or board result.')
    def remember(p): report['artifacts'][str(p.relative_to(out))] = sha(p)
    def save(): (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    def guard():
        require(time.monotonic()-started < 3600, 'total gate budget')
        require(shutil.disk_usage(out).free >= 10*GIB+max(0, 64*MIB-baseline.allocated_bytes(out)), 'durable reservation/floor')
        require(shutil.disk_usage(scratch).free >= 2*GIB+max(0, 768*MIB-baseline.allocated_bytes(scratch)), 'tmpfs reservation/floor')
        mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024 >= 4*GIB, 'host memory floor')
    def recheck(): require(verify_manifest(root, path, digest, group)[1] == pins, 'input/source drift')
    env = {k: v for k, v in os.environ.items() if k not in ('MAKEFLAGS','MFLAGS','CFLAGS','CXXFLAGS','CPPFLAGS',
           'LDFLAGS','CC','CXX','AR','OBJCACHE','OPT_FAST','OPT_SLOW','OPT_GLOBAL','TMPDIR','TMP','TEMP') and not k.startswith('NTT_')}
    env.update(TMPDIR=str(temporary), TMP=str(temporary), TEMP=str(temporary))
    def run(name, argv):
        guard(); recheck(); log = out/(name+'.log'); before = time.monotonic(); failure = None
        with log.open('x') as stream:
            child = subprocess.Popen(argv, cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                while child.poll() is None:
                    guard(); require(time.monotonic()-before < 1800, 'command timeout'); time.sleep(1)
            except BaseException as error:
                failure = error
                try: os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                child.wait()
        remember(log); report['steps'].append(dict(name=name, command=argv, returncode=child.returncode,
             seconds=time.monotonic()-before, error=repr(failure) if failure else None, log=log.name, sha256=sha(log)))
        save()
        if failure: raise failure
        require(child.returncode == 0, name+' failed'); guard(); return log.read_text()
    try:
        guard(); recheck()
        tools = [Path(sys.executable).resolve()]
        for name in ('g++', 'verilator', 'verilator_bin', 'make'):
            found = shutil.which(name); require(found is not None, 'missing '+name); tools.append(Path(found).resolve())
        report['tool_sha256'] = {str(p): sha(p) for p in tools}; report['python_version'] = sys.version
        report['verilator_version'] = run('verilator-version', ['verilator', '--version']).strip()
        report['compiler_version'] = run('compiler-version', ['g++', '--version']).strip()
        shutil.copyfile(path, out/'approved-manifest.json'); remember(out/'approved-manifest.json')
        with tarfile.open(out/'sources.tar.gz', 'x:gz') as tar:
            for name in sorted(pins): tar.add(root/name, arcname=name, recursive=False)
        remember(out/'sources.tar.gz')
        vector = out/'vectors.txt'
        parent = json.loads((root/NORMAL_REPORT).read_text())
        if group == 'normal':
            report['vectors'] = baseline.write_vectors(vector, 5, 20260929, True)
            require(report['vectors'] == parent['vectors'], 'exact frozen AW5 vectors')
        else:
            vector.write_text(vectors.target_vectors(5))
            require(sha(vector) == TARGET_VECTOR_SHA, 'approved targeted direct-integer vectors')
        remember(vector)
        build = scratch/'build'
        bench = 'rtl/tb/core27_prefill_normal_v2_threaded.cpp' if group == 'normal' else 'rtl/tb/core27_prefill_tail.cpp'
        argv = ['verilator','--cc','--exe','--build','-j','2','--threads','1','--top-module',top(group),
                '-GAW=5','-GNTT_LANES=64','-CFLAGS','-std=c++17 -Werror=return-type -DCORE27_PREFETCH_R2_RUNTIME_THREADS=1',
                '--Mdir',str(build),*[str(root/name) for name in compiled(root, group)],str(root/bench)]
        with LOCK.open('r') as lock:
            until = time.monotonic()+1800
            while True:
                try: fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB); break
                except BlockingIOError: guard(); require(time.monotonic() < until, 'compile lock timeout'); time.sleep(1)
            run('build', argv)
        exe = out/('V'+top(group)); shutil.copy2(build/exe.name, exe); remember(exe)
        require(sha(exe) == sha(build/exe.name), 'executable copy integrity')
        generated = {p.name: sha(p) for p in build.iterdir() if p.is_file() and p.suffix in ('.cpp','.h','.mk','.dat')}
        with tarfile.open(out/'generated-sources.tar.gz', 'x:gz') as tar:
            for name in sorted(generated): tar.add(build/name, arcname=name, recursive=False)
        report['generated_source_sha256'] = generated; remember(out/'generated-sources.tar.gz')
        baseline.check_probe(run('probe', [str(exe), '--runtime-probe']), 1)
        for name, command in commands(exe, vector, group):
            output = run(name, command)
            if group == 'normal': report['metrics'] = check_normal(output, parent)
            else:
                match = re.findall(r'^T5_TARGET_PASS .*$', output, re.M)
                require(len(match) == 1 and 'event_hits=1 ' in match[0], 'one targeted event reached')
                expected = (3,3,0) if name == 'changed-base' else (2,2,1) if name == 'base-reject' else (1,1,1)
                require(f'successful={expected[0]} readbacks={expected[1]} recoveries={expected[2]}' in match[0], 'target coverage/recovery')
                report.setdefault('target_results', []).append(match[0])
            require(sha(exe) == report['artifacts'][exe.name], 'executable drift')
        recheck(); guard()
        require(all(sha(out/name) == value for name, value in report['artifacts'].items()), 'artifact drift')
        require(all(sha(p) == value for p, value in report['tool_sha256'].items()), 'toolchain drift')
        report['status'] = 'passed_aw5_group_only'
    except BaseException as error:
        report.update(status='failed_or_incomplete', error=repr(error)); raise
    finally: save()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare', type=Path); p.add_argument('--execute', action='store_true')
    p.add_argument('--group', choices=GROUPS); p.add_argument('--output', type=Path)
    p.add_argument('--manifest', type=Path); p.add_argument('--manifest-sha')
    a = p.parse_args()
    if a.prepare:
        require(not a.execute and not any((a.group, a.output, a.manifest, a.manifest_sha)), 'exclusive preparation')
        prepare(a.prepare.resolve())
    else:
        require(a.execute and a.group and a.output and a.manifest and a.manifest_sha, 'explicit bounded execution')
        execute(a.output.resolve(), a.manifest.resolve(), a.manifest_sha, a.group)


if __name__ == '__main__': main()
