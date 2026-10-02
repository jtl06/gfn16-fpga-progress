"""Tiny aethia-only scheduler gate; reserves data27 space, never builds NTT RTL."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import signal
import subprocess
import tarfile
import time

from .ntt_pair_root_metadata import schedule_source, SCHEDULE_SHA

TOP = 'genefer_ntt_pair_schedule_metadata'
BENCH_SHA = 'c3c9668400b19135a398cfe0786d14036aa14c0b095ee6506db16abb0e7e0a84'
CANDIDATE_SHA = 'a392c1eb052164e9e950256d0feebda347f97990dfdb781c7913b79938c0a816'
CANDIDATE_BENCH_SHA = 'abef9667db236bde32ec64f410ada4406abbe55d722e2f234e184b87a4080aa0'
DISK_FLOOR = (10 << 30) + (900 << 20)
ARTIFACT_CAP = 32 << 20
TRANSIENT_RESERVE = 32 << 20
LOCK = Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if not __debug__:
        raise RuntimeError('optimized Python disables required structural assertions')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compile-lock', type=Path, required=True)
    args = parser.parse_args()
    if platform.node().split('.')[0] != 'aethia':
        raise RuntimeError('scheduler RTL simulation is restricted to aethia')
    if args.compile_lock.resolve() != LOCK:
        raise RuntimeError('shared compiler lock is required')
    root = Path(__file__).resolve().parents[1]
    if root != Path('/home/jtl/gfn-fpga-lab/agent-work/ntt-pair-schedule/fpga'):
        raise RuntimeError('scheduler gate requires its isolated existing workspace')
    out = args.output.resolve()
    if not out.is_relative_to(root / 'artifacts'):
        raise RuntimeError('evidence must remain in the isolated artifact tree')
    resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 << 20, 8 << 20))
    if shutil.disk_usage(root).free < DISK_FLOOR + ARTIFACT_CAP + TRANSIENT_RESERVE:
        raise RuntimeError('refuse gate: insufficient data27 plus scheduler disk reserve')
    out.mkdir(parents=True, exist_ok=False)
    rtl = root / 'rtl/kernel' / (TOP + '.sv')
    bench = root / 'rtl/tb/ntt_pair_schedule_metadata.cpp'
    ancestor = root / 'rtl/kernel/genefer_ntt_pair_schedule.sv'
    ancestor_bench = root / 'rtl/tb/ntt_pair_schedule.cpp'
    files = [rtl, bench, ancestor, ancestor_bench, Path(__file__).resolve(),
             root / 'reference/ntt_pair_root_metadata.py', root / 'reference/__init__.py']
    hashes = {str(p.relative_to(root)): sha(p) for p in files}
    report = dict(status='running', host=platform.node(), sources=hashes, steps=[], builds=[],
        scope='Standalone event/tag scheduler only; no NTT arithmetic, memory, integration or physical qualification.',
        compile_workers=2, compiled_runtime_threads=1, memory_limit_bytes=2 << 30,
        disk_floor_bytes=DISK_FLOOR, data27_reserved_bytes=900 << 20,
        artifact_cap_bytes=ARTIFACT_CAP, transient_reserve_bytes=TRANSIENT_RESERVE,
        disk_observations=[])

    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    def structural():
        assert sha(ancestor) == SCHEDULE_SHA
        assert sha(ancestor_bench) == BENCH_SHA
        assert sha(rtl) == CANDIDATE_SHA and sha(bench) == CANDIDATE_BENCH_SHA
        assert rtl.read_text() == schedule_source(ancestor.read_text())
        assert bench.read_text() == ancestor_bench.read_text().replace(
            'Vgenefer_ntt_pair_schedule', 'Vgenefer_ntt_pair_schedule_metadata')

    def disk_guard(stage):
        used = sum(p.stat().st_blocks * 512 for p in out.rglob('*') if p.is_file())
        free = shutil.disk_usage(out).free
        report['disk_observations'].append(dict(stage=stage, free_bytes=free, artifact_bytes=used))
        save()
        if used > ARTIFACT_CAP:
            raise RuntimeError('scheduler artifact cap exceeded; no further builds permitted')
        if free < DISK_FLOOR + ARTIFACT_CAP + TRANSIENT_RESERVE:
            raise RuntimeError('refuse next command: data27 plus scheduler disk reserve exhausted')

    def run(name, command, diagnostic=None):
        disk_guard('before-' + name)
        begin = time.monotonic()
        process = subprocess.Popen(list(map(str, command)), cwd=root, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, start_new_session=True)
        timed_out = False
        try:
            output, _ = process.communicate(timeout=180)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            output, _ = process.communicate()
        log = out / (name + '.log')
        log.write_text(output)
        passed = not timed_out and (process.returncode == 0 if diagnostic is None else
                                   process.returncode == 1 and diagnostic in output)
        report['steps'].append(dict(name=name, command=list(map(str, command)),
            returncode=process.returncode, passed=passed, timed_out=timed_out,
            seconds=time.monotonic()-begin, log=log.name, log_sha256=sha(log), diagnostic=diagnostic))
        save()
        print(name, 'PASS' if passed else 'FAIL', output[-500:], flush=True)
        if not passed:
            raise RuntimeError(name + ': ' + output[-2500:])
        disk_guard('after-' + name)

    def build(name, source, width):
        with LOCK.open('a') as lock:
            begin = time.monotonic()
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic()-begin > 600:
                        raise TimeoutError('shared compile-lock wait exceeded600seconds')
                    time.sleep(.2)
            wait = time.monotonic()-begin
            directory = out / name
            run(name, ['verilator', '--cc', '--exe', '--build', '-j', '2', '--threads', '1',
                '--top-module', TOP, '--Mdir', directory, f'-GGROUP_AW={width}',
                '-CFLAGS', f'-DGROUP_AW={width}', source, bench])
        exe = directory / ('V' + TOP)
        report['builds'].append(dict(name=name, group_aw=width, source_sha256=sha(source),
            executable=str(exe), executable_sha256=sha(exe), lock_wait_seconds=wait))
        save()
        return exe

    try:
        with tarfile.open(out / 'source-snapshot.tar.gz', 'w:gz') as archive:
            for path in files:
                archive.add(path, arcname=str(path.relative_to(root)))
        report['source_archive_sha256'] = sha(out / 'source-snapshot.tar.gz')
        structural()
        report['exact_source_delta_verified'] = True
        for name, command in [('verilator', ['verilator', '--version']),
                              ('cxx', ['g++', '--version']), ('python', ['python3', '--version'])]:
            run('version-' + name, command)
        report['tool_sha256'] = {name: sha(Path(shutil.which(name)))
            for name in ('verilator', 'verilator_bin', 'g++', 'python3') if shutil.which(name)}
        for width in (1, 4, 16):
            exe = build(f'build-aw{width}', rtl, width)
            run(f'normal-aw{width}', [exe])
        mutants = [
            ('root-A-tag', "GROUP_AW'(tick>>1)", "GROUP_AW'((tick>>1)+TW'(1))", 'root tag mismatch'),
            ('root-B-offset', "root_group=tick[0] ? GROUP_AW'((tick-TW'(7))>>1)", "root_group=tick[0] ? GROUP_AW'((tick-TW'(5))>>1)", 'root tag mismatch'),
            ('root-kind', 'root_second=tick[0];', 'root_second=!tick[0];', 'root tag mismatch'),
            ('root-event-valid', 'root_read=read_a || read_b;', 'root_read=busy;', 'event mismatch'),
            ('hold-phase', 'hold_first=read_b;', 'hold_first=read_a;', 'event mismatch'),
            ('early-commit', "tick>=TW'(14)", "tick>=TW'(12)", 'event mismatch'),
            ('early-done', "tick==twice_groups+TW'(12)", "tick==twice_groups+TW'(10)", 'active contract'),
            ('reset-busy', 'busy<=0;done<=0;error<=0;', 'busy<=1;done<=0;error<=0;', 'reset leaked events'),
            ('inflight-start', 'if(!busy) begin', 'if(!busy || start) begin', 'active contract'),
        ]
        original = rtl.read_text()
        for name, old, new, diagnostic in mutants:
            if original.count(old) != 1:
                raise ValueError('ambiguous metadata mutation: ' + name)
            path = out / ('mutant-' + name + '.sv')
            path.write_text(original.replace(old, new))
            exe = build('build-' + name, path, 4)
            run('reject-' + name, [exe], diagnostic)
        structural()
        if hashes != {str(p.relative_to(root)): sha(p) for p in files}:
            raise RuntimeError('source closure changed during gate')
        for model in report['builds']:
            if sha(Path(model['executable'])) != model['executable_sha256']:
                raise RuntimeError('built executable changed during gate: ' + model['name'])
        report.update(status='passed', sources_rechecked=True,
                      executables_rechecked=True, negative_mutants=len(mutants))
    except BaseException as exc:
        report.update(status='failed', error=repr(exc))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
