"""One fresh-control/four-mutant AW5 batch, or one bounded AW16 fault group.

Additive runner; no mutation of frozen ancestors, automatic dispatch, or promotion.
Native execution is restricted to an isolated aethia snapshot and two physical CPUs.
"""
import argparse
import fcntl
import gzip
import hashlib
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

sys.dont_write_bytecode = True

ROOT = Path('/home/jtl/gfn-fpga-lab/agent-work/core27-prefill-qualification-v2/snapshot-v1/fpga')
DESTINATION = ROOT.parent.parent
RUNNER = 'reference/core27_prefill_qualification_v2_regression.py'
RECIPES = 'reference/core27_prefill_qualification_v2.py'
OLD = 'reference/core27_prefill_adversarial_regression.py'
OLD_SHA = '5d6890d1027f3e77c716ca5e255be671f0dc0e982467a00884b24abfb5a72213'
AW16_RUNNER = 'reference/core27_prefill_aw16_regression.py'
AW16_RUNNER_SHA = '37fb46e26a79dd7ba1df96c17d27f4a5077cca3c417b8c63bb25801c36c4313d'
AW16_REPORT = 'results/throughput-20260929/core27-prefill-aw16-normal-v1/report.json'
AW16_SHA = 'c873de800c0e90891d9660ae27590a0edaa8bb7be30504ca3d4fe06a441b0209'
AW16_NORMAL = Path('/home/jtl/gfn-fpga-lab/agent-work/core27-prefill-aw16/normal-v1/report.json')
TEST = 'tests/test_core27_prefill_qualification_v2.py'
GIB, MIB = 1 << 30, 1 << 20


def require(ok, why):
    if not ok: raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def module(root, relative, digest):
    require(sha(root/relative) == digest, 'module source identity: '+relative)
    spec = importlib.util.spec_from_file_location('_t5_'+Path(relative).stem, root/relative)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def source_pins(root):
    old = module(root, OLD, OLD_SHA)
    pins = old.source_pins(root)
    require(pins[OLD] == OLD_SHA, 'immutable AW5 runner')
    require(sha(root/AW16_REPORT) == AW16_SHA, 'AW16 normal prerequisite identity')
    normal = json.loads((root/AW16_REPORT).read_text())
    for name, digest in normal['sources'].items():
        require(name not in pins or pins[name] == digest, 'shared normal ancestry agreement')
        pins[name] = digest
    pins.update({AW16_REPORT: AW16_SHA, AW16_RUNNER: AW16_RUNNER_SHA})
    for name in (RUNNER, RECIPES, TEST): pins[name] = sha(root/name)
    for name, digest in pins.items():
        path = root/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and not path.is_symlink()
                and path.resolve().is_relative_to(root) and sha(path) == digest, 'closed source path/hash: '+name)
    return old, pins


def prepare(out):
    root = Path(__file__).resolve().parents[1]
    old, pins = source_pins(root)
    recipes = module(root, RECIPES, pins[RECIPES])
    require(not out.exists(), 'fresh stage output'); out.mkdir(parents=True)
    with tarfile.open(out/'source.tar.gz', 'x:gz') as tar:
        for name in sorted(pins): tar.add(root/name, arcname='fpga/'+name, recursive=False)
    require(source_pins(root)[1] == pins, 'prepare source drift')
    manifest = dict(status='prepared_not_executed', target=str(ROOT), sources=pins,
                    archive_sha256=sha(out/'source.tar.gz'), mutations=list(recipes.REMAINING),
                    aw16_groups=list(recipes.AW16_GROUPS), compiled=old.compiled(root, 'reset-tail'),
                    observer_state_mapping=old.validate_observer_states(root),
                    shared_control_guard_removal='T5_EMIT_SIGNED32_REPRESENTATION',
                    limitation='AW5 four-contract batch or one AW16 fault group; no promotion or automatic execution.')
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(manifest_sha256=sha(out/'manifest.json'), archive_sha256=manifest['archive_sha256'], files=len(pins))))
    return manifest


