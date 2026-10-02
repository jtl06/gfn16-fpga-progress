"""Read-only owner replay of the three retained N1 selector token jobs.

No native rerun, source extraction, HDL tool, field arithmetic or transform.
This is candidate-author replay, not an independent promotion receipt.
"""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import struct
import tarfile

FPGA = Path(__file__).resolve().parents[1]
REPORTS = (
    '1a45284169c68335638c17c4beed1a11bb7962f00486668e87001220d40a0ab2',
    '2e723515f7005814c7927204e367c8a9507c71547cd4a26944e29296407da936',
    'e7e2af5576f9f26f5ee5e870602c9150065eb42319974f664b5b944e55264286',
)
SV = '559e61470a5f5a8d6da1806ca2f733a1c0155c19ef2668193180228be4ca0563'
CPP = '65276b4e1bb0d8f5915339d3eb4f1006827a2f9e2474e8315d6e299ecfceb854'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink(), 'regular retained file')
    return sha(path.read_bytes())


def read(path):
    return json.loads(Path(path).read_text())


def archive(path):
    """In-memory regular members only; never extract or execute."""
    actual, size = {}, 0
    with tarfile.open(path, 'r:gz') as stream:
        for member in stream:
            rel = PurePosixPath(member.name)
            need(member.isfile() and str(rel) == member.name and not rel.is_absolute()
                 and '..' not in rel.parts and member.name not in actual,
                 'unique safe regular archive member')
            size += member.size
            need(size <= 128 << 20, 'bounded replay archive')
            actual[member.name] = stream.extractfile(member).read()
    return actual


