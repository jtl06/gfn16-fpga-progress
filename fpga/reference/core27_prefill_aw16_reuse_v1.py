"""Source-bound reuse of one successful AW16 fault executable; no compilation.

One selected list of remaining groups, at most two one-core native processes.
Every case is a fresh process. Failed, altered and foreign models are rejected.
"""
import argparse
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
import time

sys.dont_write_bytecode = True
ROOT = Path('/home/jtl/gfn-fpga-lab/agent-work/core27-prefill-aw16-reuse-v1/snapshot-v1/fpga')
DESTINATION = ROOT.parent.parent
RUNNER = 'reference/core27_prefill_aw16_reuse_v1.py'
TEST = 'tests/test_core27_prefill_aw16_reuse_v1.py'
FROZEN = 'reference/core27_prefill_qualification_v2_regression.py'
FROZEN_SHA = 'e56df3c738c9c6bbf6a3bc18bbc98c4cfdc041edd5d83d4a0ca7a6b9bfcabe96'
PRE_MANIFEST = 'results/throughput-20260929/core27-prefill-qualification-v2-stage-v1/manifest.json'
PRE_MANIFEST_SHA = '01419313953b539752bcc3cfd862c75c9cbd408cd3d334076658cfd61e4ea9fb'
PRE_DIRECTORY = 'results/throughput-20260929/core27-prefill-aw16-reset-middle-v2'
PRE_REPORT_SHA = '398533fe82384b6027112f220668c132c09ee63e9a7e90c6b74119ad31c27375'
PRE_NATIVE = Path('/home/jtl/gfn-fpga-lab/agent-work/core27-prefill-qualification-v2/aw16-reset-middle-v1')
ROLE = 'aw16-reset-middle'
GIB, MIB = 1 << 30, 1 << 20


def require(ok, why):
    if not ok: raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_file(directory, name):
    path = directory/name
    require(not Path(name).is_absolute() and '..' not in Path(name).parts and not path.is_symlink()
            and path.resolve().is_relative_to(directory.resolve()) and path.is_file(), 'safe regular evidence file: '+name)
    return path


def archive_inventory(path, expected):
    actual = {}
    with tarfile.open(path, 'r:gz') as archive:
        for item in archive:
            require(item.isfile() and not Path(item.name).is_absolute() and '..' not in Path(item.name).parts
                    and item.name not in actual, 'safe unique regular archive member')
            actual[item.name] = hashlib.file_digest(archive.extractfile(item), 'sha256').hexdigest()
    require(actual == expected, 'complete archive inventory/hash identity')
    return len(actual)


def frozen_modules(root):
    require(sha(root/FROZEN) == FROZEN_SHA, 'immutable qualification-v2 runner')
    spec = importlib.util.spec_from_file_location('_t5_qualification_v2', root/FROZEN)
    frozen = importlib.util.module_from_spec(spec); spec.loader.exec_module(frozen)
    old, recipes, pins = frozen.verify(root, root/PRE_MANIFEST, PRE_MANIFEST_SHA)
    return frozen, old, recipes, pins