def verify(root, path, digest):
    require(re.fullmatch('[0-9a-f]{64}', digest) is not None and sha(path) == digest, 'approved manifest identity')
    old, pins = source_pins(root)
    manifest = json.loads(path.read_text())
    require(manifest['sources'] == pins, 'approved pre-import source closure')
    recipes = module(root, RECIPES, pins[RECIPES])
    require(manifest['status'] == 'prepared_not_executed' and manifest['target'] == str(ROOT) and
            manifest['sources'] == pins and manifest['mutations'] == list(recipes.REMAINING) and
            manifest['aw16_groups'] == list(recipes.AW16_GROUPS) and
            manifest['compiled'] == old.compiled(root, 'reset-tail') and
            manifest['observer_state_mapping'] == old.validate_observer_states(root) and
            manifest['shared_control_guard_removal'] == 'T5_EMIT_SIGNED32_REPRESENTATION', 'exact qualification manifest')
    return old, recipes, pins


def aw16_prerequisite(root, path, baseline):
    require(path == AW16_NORMAL and path.resolve() == path and sha(path) == AW16_SHA, 'exact AW16 normal path/hash')
    report = json.loads(path.read_text())
    normal = module(root, AW16_RUNNER, AW16_RUNNER_SHA)
    require(report['status'] == 'passed_aw16_normal_only' and report['aw'] == 16 and report['group'] == 'normal'
            and report['sources'] == normal.source_pins(root) and report['compile_workers'] == 2 and
            report['model_threads'] == 1, 'source-matched passed AW16 normal')
    for name, digest in report['artifacts'].items():
        artifact = path.parent/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and not artifact.is_symlink()
                and artifact.resolve().is_relative_to(path.parent) and sha(artifact) == digest, 'AW16 prerequisite artifact closure')
    require([step['name'] for step in report['steps']] == ['verilator-version', 'compiler-version', 'build', 'probe', 'normal']
            and all(step['returncode'] == 0 and step['error'] is None for step in report['steps']), 'AW16 native steps')
    baseline.check_probe((path.parent/'probe.log').read_text(), 1)
    parent = json.loads((root/normal.NORMAL_REPORT).read_text())
    require(normal.check_normal((path.parent/'normal.log').read_text(), parent) == report['metrics'] and
            report['vectors'] == parent['vectors'], 'AW16 normal actual-output replay')
    return report


