"""Bounded, opt-in one-versus-eight Verilator runtime experiment on aethia.

Build and timing are separate invocations so the parent can reserve CPU time.
The frozen bench is included unchanged by one common context-setting wrapper.
Every invocation executes the oracle; no correctness result is cached.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import socket
import subprocess
import time

TOP = 'genefer_square_core27'
NAMES = [
    'genefer_montgomery_mul32_pipe', 'genefer_montgomery_mul27_sparse_pipe',
    'genefer_digit_reduce27_pipe', 'genefer_sdp_ram32',
    'genefer_ntt_banked27_engine', 'genefer_ntt_banked27_host_engine',
    'genefer_mod64_pipe', 'genefer_crt3_27_pipe', 'genefer_carry_transfer_tree',
    'genefer_sp_ram', 'genefer_div_recip_narrow',
    'genefer_carry_prefix_vector_pipe_v2', TOP,
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temporary, path)


def verify(inputs):
    for path, expected in inputs.items():
        if sha(path) != expected:
            raise ValueError('input identity changed: ' + path)


def run(out, label, command, timeout=600):
    """Fresh logs, bounded own process group, independent user/system CPU time."""
    stdout_path, stderr_path = out / (label + '.stdout'), out / (label + '.stderr')
    usage_path = out / (label + '.resources')
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    timed_out = False
    with stdout_path.open('x') as stdout, stderr_path.open('x') as stderr:
        process = subprocess.Popen(['/usr/bin/time', '-v', '-o', str(usage_path), *command],
                                   stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = dict(label=label, command=command, returncode=process.returncode,
                  timed_out=timed_out, seconds=time.monotonic() - started,
                  user_seconds=after.ru_utime - before.ru_utime,
                  system_seconds=after.ru_stime - before.ru_stime,
                  stdout=str(stdout_path), stderr=str(stderr_path),
                  stdout_sha256=sha(stdout_path), stderr_sha256=sha(stderr_path))
    result['resource_log'] = str(usage_path)
    for line in usage_path.read_text().splitlines():
        if 'Maximum resident set size (kbytes):' in line:
            result['peak_rss_kib'] = int(line.rsplit(':', 1)[1])
    print(label, result['returncode'], round(result['seconds'], 3), flush=True)
    return result


def cpu_context():
    """Record every visible ancestor quota, rejecting less than eight CPUs."""
    entry = next(line for line in Path('/proc/self/cgroup').read_text().splitlines()
                 if line.startswith('0::'))
    directory = Path('/sys/fs/cgroup') / entry.split('::', 1)[1].lstrip('/')
    quotas = {}
    while directory != Path('/sys/fs'):
        path = directory / 'cpu.max'
        if path.exists():
            value = path.read_text().strip()
            quotas[str(path)] = value
            quota, period = value.split()
            if quota != 'max' and int(quota) < 8 * int(period):
                raise RuntimeError('runtime benchmark needs at least 800% CPU quota: ' + str(path))
        directory = directory.parent
    if not quotas:
        raise RuntimeError('cannot establish CPU quota')
    affinity = sorted(os.sched_getaffinity(0))
    if len(affinity) < 8:
        raise RuntimeError('runtime benchmark needs at least eight eligible CPUs')
    return dict(cgroup=entry, quotas=quotas, affinity=affinity,
                load_average=list(os.getloadavg()))


def build(args, root, out):
    gate_path = args.gate.resolve()
    gate = json.loads(gate_path.read_text())
    if gate.get('status') != 'passed' or gate.get('radix_bits') != 32:
        raise ValueError('a completed atomic27 gate is required')
    if [64, 16] not in gate['profiles']:
        raise ValueError('missing 64/16 correctness profile')
    inputs = {str((root / name).resolve()): value for name, value in gate['sources'].items()}
    inputs[str(gate_path)] = sha(gate_path)
    inputs[str(Path(__file__).resolve())] = sha(__file__)
    verify(inputs)
    vectors = {5: args.aw5_vectors.resolve(), 16: args.full_vectors.resolve()}
    if sha(vectors[5]) != gate['vectors']['5']['sha256']:
        raise ValueError('AW5 vector differs from the completed gate')
    segments = gate.get('recovery', {}).get('segments', [])
    if not any(sha(vectors[16]) == item['sha256'] for item in segments):
        raise ValueError('full-N fixture must be an exact completed resetting segment')
    if not any(line.startswith('LOAD ') for line in vectors[16].read_text().splitlines()):
        raise ValueError('full-N fixture lacks its reset transaction')
    out.mkdir(parents=True, exist_ok=False)
    bench = root / 'rtl/tb/square_core27.cpp'
    wrapper = out / 'frozen_context_wrapper.cpp'
    wrapper.write_text('#define main frozen_core27_main\n#include ' + json.dumps(str(bench)) +
                       '\n#undef main\nint main(int argc,char** argv) {\n'
                       '    static_assert(BENCH_THREADS==1 || BENCH_THREADS==8,"thread count");\n'
                       '    Verilated::threadContextp()->threads(BENCH_THREADS);\n'
                       '    int result=frozen_core27_main(argc,argv);\n'
                       '    if(Verilated::threadContextp()->threads()!=BENCH_THREADS) return 97;\n'
                       '    return result;\n}\n')
    inputs[str(wrapper)] = sha(wrapper)
    fixtures = {}
    for aw, original in vectors.items():
        target = out / f'vectors-aw{aw}.txt'
        shutil.copy2(original, target)
        inputs[str(target)] = sha(original)
        fixtures[str(aw)] = str(target)
    tools = {}
    for name in ('verilator', 'g++', 'make'):
        path = Path(shutil.which(name)).resolve()
        tools[name] = dict(path=str(path), sha256=sha(path),
                           version=subprocess.check_output([name, '--version'], text=True).splitlines()[0])
        inputs[str(path)] = sha(path)
    verilator_bin = Path(tools['verilator']['path']).with_name('verilator_bin')
    inputs[str(verilator_bin)] = sha(verilator_bin)
    inputs['/usr/bin/time'] = sha('/usr/bin/time')
    tools['verilator']['configuration'] = subprocess.check_output(['verilator', '-V'], text=True)
    runtime = Path(os.environ['VERILATOR_ROOT']).resolve()
    for path in sorted((runtime / 'include').rglob('*')):
        if path.is_file():
            inputs[str(path)] = sha(path)
    report = dict(status='building', host=socket.gethostname(), gate=str(gate_path),
                  inputs=inputs, tools=tools, fixtures=fixtures, builds=[], runs=[],
                  build_workers=2, memory_limit_bytes=6 << 30, command_timeout_seconds=600,
                  lanes=[64, 16], wrapper_sha256=sha(wrapper),
                  note='Runtime model/context threads change together; -j2 compiler workers and frozen oracle do not.')
    try:
        sources = [str(root / 'rtl/kernel' / (name + '.sv')) for name in NAMES]
        for aw in (5, 16):
            for threads in (1, 8):
                verify(inputs)
                directory = out / f'build-aw{aw}-threads{threads}'
                command = ['verilator', '--cc', '--exe', '--build', '-j', '2',
                           '--threads', str(threads), '--top-module', TOP, '--Mdir', str(directory),
                           f'-GAW={aw}', '-GNTT_LANES=64', '-CFLAGS', f'-DBENCH_THREADS={threads}',
                           *sources, str(wrapper)]
                result = run(out, directory.name, command)
                result.update(aw=aw, threads=threads)
                report['builds'].append(result)
                if result['returncode'] or result['timed_out']:
                    raise RuntimeError('bounded build failed: ' + directory.name)
                executable = directory / ('V' + TOP)
                result.update(executable=str(executable), executable_sha256=sha(executable))
                verify(inputs)
                save(out / 'report.json', report)
        report['status'] = 'built-awaiting-coordinated-timing'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        save(out / 'report.json', report)


def timing(args, out):
    report = json.loads((out / 'report.json').read_text())
    if report['status'] != 'built-awaiting-coordinated-timing':
        raise ValueError('benchmark is not a fresh completed build')
    context = cpu_context()
    cpus = [int(value) for value in args.cpus.split(',')]
    if len(cpus) != 8 or len(set(cpus)) != 8 or not set(cpus) <= set(context['affinity']):
        raise ValueError('specify eight distinct eligible CPUs coordinated with parent')
    os.sched_setaffinity(0, cpus)
    report.update(status='timing', cpu_context=context, timed_affinity=cpus)
    builds = {(item['aw'], item['threads']): item for item in report['builds']}
    try:
        timed_out_profiles = set()
        # AW5 repeats test fresh-process/reset determinism; full-N is mandatory
        # regardless of whether small-N synchronization overhead looks poor.
        for aw, order in ((5, (1, 8, 8, 1)), (16, (1, 8))):
            outputs = []
            for index, threads in enumerate(order):
                if (aw, threads) in timed_out_profiles:
                    report.setdefault('skipped_repeats', []).append(dict(
                        aw=aw, threads=threads, repeat=index,
                        reason='identical profile already exceeded unchanged runtime cap'))
                    continue
                verify(report['inputs'])
                item = builds[aw, threads]
                if sha(item['executable']) != item['executable_sha256']:
                    raise ValueError('executable changed after build')
                result = run(out, f'run-aw{aw}-threads{threads}-r{index}',
                             [item['executable'], report['fixtures'][str(aw)], 'cache'])
                result.update(aw=aw, threads=threads, repeat=index,
                              executable_sha256=item['executable_sha256'])
                report['runs'].append(result)
                if result['timed_out']:
                    timed_out_profiles.add((aw, threads))
                    save(out / 'report.json', report)
                    continue
                if result['returncode']:
                    raise RuntimeError('bounded runtime failed: ' + result['label'])
                payload = Path(result['stdout']).read_bytes()
                if b'PASS n=' not in payload:
                    raise RuntimeError('oracle completion absent')
                outputs.append(payload)
                if payload != outputs[0]:
                    raise RuntimeError('thread-count or repeat output/counter nondeterminism')
                if sha(item['executable']) != item['executable_sha256']:
                    raise ValueError('executable changed during run')
                verify(report['inputs'])
                save(out / 'report.json', report)
        if timed_out_profiles:
            report.update(status='incomplete-runtime-cap',
                          timed_out_profiles=[list(item) for item in sorted(timed_out_profiles)])
        else:
            report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        save(out / 'report.json', report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['build', 'timing'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--gate', type=Path)
    parser.add_argument('--aw5-vectors', type=Path)
    parser.add_argument('--full-vectors', type=Path)
    parser.add_argument('--cpus', help='eight comma-separated CPUs, after parent coordination')
    args = parser.parse_args()
    if socket.gethostname() != 'aethia':
        raise RuntimeError('aethia only')
    resource.setrlimit(resource.RLIMIT_AS, (6 << 30, 6 << 30))
    root = Path(__file__).resolve().parents[1]
    if args.phase == 'build':
        if not all((args.gate, args.aw5_vectors, args.full_vectors)):
            parser.error('build requires gate and both frozen vector paths')
        build(args, root, args.output.resolve())
    else:
        if not args.cpus:
            parser.error('timing requires parent-coordinated --cpus')
        timing(args, args.output.resolve())


if __name__ == '__main__':
    main()