def predecessor(root):
    """Read-only archive replay, including exact build and seven case commands."""
    frozen, old, recipes, pins = frozen_modules(root)
    directory = root/PRE_DIRECTORY
    require(sha(safe_file(directory, 'report.json')) == PRE_REPORT_SHA, 'exact successful predecessor report')
    report = json.loads((directory/'report.json').read_text())
    require(report['status'] == 'passed_one_aw16_targeted_group_only' and report['mode'] == 'aw16-group'
            and report['group'] == 'reset-middle' and report['aw'] == 16, 'successful AW16 reset-middle prerequisite')
    require(report['sources'] == pins and len(pins) == 113 and report['manifest_sha256'] == PRE_MANIFEST_SHA
            and sha(directory/'approved-manifest.json') == PRE_MANIFEST_SHA, 'approved predecessor source/manifest closure')
    require(report['prerequisite_normal_sha256'] == frozen.AW16_SHA and
            sha(directory/'prerequisite-normal-report.json') == frozen.AW16_SHA, 'passed normal prerequisite binding')
    for name, digest in report['artifacts'].items():
        require(sha(safe_file(directory, name)) == digest, 'predecessor artifact identity: '+name)
    archive_inventory(directory/'sources.tar.gz', pins)
    require(set(report['builds']) == {ROLE}, 'one original AW16 build')
    build = report['builds'][ROLE]
    archive_inventory(safe_file(directory, build['generated_archive']), build['generated_source_sha256'])
    core = 'rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill.sv'
    carry = 'rtl/kernel/genefer_carry_prefix_stream_precision_emit.sv'
    bridge = 'rtl/tb/core27_prefill_fault_bridge.sv'
    require(build['derived_sources'] == {name:pins[name] for name in (core, carry, bridge)},
            'pristine AW16 production assertions and exact zero-capable fault bridge')
    for name, digest in build['derived_sources'].items():
        require(sha(safe_file(directory, 'derived-'+ROLE+'/'+name)) == digest, 'original AW16 overlay identity')
    harness_name = 'core27_prefill_adversarial_aw16.cpp'
    harness = safe_file(directory, harness_name)
    require(harness.read_text() == recipes.aw16_harness((root/'rtl/tb/core27_prefill_adversarial_v1.cpp').read_text())
            and sha(harness) == build['harness_sha256'] and build['harness'] == str(PRE_NATIVE/harness_name), 'exact derived AW16 harness')
    expected_sources = [str(PRE_NATIVE/('derived-'+ROLE)/name) if name in build['derived_sources'] else str(frozen.ROOT/name)
                        for name in old.compiled(root, 'reset-tail')]
    require(build['compiled_source_order'] == expected_sources and
            build['compiled_source_sha256'] == dict(zip(expected_sources, [pins[name] for name in old.compiled(root, 'reset-tail')])),
            'exact ordered compiled source identity')
    require(build['fresh_build_directory'] == report['scratch']+'/build-'+ROLE and
            build['executable'] == build['fresh_build_directory']+'/Vcore27_prefill_tail_probe_v3', 'fresh predecessor model path')
    model = safe_file(directory, build['executable_archive']); identity = build['executable_archive_identity']
    require(sha(model) == identity['compressed_sha256'] and model.stat().st_size == identity['compressed_bytes'], 'compressed model identity')
    with gzip.open(model, 'rb') as stream: model_bytes = stream.read()
    require(hashlib.sha256(model_bytes).hexdigest() == identity['uncompressed_sha256'] == build['executable_sha256']
            and len(model_bytes) == identity['uncompressed_bytes'] and model_bytes.startswith(b'\x7fELF'), 'exact native ELF model identity')
    require(sha(directory/'vectors.txt') == report['vector_sha256'], 'exact previously passed AW16 vectors')
    vector_values = list(map(int, (directory/'vectors.txt').read_text().split()))
    require(vector_values[:3] == [65536, 604832956, 1000000000] and len(vector_values) == 3+4*65536
            and vector_values[3+65536] >= 2*65536+5, 'AW16 vector geometry and early invalid digit')
    probe_name = 'probe-'+ROLE+'.log'
    require(build['probe_log'] == probe_name and build['probe_sha256'] == sha(directory/probe_name) and
            json.loads((directory/probe_name).read_text()) == dict(context_threads=1, model_threads=1, expected_threads=1), 'predecessor runtime probe')
    expected_cases = recipes.group_commands(build['executable'], PRE_NATIVE/'vectors.txt', 'reset-middle')
    require(len(report['cases']) == 7, 'all seven reset-middle cases')
    for case, (name, argv) in zip(report['cases'], expected_cases):
        require(case['name'] == name and case['command'] == argv and case['log'] == name+'.log'
                and case['log_sha256'] == sha(directory/case['log']), 'predecessor case command/log identity')
        output = (directory/case['log']).read_text()
        require(not any(marker in output for marker in ('%Fatal', '%Error', 'Assertion failed')) and
                case['footer'] == recipes.check_aw16_footer(output, argv), 'predecessor command-bound positive footer')
    expected_names = ['verilator-version', 'compiler-version', 'integer-oracle', 'build-'+ROLE, 'probe-'+ROLE]+[name for name, _ in expected_cases]
    require([step['name'] for step in report['steps']] == expected_names, 'complete successful predecessor step order')
    steps = {step['name']:step for step in report['steps']}
    for step in report['steps']:
        require(step['returncode'] == 0 and step['error'] is None and step['log'] == step['name']+'.log'
                and sha(directory/step['log']) == step['sha256'], 'successful predecessor native step')
    expected_build = ['verilator', '--cc', '--exe', '--build', '-j', '2', '--threads', '1', '--top-module',
        'core27_prefill_tail_probe_v3', '-GAW=16', '-GNTT_LANES=64', '-CFLAGS', '-std=c++17 -Werror=return-type',
        '--Mdir', build['fresh_build_directory'], *expected_sources, str(PRE_NATIVE/harness_name)]
    require(steps['build-'+ROLE]['command'] == expected_build and
            steps['probe-'+ROLE]['command'] == [build['executable'], '--runtime-probe'], 'exact predecessor build/probe argv')
    for name, argv in expected_cases: require(steps[name]['command'] == argv, 'predecessor step/case argv agreement')
    require(report['model_threads'] == 1 and report['compile_workers'] == 2 and
            len(report['limits']['affinity']) == 2 and len({tuple(x) for x in report['limits']['physical_cores']}) == 2,
            'bounded predecessor thread/core provenance')
    quota, period = map(int, report['limits']['cpu_max'])
    require(quota <= 2*period and report['limits']['memory_max_bytes'] <= 6*GIB, 'bounded predecessor cgroup')
    return frozen, old, recipes, pins, report