def load(name, pin):
    path = FPGA / name
    need(digest(path) == pin, 'pinned pure replay helper')
    spec = importlib.util.spec_from_file_location('_n1_' + Path(name).stem, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def contract(mode, returncode, stdout, stderr, negative=False):
    need(type(mode) is int and mode in range(3), 'typed selector mode')
    need(type(returncode) is int and type(stdout) is bytes and type(stderr) is bytes,
         'typed raw selector outcome')
    expected = (1, b'', b'N1_SELECTOR_MISMATCH\n') if negative else (
        0, f'N1_SELECTOR_PASS mode={mode} cases=8192 responses=8192 aborts=4 faults=1 threads=1\n'.encode(), b'')
    need((returncode, stdout, stderr) == expected, 'exact token contract, not incidental failure')


def replay(mode):
    job = f'n1-selector-mode{mode}-q1-v1'
    done_path = FPGA / 'queue/done' / (job + '.json')
    done = read(done_path)
    attempt = FPGA / 'queue/evidence' / job / 'attempt-0'
    evidence = attempt / 'collected'
    raw = archive(attempt / 'evidence.tar.gz')
    need(digest(attempt / 'evidence.tar.gz') == done['result']['archive_sha256'], 'worker archive pin')
    need(raw == {str(p.relative_to(evidence)): p.read_bytes() for p in evidence.rglob('*') if p.is_file()},
         'complete collected archive')
    inventory = read(evidence / 'dispatcher-inventory.json')['files']
    need(inventory == {k: sha(v) for k, v in raw.items() if k != 'dispatcher-inventory.json'},
         'complete dispatcher inventory')
    n = evidence / 'output/native'
    report = read(n / 'report.json')
    manifest = read(evidence / 'manifest.json')
    ticket = read(evidence / 'ticket.json')
    package = done['package']
    need(digest(n / 'report.json') == REPORTS[mode] == done['result']['queue_report']['report_sha256'],
         'external exact report pin')
    need(report['status'] == 'completed_native_commands_unreviewed', 'completed native commands')
    need(digest(evidence / 'manifest.json') == package['manifest_sha256'] == report['manifest_sha256']
         == ticket['manifest_sha256'], 'manifest closure')
    need(digest(evidence / 'ticket.json') == package['ticket_sha256'], 'ticket pin')
    need(read(evidence / 'queue-report.json') == done['result']['queue_report'], 'queue report closure')
    gate = done['dependency_gate']
    need(gate['status'] == 'PASS_expected_contracts' and digest(gate['path']) == gate['sha256'], 'typed queue gate')
    need(read(gate['path'])['report_sha256'] == REPORTS[mode], 'gate binds report')
    source = archive(n / 'sources.tar.gz')
    generated = archive(n / 'generated-sources.tar.gz')
    need({k: sha(v) for k, v in source.items()} == report['sources'] == manifest['sources'], 'source closure')
    need({k: sha(v) for k, v in generated.items()} == report['generated_source_sha256'], 'generated closure')
    need(report['sources']['rtl/kernel/radix22_selector_probe_v1.sv'] == SV
         and report['sources']['rtl/tb/radix22_selector_probe_v1.cpp'] == CPP, 'unchanged authored HDL/bench')
    need(digest(FPGA / 'rtl/kernel/radix22_selector_probe_v1.sv') == SV
         and digest(FPGA / 'rtl/tb/radix22_selector_probe_v1.cpp') == CPP, 'current author source matches executed snapshot')
    capture = read(evidence / 'capture/capture.json')
    need(capture['source_sha256'] == report['sources'] and capture['manifest_sha256'] == report['manifest_sha256'],
         'capture identity')
    need(digest(evidence / 'capture/source.tar.gz') == capture['archive_sha256'], 'capture archive pin')
    need(archive(evidence / 'capture/source.tar.gz') == {'fpga/' + k: v for k, v in source.items()}, 'capture members')
    need(digest(package['archive']) == package['sha256'], 'selected package pin')
    packaged = archive(package['archive'])
    need(len(packaged) == len(source) + 5 and all(packaged['capture/source/fpga/' + k] == v for k, v in source.items()),
         'selected package complete source')
    for name in ('manifest.json', 'ticket.json', 'capture/capture.json', 'capture/source.tar.gz', 'capture/approved-manifest.json'):
        need(packaged[name] == (evidence / name).read_bytes(), 'selected package input identity')
    stage = read(evidence / 'stage-receipt.json')
    need(stage['archive_sha256'] == package['sha256'] and stage['ticket_sha256'] == package['ticket_sha256'], 'stage pin')
    need(stage['inputs'] == {k: sha(v) for k, v in packaged.items()}, 'stage all input hashes')
    for name, pin in report['artifacts'].items():
        need(digest(n / name) == pin, 'native artifact hash')
    elf = gzip.decompress((n / 'model.gz').read_bytes())
    need(sha(elf) == report['executable_sha256'] and elf[:6] == b'\x7fELF\x02\x01'
         and struct.unpack('<H', elf[18:20])[0] == 62, 'Linux x86_64 ELF; never execute')
    observed = json.loads(source['results/throughput-20260929/azure-sim-resize-r49-v1/toolchain-observation-v1.json'])
    identity = load('tools/build_identity_v1.py', report['sources']['tools/build_identity_v1.py'])
    profile = dict(hashes=observed['hashes'], verilator_dir=str(Path(observed['paths']['verilator']).parent))
    need(identity.build_identity(manifest, profile)['build_key'] == ticket['build_key'], 'build key replay')
    run = dict(build_key=ticket['build_key'], steps=manifest['steps'], probe=manifest['probe'], phase='run', id=ticket['id'])
    need(sha(json.dumps(run, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()) == ticket['run_key'], 'run key replay')
    paths = observed['paths']
    need(report['tool_sha256'] == {paths[k]: observed['hashes'][k] for k in ('verilator', 'verilator_bin', 'compiler', 'python', 'make', 'taskset')},
         'actual observed tool fingerprints')
    cpus = [2 * mode, 2 * mode + 1]
    affinity = ','.join(map(str, cpus))
    limits = report['limits']
    need(limits['affinity'] == cpus and limits['physical_cores'] == [[0, c] for c in cpus]
         and limits['full_topology'] == observed['topology'] and limits['memory_max_bytes'] == 8 << 30
         and limits['swap_max_bytes'] == 0 and list(map(int, limits['cpu_max'])) == [200000, 100000], 'actual physical caps')
    props = done['result']['properties']
    need(props == done['dispatch']['properties'] and props['InvocationID'] == done['dispatch']['invocation'], 'actual invocation')
    need((props['MainPID'], props['SubState'], props['Result'], props['ExecMainStatus'], props['ControlGroup'])
         == ('0', 'exited', 'success', '0', ''), 'terminal no live process')
    need((props['MemoryMax'], props['MemorySwapMax'], props['CPUQuotaPerSecUSec'], props['TimeoutStopUSec'], props['RuntimeMaxUSec'], props['AllowedCPUs'])
         == (str(8 << 30), '0', '2s', '15s', '1h 1min 40s', f'{cpus[0]}-{cpus[1]}'), 'outer finite caps')
    for log in ('stage_log', 'launch_log', 'terminal_journal'):
        record = done['dispatch'][log]
        need(record['returncode'] == 0, 'dispatcher finite command success')
        for stream in ('stdout', 'stderr'):
            need(digest(record[stream]) == record[stream + '_sha256'], 'dispatcher raw evidence pin')
    launch = done['dispatch']['launch_log']['argv'][-1]
    need('--property=KillMode=control-group' in launch and '--property=MemorySwapMax=0' in launch
         and '--property=RuntimeMaxSec=3700' in launch and '--property=TimeoutStopSec=15' in launch
         and '/usr/bin/env -i ' in launch and package['runner'] + ' run --ticket ' in launch,
         'outer kill-group and source-pinned executor envelope')
    budget = done['dispatch']['budget_check']
    need(budget['admitted'] and budget['status'] == 'PASS_budget_only_no_job_reservation'
         and budget['rolling24h_spend_upper_usd'] + budget['future_full_hosts_bound_usd'] < budget['rolling24h_cap_usd'], 'retained host budget admission')
    build = manifest['build']
    need(build == dict(top='radix22_selector_probe_v1', sv_sources=['rtl/kernel/radix22_selector_probe_v1.sv'], cpp_source='rtl/tb/radix22_selector_probe_v1.cpp',
                       parameters={'MODE': mode}, cflags=['-std=c++17', '-Werror=return-type', f'-DN1_SELECTOR_MODE={mode}'], runtime_threads=1), 'exact MODE build')
    steps = report['steps']
    need([x['name'] for x in steps] == ['verilator-version', 'compiler-version', 'lint', 'build', 'probe', 'selector-control', 'selector-negative']
         and [x['returncode'] for x in steps] == [0, 0, 0, 0, 0, 0, 1], 'complete ordered finite commands')
    root, mdir = report['source_root'], report['scratch'] + '/build'
    exe = mdir + '/Vradix22_selector_probe_v1'
    common = ['--threads', '1', '--top-module', build['top'], f'-GMODE={mode}']
    sv = [root + '/' + build['sv_sources'][0]]
    expected = [[paths['verilator'], '--version'], [paths['compiler'], '--version'],
                [paths['verilator'], '--lint-only', '-Wall', '-Wno-fatal'] + common + ['--Mdir', mdir] + sv,
                [paths['verilator'], '--cc', '--exe', '--build', '-Wall', '-Wno-fatal', '-j', '2'] + common + ['-CFLAGS', ' '.join(build['cflags']), '--Mdir', mdir] + sv + [root + '/' + build['cpp_source']],
                [exe, '--runtime-probe'], [exe], [exe, '--negative-selector']]
    for step, command in zip(steps, expected):
        need(step['command'] == ['/usr/bin/taskset', '-c', affinity] + command and step['error'] is None and step['seconds'] < 1800, 'exact ordered argv and bound')
        need(digest(n / step['log']) == step['sha256'] and digest(n / step['stderr_log']) == step['stderr_sha256'], 'exact step logs')
    need(read(n / 'probe.log') == report['probe'] == manifest['probe']['expected_json'] == dict(context_threads=1, model_threads=1, expected_threads=1), 'actual thread probe')
    for step, negative in zip(steps[5:], (False, True)):
        contract(mode, step['returncode'], (n / step['log']).read_bytes(), (n / step['stderr_log']).read_bytes(), negative)
    classifier = load('tools/native_lint_classes_v1.py', report['sources']['tools/native_lint_classes_v1.py'])
    for step in steps[2:4]:
        got = classifier.classify(step['returncode'], (n / step['log']).read_bytes(), (n / step['stderr_log']).read_bytes(), manifest, FPGA)
        got['source_root'] = root
        need(got == report[step['name'] + '_admission'], 'class policy raw-log replay; not clean lint')
    quota = report['scratch_quota_admission']
    q = quota['quota']
    need(q['quota_state'] == 'positively_verified_disabled_on_ext4' and q['raw'] == dict(q_getquota_errno=3, q_getfmt_errno=3)
         and q['global_available_bytes'] >= quota['floor_bytes'] + quota['outstanding_reservation_bytes']
         and q['global_available_inodes'] >= quota['floor_inodes'] + quota['outstanding_reservation_inodes'], 'retained actual own-user quota/headroom')
    need(report['compile_workers'] == 2 and report['model_threads'] == 1 and report['seconds'] < 3600, 'serial model finite bounds')
    return dict(mode=mode, status='PASS_owner_token_native_replay_NOT_independent', done_sha256=digest(done_path), report_sha256=REPORTS[mode],
                manifest_sha256=report['manifest_sha256'], package_sha256=package['sha256'], gate_sha256=gate['sha256'],
                invocation=props['InvocationID'], start=props['ExecMainStartTimestamp'], end=props['ExecMainExitTimestamp'],
                worker_seconds=report['seconds'], peak_manager_bytes=int(props['MemoryPeak']),
                cumulative_children_peak_rss_kib=max(x['cumulative_children_peak_rss_kib'] for x in steps),
                ELF_sha256=report['executable_sha256'], native_artifacts=len(report['artifacts']), sources=len(source),
                generated_sources=len(generated), dispatcher_pins=len(inventory), package_members=len(packaged),
                ordered_commands=len(steps), lint_style_classes=report['lint_admission']['class_counts'],
                packets=8192, responses=8192, cancellation_resets=4, illegal_pattern_faults=1,
                tokens_not_field_arithmetic=True, root_ROM_address_supply_excluded=True, physical_or_architecture_GO=False)


def main():
    return dict(schema='n1-selector-owner-native-replay-v1', status='PASS_scoped_three_MODE_token_native_owner_replay',
                independent=False, native_rerun=False, full_N_numeric_local=False,
                records=[replay(mode) for mode in range(3)])


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