def execute(out, manifest_path, manifest_sha, normal_path, mode, group, cpus):
    require(__debug__ and socket.gethostname() == 'aethia', 'aethia assertions-only execution')
    root = Path(__file__).resolve().parents[1]
    require(root == ROOT and root.resolve() == ROOT, 'fixed isolated snapshot')
    require(out.resolve().parent == DESTINATION and not out.exists(), 'fresh isolated output')
    old, recipes, pins = verify(root, manifest_path, manifest_sha)
    require(mode in ('batch', 'aw16-group') and ((mode == 'batch' and group is None) or group in recipes.AW16_GROUPS), 'explicit bounded mode')
    baseline, normal, recipe, vectors = old.load_project(root, old.source_pins(root))
    normal_sha = old.NORMAL_T5_SHA if mode == 'batch' else AW16_SHA
    def prerequisite():
        return old.normal_prerequisite(root, normal_path, normal_sha, baseline, normal) if mode == 'batch' else aw16_prerequisite(root, normal_path, baseline)
    prior = prerequisite()
    limits = baseline.execution_limits()
    require(len(cpus) == 2 and len(set(cpus)) == 2 and limits['affinity'] == list(cpus) and
            len({tuple(x) for x in limits['physical_cores']}) == 2, 'exact requested two distinct physical CPUs; taskset required')
    require(old.LOCK.is_file() and old.LOCK.resolve() == old.LOCK, 'shared exclusive compiler lock')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); resource.setrlimit(resource.RLIMIT_AS, (6*GIB, 6*GIB))
    out.mkdir(); scratch = Path(tempfile.mkdtemp(prefix='gfn16-t5-qualification-v2-', dir='/dev/shm')); os.chmod(scratch, 0o700)
    temporary = scratch/'tmp'; temporary.mkdir()
    started = time.monotonic(); budget = 10800 if mode == 'batch' else 7200
    reserve = (3840 if mode == 'batch' else 768)*MIB
    report = dict(status='running', mode=mode, group=group, aw=5 if mode == 'batch' else 16,
                  sources=pins, manifest_sha256=manifest_sha, prerequisite_normal_sha256=normal_sha,
                  limits=limits, compile_workers=2, model_threads=1, compiler_lock=str(old.LOCK),
                  lock_policy='exclusive shared lock; one compile at a time', steps=[], artifacts={}, builds={}, receipts=[],
                  scratch=str(scratch), scratch_reservation_bytes=reserve, scratch_free_floor_bytes=2*GIB,
                  durable_reservation_bytes=128*MIB, durable_free_floor_bytes=10*GIB, host_memory_floor_bytes=4*GIB,
                  command_timeout_seconds=1800, total_budget_seconds=budget, lock_wait_timeout_seconds=1800,
                  cleanup='All scratch and failed evidence retained; no deletion.',
                  limitation='Qualification only; no clock, fit, full-PRP or aggregate promotion.')
    def remember(path): report['artifacts'][str(path.relative_to(out))] = sha(path)
    def save(): (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    def guard():
        require(time.monotonic()-started < budget, 'total qualification time budget')
        require(shutil.disk_usage(out).free >= 10*GIB+max(0, 128*MIB-baseline.allocated_bytes(out)), 'durable reservation/floor')
        require(shutil.disk_usage(scratch).free >= 2*GIB+max(0, reserve-baseline.allocated_bytes(scratch)), 'tmpfs reservation/floor')
        mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024 >= 4*GIB, 'host memory floor')
    def recheck():
        require(source_pins(root)[1] == pins and sha(manifest_path) == manifest_sha and sha(normal_path) == normal_sha,
                'source/manifest/prerequisite drift')
    env = {k:v for k,v in os.environ.items() if k not in ('MAKEFLAGS', 'MFLAGS', 'CFLAGS', 'CXXFLAGS', 'CPPFLAGS', 'LDFLAGS',
           'CC', 'CXX', 'AR', 'OBJCACHE', 'OPT_FAST', 'OPT_SLOW', 'OPT_GLOBAL', 'TMPDIR', 'TMP', 'TEMP', 'PYTHONPATH') and not k.startswith('NTT_')}
    env.update(TMPDIR=str(temporary), TMP=str(temporary), TEMP=str(temporary), CCACHE_DISABLE='1', PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE='1')
    def run(name, argv, abort_expected=False):
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
        require(child.returncode == (-6 if abort_expected else 0), 'unexpected native return code: '+name)
        guard(); return log.read_text(), child.returncode
    def build(role, derived, harness):
        directory = scratch/('build-'+role); require(not directory.exists(), 'fresh per-role build')
        overlay = out/('derived-'+role); overlay.mkdir()
        for relative, source in derived.items():
            target = overlay/relative; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(source); remember(target)
        sources = [overlay/name if name in derived else root/name for name in old.compiled(root, 'reset-tail')]
        argv = ['verilator', '--cc', '--exe', '--build', '-j', '2', '--threads', '1', '--top-module', 'core27_prefill_tail_probe_v3',
                '-GAW='+str(report['aw']), '-GNTT_LANES=64', '-CFLAGS', '-std=c++17 -Werror=return-type',
                '--Mdir', str(directory), *map(str, sources), str(harness)]
        with old.LOCK.open('r') as lock:
            deadline = time.monotonic()+1800
            while True:
                try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB); break
                except BlockingIOError: guard(); require(time.monotonic() < deadline, 'compile lock timeout'); time.sleep(1)
            run('build-'+role, argv)
        exe = directory/'Vcore27_prefill_tail_probe_v3'
        archive = out/('model-'+role+'.gz'); executable_identity = old.compressed_executable(exe, archive); remember(archive)
        generated = {p.name:sha(p) for p in directory.iterdir() if p.is_file() and p.suffix in ('.cpp', '.h', '.mk', '.dat')}
        generated_archive = out/('generated-'+role+'.tar.gz')
        with tarfile.open(generated_archive, 'x:gz') as tar:
            for name in sorted(generated): tar.add(directory/name, arcname=name, recursive=False)
        remember(generated_archive)
        baseline.check_probe(run('probe-'+role, [str(exe), '--runtime-probe'])[0], 1)
        report['builds'][role] = dict(derived_sources={name:sha(overlay/name) for name in derived},
            compiled_source_order=[str(p) for p in sources], compiled_source_sha256={str(p):sha(p) for p in sources},
            harness=str(harness), harness_sha256=sha(harness), executable=str(exe), executable_sha256=sha(exe),
            executable_archive=archive.name, executable_archive_identity=executable_identity,
            generated_archive=generated_archive.name, generated_source_sha256=generated, fresh_build_directory=str(directory),
            probe_log='probe-'+role+'.log', probe_sha256=sha(out/('probe-'+role+'.log')))
        save(); return exe
    try:
        guard(); recheck()
        tools = [Path(sys.executable).resolve()]
        for name in ('g++', 'verilator', 'verilator_bin', 'make'):
            found = shutil.which(name); require(found is not None, 'missing '+name); tools.append(Path(found).resolve())
        report['tool_sha256'] = {str(path):sha(path) for path in tools}; report['python_version'] = sys.version
        report['verilator_version'] = run('verilator-version', ['verilator', '--version'])[0].strip()
        report['compiler_version'] = run('compiler-version', ['g++', '--version'])[0].strip()
        shutil.copyfile(manifest_path, out/'approved-manifest.json'); remember(out/'approved-manifest.json')
        shutil.copyfile(normal_path, out/'prerequisite-normal-report.json'); remember(out/'prerequisite-normal-report.json')
        with tarfile.open(out/'sources.tar.gz', 'x:gz') as tar:
            for name in sorted(pins): tar.add(root/name, arcname=name, recursive=False)
        remember(out/'sources.tar.gz')
        vector = out/'vectors.txt'
        # Full-N ordinary-integer oracle runs only inside this bounded native
        # dispatch, never during local preparation/tests and never via NTT.
        oracle_start = time.monotonic()
        if mode == 'batch': vector.write_text(vectors.target_vectors(5))
        else: run('integer-oracle', [sys.executable, '-B', str(root/RECIPES), '--output', str(vector)])
        remember(vector)
        report['oracle_seconds'] = time.monotonic()-oracle_start; report['vector_sha256'] = sha(vector)
        if mode == 'batch': require(sha(vector) == old.TARGET_VECTOR_SHA, 'exact AW5 vectors')
        guard(); recheck()
        harness = root/'rtl/tb/core27_prefill_adversarial_v1.cpp'
        if mode == 'batch':
            control, mutants = recipes.batch_sources(root, recipe, recipes.REMAINING)
            report['shared_control_guard_removal'] = 'T5_EMIT_SIGNED32_REPRESENTATION'
            control_exe = build('shared-control', control, harness)
            controls = {}
            # Every command runs against the same fresh executable in a fresh
            # process before any mutant executes; no cross-process DUT state.
            for name in recipes.REMAINING:
                argv = recipe.command(control_exe, vector, name)
                output, _ = run('control-'+name, argv)
                controls[name] = dict(command=argv, footer=recipe.check_footer(output, argv),
                    executable_sha256=sha(control_exe), log='control-'+name+'.log', log_sha256=sha(out/('control-'+name+'.log')))
            report['shared_control_cases'] = controls; save()
            for name in recipes.REMAINING:
                derived, contract = mutants[name]
                receipt = dict(name=name, status='running', contract=contract, control=controls[name],
                               sources=pins, manifest_sha256=manifest_sha, tool_sha256=report['tool_sha256'],
                               vector_sha256=sha(vector), control_build=report['builds']['shared-control'])
                receipt_path = out/('receipt-'+name+'.json')
                def save_receipt(): receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
                save_receipt()
                try:
                    exe = build(name, derived, harness); receipt['mutant_build'] = report['builds'][name]
                    argv = recipe.command(exe, vector, name)
                    require(argv[1:] == controls[name]['command'][1:], 'identical mutant/control command')
                    output, code = run('mutant-'+name, argv, abort_expected=True)
                    receipt.update(status='passed_typed_mutation_with_shared_fresh_control', command=argv,
                        typed_rejection=recipe.check_fatal(output, code, contract), log='mutant-'+name+'.log',
                        log_sha256=sha(out/('mutant-'+name+'.log')))
                except BaseException as error:
                    receipt.update(status='failed_or_incomplete', error=repr(error)); raise
                finally:
                    save_receipt(); remember(receipt_path); report['receipts'].append(receipt_path.name); save()
            require(len(report['builds']) == 5 and len(report['receipts']) == 4, 'one fresh control plus four fresh mutant builds')
            passed_status = 'passed_four_mutation_contracts_only'
        else:
            harness_path = out/'core27_prefill_adversarial_aw16.cpp'
            harness_path.write_text(recipes.aw16_harness(harness.read_text())); remember(harness_path)
            original = {name:(root/name).read_text() for name in (recipe.CORE, recipe.CARRY, recipe.BRIDGE)}
            exe = build('aw16-'+group, original, harness_path)
            report['cases'] = []
            for name, argv in recipes.group_commands(exe, vector, group):
                output, _ = run(name, argv)
                report['cases'].append(dict(name=name, command=argv, footer=recipes.check_aw16_footer(output, argv),
                                            log=name+'.log', log_sha256=sha(out/(name+'.log')))); save()
            require(1 <= len(report['cases']) <= 7, 'one bounded AW16 group')
            passed_status = 'passed_one_aw16_targeted_group_only'
        recheck(); guard(); require(prerequisite() == prior, 'normal prerequisite drift')
        require(all(sha(out/name) == digest for name, digest in report['artifacts'].items()), 'artifact drift')
        require(all(sha(path) == digest for path, digest in report['tool_sha256'].items()), 'toolchain drift')
        for entry in report['builds'].values():
            require(sha(entry['executable']) == entry['executable_sha256'], 'native model drift')
            with gzip.open(out/entry['executable_archive'], 'rb') as stream:
                require(hashlib.file_digest(stream, 'sha256').hexdigest() == entry['executable_sha256'], 'durable executable identity')
        report['status'] = passed_status
    except BaseException as error:
        report.update(status='failed_or_incomplete', error=repr(error)); raise
    finally: save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', type=Path); parser.add_argument('--execute', action='store_true')
    parser.add_argument('--mode', choices=('batch', 'aw16-group')); parser.add_argument('--group')
    parser.add_argument('--output', type=Path); parser.add_argument('--manifest', type=Path); parser.add_argument('--manifest-sha')
    parser.add_argument('--normal-report', type=Path); parser.add_argument('--cpus', help='exact two sorted taskset CPU IDs, e.g. 0,2')
    args = parser.parse_args()
    if args.prepare:
        require(not any((args.execute, args.mode, args.group, args.output, args.manifest, args.manifest_sha, args.normal_report, args.cpus)), 'exclusive preparation')
        prepare(args.prepare.resolve())
    else:
        require(args.execute and args.mode and args.output and args.manifest and args.manifest_sha and args.normal_report and args.cpus,
                'explicit native mode, evidence and affinity required')
        cpus = tuple(map(int, args.cpus.split(','))); require(list(cpus) == sorted(cpus), 'sorted explicit CPUs')
        execute(args.output.resolve(), args.manifest.resolve(), args.manifest_sha, args.normal_report.resolve(), args.mode, args.group, cpus)


if __name__ == '__main__': main()