def selected_cases(recipes, groups, exe, vector):
    remaining = tuple(group for group in recipes.AW16_GROUPS if group != 'reset-middle')
    require(1 <= len(groups) <= 10 and len(set(groups)) == len(groups) and all(group in remaining for group in groups),
            'unique explicit remaining AW16 groups only')
    result = [(group, name, argv) for group in groups for name, argv in recipes.group_commands(exe, vector, group)]
    require(1 <= len(result) <= 59 and len({name for _, name, _ in result}) == len(result), 'bounded unique selected cases')
    return result


def source_pins(root):
    _, _, _, pins = frozen_modules(root)
    return dict(pins, **{PRE_MANIFEST:PRE_MANIFEST_SHA, RUNNER:sha(root/RUNNER), TEST:sha(root/TEST)})


def evidence_pins(root, prior):
    return {PRE_DIRECTORY+'/'+name:digest for name, digest in dict(prior['artifacts'], **{'report.json':PRE_REPORT_SHA}).items()}


def prepare(out):
    root = Path(__file__).resolve().parents[1]
    _, _, _, _, prior = predecessor(root)
    sources, evidence = source_pins(root), evidence_pins(root, prior)
    require(not out.exists(), 'fresh reuse stage'); out.mkdir(parents=True)
    with tarfile.open(out/'source.tar.gz', 'x:gz') as archive:
        for name in sorted(sources | evidence): archive.add(root/name, arcname='fpga/'+name, recursive=False)
    require(source_pins(root) == sources and all(sha(root/name) == digest for name, digest in evidence.items()), 'stage input drift')
    manifest = dict(status='prepared_not_executed', target=str(ROOT), sources=sources, evidence=evidence,
                    predecessor_report_sha256=PRE_REPORT_SHA, predecessor_manifest_sha256=PRE_MANIFEST_SHA,
                    archive_sha256=sha(out/'source.tar.gz'), modes=['selected-aw16-groups-reuse'], max_cases=59,
                    max_concurrent_processes=2, threads_per_process=1, compile_allowed=False,
                    limitation='Reuse exact passed AW16 reset-middle model only; selected groups are new evidence, no aggregate/clock promotion.')
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(manifest_sha256=sha(out/'manifest.json'), archive_sha256=manifest['archive_sha256'],
                         sources=len(sources), evidence_files=len(evidence))))
    return manifest


