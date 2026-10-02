"""Aethia-only two-layer four-point component gate, not a banked NTT."""
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

PINS = {
    'rtl/kernel/genefer_ntt_pair_schedule.sv': '89c17cad846d9db0fa44e768a2f052b193d657fe633f425c77e9441b0512aa81',
    'rtl/kernel/genefer_ntt_banked27_engine.sv': '7ae89e702b671e3fbe8a1f90beb99ea595c832729e5e94232bf82515f1d74fe9',
    'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv': '501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b',
}
FIELDS = [(104857601, 4190109697, 3), (69206017, 4225761281, 5), (67239937, 4227727361, 10)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--compile-lock', type=Path, required=True)
    ap.add_argument('--smoke', action='store_true')
    args = ap.parse_args()
    if platform.node().split('.')[0] != 'aethia':
        raise RuntimeError('RTL simulation restricted to aethia')
    resource.setrlimit(resource.RLIMIT_AS, (6 << 30, 6 << 30))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    root = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    rtl = root / 'rtl/kernel/genefer_ntt_pair4_datapath.sv'
    bench = root / 'rtl/tb/ntt_pair4_datapath.cpp'
    deps = [root / name for name in PINS]
    tracked = [*deps, rtl, bench, Path(__file__).resolve()]
    report = dict(status='running', host=platform.node(), smoke=args.smoke,
                  scope='Two actual frozen butterflies shared by two dependency-ordered four-point layers; no physical RAM banking or full NTT.',
                  fields=[dict(p=p, q=q, generator=g) for p, q, g in FIELDS],
                  radix_bits=32, compile_workers=2, runtime_threads=1,
                  scope_cpu_percent=200, memory_bytes=6 << 30, disk_floor_bytes=10 << 30,
                  sources={str(p.relative_to(root)): sha(p) for p in tracked},
                  builds=[], steps=[], metrics=[], mutations={})

    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    def run(name, command, reject=None):
        before = time.monotonic()
        proc = subprocess.Popen(list(map(str, command)), cwd=root, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        timed_out = False
        try:
            output, _ = proc.communicate(timeout=240)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGKILL)
            output, _ = proc.communicate()
        log = out / (name + '.log')
        log.write_text(output)
        passed = not timed_out and (proc.returncode == 0 if reject is None else proc.returncode == 1 and reject in output)
        report['steps'].append(dict(name=name, command=list(map(str, command)), passed=passed,
                                    returncode=proc.returncode, timed_out=timed_out,
                                    seconds=time.monotonic() - before, log=log.name, sha256=sha(log), reject=reject))
        save()
        print(name, 'PASS' if passed else 'FAIL', output[-450:], flush=True)
        if not passed:
            raise RuntimeError(name + ': ' + output[-2000:])
        return output

    def build(name, aw, field, source=rtl):
        p, q, g = FIELDS[field]
        directory = out / name
        with args.compile_lock.open('a') as lock:
            before = time.monotonic()
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() - before > 600:
                        raise TimeoutError('compile lock wait exceeded 600 seconds')
                    time.sleep(.2)
            waited = time.monotonic() - before
            if shutil.disk_usage(out).free < 10 << 30:
                raise RuntimeError('no build below 10 GiB free')
            run(name, ['verilator', '--cc', '--exe', '--build', '-j', '2',
                       '--top-module', 'genefer_ntt_pair4_datapath', '--Mdir', directory,
                       f'-GGROUP_AW={aw}', f'-GP={p}', f'-GQ={q}', '-CFLAGS',
                       f'-DGROUP_AW={aw} -DFIELD_P={p}u -DFIELD_G={g}u', *deps, source, bench])
        exe = directory / 'Vgenefer_ntt_pair4_datapath'
        report['builds'].append(dict(name=name, group_aw=aw, field=field + 1, p=p, q=q, generator=g,
                                     lock_wait_seconds=waited, source=str(source), source_sha256=sha(source),
                                     executable=str(exe), executable_sha256=sha(exe)))
        save()
        return exe

    def changed(name, text):
        path = out / (name + '.sv')
        path.write_text(text)
        report['mutations'][name] = dict(path=path.name, sha256=sha(path))
        return path

    def replace(text, old, new):
        if text.count(old) != 1:
            raise ValueError('ambiguous mutation anchor: ' + old)
        return text.replace(old, new)

    try:
        for name, digest in PINS.items():
            if sha(root / name) != digest:
                raise RuntimeError('frozen source changed: ' + name)
        report['versions'] = {name: run('version-' + name, command).strip() for name, command in
                              [('verilator', ['verilator', '--version']), ('cxx', ['g++', '--version'])]}
        for field in range(1 if args.smoke else 3):
            for aw in ((4,) if args.smoke else (1, 4, 12)):
                exe = build(f'build-p{field + 1}-aw{aw}', aw, field)
                metric = json.loads(run(f'normal-p{field + 1}-aw{aw}', [exe]))
                if metric['p'] != FIELDS[field][0] or metric['generator'] != FIELDS[field][2] or metric['group_aw'] != aw:
                    raise RuntimeError('bench profile mismatch')
                report['metrics'].append(metric)
        original = rtl.read_text()
        if not args.smoke:
            # These positive fault-injection cases corrupt only a second-layer
            # token's terminal tag. Normal arithmetic/result-valid is intact.
            # The bench observes write_valid BEFORE the sticky error edge.
            anchor = 'for(int k=1;k<6;k=k+1) group_pipe[k]<=group_pipe[k-1];'
            fault_cases = [
                ('group', "group_pipe[5]<=group_pipe[4]^GROUP_AW'(1);", '(group_pipe[5]==commit_group)', "1'b1"),
                ('kind', "kind_pipe[5]<=1'b0;", 'kind_pipe[5] &&', "1'b1 &&"),
                ('valid', "valid_pipe[5]<=1'b0;", 'valid_pipe[5] &&', "1'b1 &&"),
            ]
            for field, (name, injection, old, new) in enumerate(fault_cases):
                text = replace(original, anchor, anchor + '\n            if(active_dif && valid_pipe[4] && kind_pipe[4]) ' + injection)
                path = changed('fault-' + name, text)
                exe = build('build-fault-' + name, 4, field, path)
                report['metrics'].append(json.loads(run('contain-' + name, [exe, 'fault'])))
                path = changed('unguarded-' + name, replace(text, old, new))
                exe = build('build-unguarded-' + name, 4, field, path)
                run('reject-unguarded-' + name, [exe, 'fault'], 'unsafe write on bad commit token')
            mutants = [
                ('write-tag', 'assign write_group=commit_group;', "assign write_group=commit_group+1'b1;", 'write tag mismatch'),
                ('held-map', 'held[1]<=active_dif ? y0[1] : y1[0];', 'held[1]<=active_dif ? y1[0] : y0[1];', 'arithmetic mismatch'),
                ('write-map', 'write_data[32+:32]=active_dif ? y1[0] : y0[1];', 'write_data[32+:32]=active_dif ? y0[1] : y1[0];', 'arithmetic mismatch'),
                ('root-map', 'roots[0]<=root_beat[0+:32];', 'roots[0]<=root_beat[32+:32];', 'arithmetic mismatch'),
                ('input-map', 'v[1]=input_words[3];', 'v[1]=input_words[2];', 'arithmetic mismatch'),
                ('live-mode', 'active_dif<=dif;fault<=0;', 'active_dif<=!dif;fault<=0;', 'arithmetic mismatch'),
                ('early-tag', 'group_pipe[k]<=group_pipe[k-1];', 'group_pipe[k]<=group_pipe[0];', 'fault timing mismatch'),
                ('root-tag', 'root_group_d<=root_group;', "root_group_d<=root_group+1'b1;", 'fault timing mismatch'),
                ('reset-fault', 'active_dif<=0;fault<=0;', 'active_dif<=0;fault<=1;', 'reset leakage'),
            ]
            for index, (name, old, new, diagnostic) in enumerate(mutants):
                path = changed(name, replace(original, old, new))
                exe = build('build-mutant-' + name, 4, index % 3, path)
                run('reject-' + name, [exe], diagnostic)
        for name, digest in report['sources'].items():
            if sha(root / name) != digest:
                raise RuntimeError('source changed during gate: ' + name)
        for entry in report['builds']:
            if sha(Path(entry['executable'])) != entry['executable_sha256']:
                raise RuntimeError('executable changed during gate')
        with tarfile.open(out / 'source-snapshot.tar.gz', 'w:gz') as archive:
            for path in tracked:
                archive.add(path, arcname=str(path.relative_to(root)))
        report.update(status='passed', sources_rechecked=True, source_archive_sha256=sha(out / 'source-snapshot.tar.gz'))
    except BaseException as exc:
        report.update(status='failed', error=repr(exc))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