def verify_manifest(root, path, digest):
    require(re.fullmatch('[0-9a-f]{64}', digest) is not None and sha(path) == digest, 'approved reuse manifest identity')
    manifest = json.loads(path.read_text())
    require(manifest['status'] == 'prepared_not_executed' and manifest['target'] == str(ROOT) and
            manifest['sources'] == source_pins(root) and manifest['predecessor_report_sha256'] == PRE_REPORT_SHA and
            manifest['predecessor_manifest_sha256'] == PRE_MANIFEST_SHA and manifest['max_cases'] == 59 and
            manifest['max_concurrent_processes'] == 2 and manifest['threads_per_process'] == 1 and
            manifest['compile_allowed'] is False and manifest['modes'] == ['selected-aw16-groups-reuse'], 'exact reuse profile/source closure')
    for name, digest in manifest['sources'].items(): require(sha(safe_file(root, name)) == digest, 'reuse source identity')
    frozen, old, recipes, _, prior = predecessor(root)
    require(manifest['evidence'] == evidence_pins(root, prior), 'complete predecessor evidence closure')
    return manifest, frozen, old, recipes, prior


def validate_source_review(path, digest, manifest, manifest_sha):
    require(re.fullmatch('[0-9a-f]{64}', digest) is not None and sha(path) == digest, 'approved independent source review identity')
    review = json.loads(path.read_text())
    require(review['status'] == 'PASS_scoped_AW16_reuse_source_admission' and review['manifest_sha256'] == manifest_sha
            and review['predecessor_report_sha256'] == PRE_REPORT_SHA and review['sources'] == manifest['sources'],
            'independent admission binds entire reuse source closure and predecessor')
    return review


def execute(out, path, digest, review_path, review_sha, groups, cpus, concurrency):
    require(__debug__ and socket.gethostname() == 'aethia', 'aethia with assertions enabled only')
    root = Path(__file__).resolve().parents[1]
    require(root == ROOT and root.resolve() == ROOT, 'fixed isolated reuse snapshot')
    require(out.resolve().parent == DESTINATION and not out.exists(), 'fresh isolated reuse output')
    manifest, frozen, old, recipes, prior = verify_manifest(root, path, digest)
    validate_source_review(review_path, review_sha, manifest, digest)
    require(concurrency in (1, 2), 'at most two fresh native processes')
    baseline, _, _, _ = old.load_project(root, old.source_pins(root))
    limits = baseline.execution_limits()
    require(len(cpus) == 2 and list(cpus) == sorted(set(cpus)) and limits['affinity'] == list(cpus) and
            len({tuple(x) for x in limits['physical_cores']}) == 2, 'explicit distinct two-physical-core taskset affinity')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); resource.setrlimit(resource.RLIMIT_AS, (6*GIB, 6*GIB))
    frozen.aw16_prerequisite(root, frozen.AW16_NORMAL, baseline)
    current_tools = {name:sha(name) for name in prior['tool_sha256']}
    require(current_tools == prior['tool_sha256'] and str(Path(sys.executable).resolve()) in current_tools and
            sys.version == prior['python_version'], 'same host/tool/Python fingerprint; foreign models prohibited')
    taskset = shutil.which('taskset'); require(taskset is not None, 'taskset required')
    taskset = str(Path(taskset).resolve()); current_tools[taskset] = sha(taskset)
    out.mkdir(); started = time.monotonic()
    report = dict(status='running', mode='selected-aw16-groups-reuse', aw=16, groups=list(groups),
        sources=manifest['sources'], manifest_sha256=digest, source_review_sha256=review_sha,
        predecessor_report_sha256=PRE_REPORT_SHA, predecessor_manifest_sha256=PRE_MANIFEST_SHA,
        predecessor_build=prior['builds'][ROLE], vector_sha256=prior['vector_sha256'], tool_sha256=current_tools,
        limits=limits, max_concurrent_processes=concurrency, threads_per_process=1, compile_workers=0,
        command_timeout_seconds=1800, total_budget_seconds=9000, durable_free_floor_bytes=10*GIB,
        durable_reservation_bytes=128*MIB, host_memory_floor_bytes=4*GIB, child_address_space_limit_bytes=3*GIB,
        steps=[], receipts=[], artifacts={}, cleanup='All outputs and failures retained; no deletion.',
        limitation='New selected AW16 cases using exact successful predecessor model; no full T5 or physical promotion.')
    active, probes = {}, {}
    def remember(p): report['artifacts'][str(p.relative_to(out))] = sha(p)
    def save(): (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    def guard():
        require(time.monotonic()-started < 9000, 'total reuse dispatch time budget')
        require(shutil.disk_usage(out).free >= 10*GIB+max(0, 128*MIB-baseline.allocated_bytes(out)), 'durable reservation/floor')
        mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024 >= 4*GIB, 'host available-memory floor')
    def recheck():
        require(sha(path) == digest and sha(review_path) == review_sha, 'manifest/review drift')
        require(all(sha(root/name) == value for name, value in (manifest['sources'] | manifest['evidence']).items()), 'source/evidence drift')
        require(all(sha(name) == value for name, value in current_tools.items()), 'toolchain drift')
        if (out/'model').exists(): require(sha(out/'model') == prior['builds'][ROLE]['executable_sha256'], 'reused native model drift')
        if (out/'vectors.txt').exists(): require(sha(out/'vectors.txt') == prior['vector_sha256'], 'reused vector drift')
    env = {k:v for k,v in os.environ.items() if k not in ('PYTHONPATH', 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'TMPDIR', 'TMP', 'TEMP')
           and not k.startswith('NTT_')}
    env.update(PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(out), TMP=str(out), TEMP=str(out))
    def launch(name, argv, cpu, group=None):
        guard(); recheck()
        log = out/(name+'.log'); stream = log.open('x')
        command = [taskset, '-c', str(cpu), *argv]
        def isolate():
            os.sched_setaffinity(0, {cpu})
            resource.setrlimit(resource.RLIMIT_AS, (3*GIB, 3*GIB))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        try: child = subprocess.Popen(command, cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                      start_new_session=True, preexec_fn=isolate)
        except BaseException:
            stream.close(); remember(log); raise
        entry = dict(name=name, child=child, stream=stream, log=log, command=command, model_command=argv,
                     cpu=cpu, group=group, started=time.monotonic())
        active[cpu] = entry
        require(sorted(os.sched_getaffinity(child.pid)) == [cpu], 'actual native process singleton affinity')
        return entry
    def finish(cpu, error=None):
        entry = active.pop(cpu); child = entry['child']; child.wait(); entry['stream'].close()
        remember(entry['log'])
        step = dict(name=entry['name'], command=entry['command'], model_command=entry['model_command'], cpu=cpu,
                    observed_affinity=[cpu], returncode=child.returncode, seconds=time.monotonic()-entry['started'],
                    error=repr(error) if error else None, log=entry['log'].name, sha256=sha(entry['log']))
        report['steps'].append(step)
        receipt = dict(status='failed_or_incomplete', group=entry['group'], **step, manifest_sha256=digest,
                       source_review_sha256=review_sha, predecessor_report_sha256=PRE_REPORT_SHA,
                       executable_sha256=prior['builds'][ROLE]['executable_sha256'], vector_sha256=prior['vector_sha256'],
                       tool_sha256=current_tools, sources=manifest['sources'])
        try:
            require(error is None and child.returncode == 0, 'successful native process: '+entry['name'])
            output = entry['log'].read_text()
            require(not any(marker in output for marker in ('%Fatal', '%Error', 'Assertion failed')), 'no native assertion failure')
            if entry['group'] is None:
                baseline.check_probe(output, 1); receipt['probe'] = json.loads(output)
            else:
                require(cpu in probes, 'successful singleton-core runtime probe before case')
                receipt['runtime_probe'] = probes[cpu]
                receipt['footer'] = recipes.check_aw16_footer(output, entry['model_command'])
            receipt['status'] = 'passed_runtime_probe' if entry['group'] is None else 'passed_aw16_case_only'
        except BaseException as failure:
            receipt['error'] = repr(failure); raise
        finally:
            receipt_path = out/('receipt-'+entry['name']+'.json')
            receipt_path.write_text(json.dumps(receipt, indent=2)+'\n'); remember(receipt_path)
            report['receipts'].append(receipt_path.name); save()
        if entry['group'] is None:
            probes[cpu] = dict(receipt=receipt_path.name, receipt_sha256=sha(receipt_path),
                               log=entry['log'].name, log_sha256=sha(entry['log']), observed_affinity=[cpu])
        return receipt
    try:
        guard(); recheck()
        shutil.copyfile(path, out/'approved-manifest.json'); remember(out/'approved-manifest.json')
        shutil.copyfile(review_path, out/'source-review.json'); remember(out/'source-review.json')
        shutil.copyfile(root/PRE_DIRECTORY/'report.json', out/'predecessor-report.json'); remember(out/'predecessor-report.json')
        with tarfile.open(out/'sources.tar.gz', 'x:gz') as archive:
            for name in sorted(manifest['sources']): archive.add(root/name, arcname=name, recursive=False)
        remember(out/'sources.tar.gz')
        model = out/'model'
        with gzip.open(root/PRE_DIRECTORY/prior['builds'][ROLE]['executable_archive'], 'rb') as source, model.open('xb') as target:
            shutil.copyfileobj(source, target, 1 << 20)
        model.chmod(0o500); remember(model)
        vector = out/'vectors.txt'; shutil.copyfile(root/PRE_DIRECTORY/'vectors.txt', vector); remember(vector)
        cases = selected_cases(recipes, groups, model, vector)
        report['expected_cases'] = [dict(group=group, name=name, model_command=argv) for group, name, argv in cases]; save()
        # Each reused execution environment passes its own pinned single-core
        # probe before fault cases start. Probes are fresh native processes too.
        for cpu in cpus[:concurrency]:
            launch('probe-cpu'+str(cpu), [str(model), '--runtime-probe'], cpu)
            while active[cpu]['child'].poll() is None:
                guard(); require(time.monotonic()-active[cpu]['started'] < 1800, 'native probe timeout'); time.sleep(0.2)
            finish(cpu)
        pending = iter(cases); exhausted = False
        while active or not exhausted:
            guard()
            for cpu in cpus[:concurrency]:
                if cpu in active:
                    require(time.monotonic()-active[cpu]['started'] < 1800, 'native case timeout')
                    if active[cpu]['child'].poll() is None: continue
                    finish(cpu)
                if not exhausted:
                    case = next(pending, None)
                    if case is None: exhausted = True
                    else:
                        group, name, argv = case; launch(name, argv, cpu, group)
            if active: time.sleep(0.5)
        require(len(report['receipts']) == len(cases)+concurrency and
                {step['name'] for step in report['steps'] if not step['name'].startswith('probe-')} == {name for _, name, _ in cases},
                'every selected case completed exactly once')
        recheck(); guard()
        require(all(sha(out/name) == value for name, value in report['artifacts'].items()), 'durable artifact closure')
        report['status'] = 'passed_selected_aw16_groups_reuse_only'
    except BaseException as error:
        report.update(status='failed_or_incomplete', error=repr(error))
        for cpu, entry in list(active.items()):
            if entry['child'].poll() is None:
                try: os.killpg(entry['child'].pid, signal.SIGKILL)
                except ProcessLookupError: pass
            try: finish(cpu, error)
            except BaseException: pass
        raise
    finally: save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', type=Path); parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output', type=Path); parser.add_argument('--manifest', type=Path); parser.add_argument('--manifest-sha')
    parser.add_argument('--source-review', type=Path); parser.add_argument('--source-review-sha')
    parser.add_argument('--groups', nargs='+'); parser.add_argument('--cpus'); parser.add_argument('--concurrency', type=int, default=2)
    args = parser.parse_args()
    if args.prepare:
        require(not any((args.execute, args.output, args.manifest, args.manifest_sha, args.source_review, args.source_review_sha,
                         args.groups, args.cpus)), 'exclusive preparation mode')
        prepare(args.prepare.resolve())
    else:
        require(args.execute and args.output and args.manifest and args.manifest_sha and args.source_review
                and args.source_review_sha and args.groups and args.cpus, 'explicit reviewed selected-groups execution')
        execute(args.output.resolve(), args.manifest.resolve(), args.manifest_sha, args.source_review.resolve(),
                args.source_review_sha, args.groups, tuple(map(int, args.cpus.split(','))), args.concurrency)


if __name__ == '__main__': main()
