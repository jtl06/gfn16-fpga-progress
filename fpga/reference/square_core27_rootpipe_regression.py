"""Whole-core rootpipe integration gate; remote execution is aethia-only.

Fresh builds and whole-integer oracles, not cached correctness. Profiles may be
staged individually; a partial profile is never a full-size qualification.
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
import time

from .square_core27_stream_regression import NAMES as ANCESTOR_NAMES
from .square_core27_stream_regression import write_vectors, independent_profile, check_probe
from .square_core27_recovery import segments
from .square_core27_rootpipe_structure import core_source, host_source, bench_source, ntt_cycles

TOP = 'genefer_square_core27_stream_rootpipe'
ENGINE_SHA = 'cab41579a4b96793f52c31a2864f74aeab3d023f23b50f5c8acce368f07d1967'
PROFILES = (1, 5, 7, 16)
GiB = 1 << 30
COMPILE_LOCK = Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
NAMES = [name.replace('genefer_ntt_banked27_host_engine', 'genefer_ntt_banked27_host_rootpipe_engine')
         for name in ANCESTOR_NAMES[:-1]] + ['genefer_ntt_banked27_rootpipe_engine', TOP]
FIELDS = ('cycles', 'conversion', 'roots', 'ntt', 'crt', 'carry', 'passes',
          'base', 'cache_before', 'root_loads', 'root_hits', 'readback')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_sources(root):
    """Mechanical substitution plus pinned qualified NTT, no helper duplication."""
    kernel = root / 'rtl/kernel'
    for old, new, transform in (
        ('genefer_square_core27_stream', TOP, core_source),
        ('genefer_ntt_banked27_host_engine', 'genefer_ntt_banked27_host_rootpipe_engine', host_source)):
        require(transform((kernel/(old+'.sv')).read_text()) == (kernel/(new+'.sv')).read_text(),
                'unreviewed integration delta: '+new)
    tb = root / 'rtl/tb'
    require(bench_source((tb/'square_core27_stream.cpp').read_text()) ==
            (tb/'square_core27_stream_rootpipe.cpp').read_text(), 'bench delta')
    require(sha(kernel/'genefer_ntt_banked27_rootpipe_engine.sv') == ENGINE_SHA, 'NTT identity')
    sources = [kernel/(name+'.sv') for name in NAMES]
    declarations = []
    for path in sources:
        declarations += re.findall(r'^module\s+(\w+)', path.read_text(), re.M)
    require(len(declarations) == len(set(declarations)), 'duplicate module declarations')
    require('genefer_ntt_difdit_butterfly27' in declarations, 'missing shared butterfly')
    return sources


def validate_output(output, vectors, aw):
    """Exact transaction coverage, integer-oracle readbacks and phase counters."""
    commands = [line.split() for line in vectors.splitlines() if line.startswith(
        ('RUN ', 'RUN_NOREAD ', 'ABORT '))]
    runs = [row for row in commands if row[0] != 'ABORT']
    expected = [row[1] for row in runs]
    require(len(expected) == len(set(expected)), 'duplicate oracle case')
    pattern = re.compile(r'^(\S+) ' + ' '.join(key+r'=(\d+)' for key in FIELDS) + '$')
    rows = []
    for line in output.splitlines():
        if ' cycles=' not in line:
            continue
        match = pattern.fullmatch(line)
        require(match is not None, 'malformed metric')
        row = dict(zip(FIELDS, map(int, match.groups()[1:])), case=match[1], aw=aw, n=1<<aw)
        require(row['cycles'] == sum(row[k] for k in ('conversion','roots','ntt','crt','carry')),
                'phase accounting')
        require(row['ntt'] == ntt_cycles(aw), 'NTT latency differs from reviewed schedule')
        require(row['cache_before'] in (0, 15), 'incomplete cache state')
        warm = row['cache_before'] == 15
        require((row['root_loads'],row['root_hits'],row['roots']) ==
                ((0,4,0) if warm else (4,0,4*((1<<aw)+2))), 'cache contract')
        require(2*(1<<aw)+4 < row['base'] <= 1000000000, 'base domain')
        rows.append(row)
    require([row['case'] for row in rows] == expected, 'transaction coverage/order')
    require([row['readback'] for row in rows] == [int(row[0]=='RUN') for row in runs],
            'readback coverage')
    footer = f'PASS n={1<<aw} squares={len(runs)} readbacks={sum(row[0]=="RUN" for row in runs)} aborts={sum(row[0]=="ABORT" for row in commands)}'
    require(output.splitlines().count(footer) == 1, 'missing/nonunique terminal PASS')
    return rows


def allocated_bytes(root):
    total = 0
    for directory, _, names in os.walk(root):
        for name in names:
            try:
                total += (Path(directory)/name).lstat().st_blocks * 512
            except FileNotFoundError:  # Compiler temporary disappeared during inventory.
                continue
    return total


def execution_limits():
    group = next(line.split('::',1)[1] for line in Path('/proc/self/cgroup').read_text().splitlines()
                 if line.startswith('0::'))
    directory = Path('/sys/fs/cgroup')/group.lstrip('/')
    memory = (directory/'memory.max').read_text().strip()
    cpu = (directory/'cpu.max').read_text().split()
    require(memory != 'max' and int(memory) <= 6*GiB, 'aggregate memory cap missing')
    require(len(cpu)==2 and cpu[0]!='max' and int(cpu[0])<=2*int(cpu[1]), 'aggregate CPU quota missing')
    affinity = sorted(os.sched_getaffinity(0))
    require(len(affinity)==2, 'require two pinned logical CPUs on separate physical cores')
    cores = []
    for processor in affinity:
        topology=Path(f'/sys/devices/system/cpu/cpu{processor}/topology')
        cores.append(tuple(int((topology/name).read_text()) for name in ('physical_package_id','core_id')))
    require(len(set(cores))==2, 'SMT siblings are not separate compile cores')
    return dict(cgroup=group,memory_max_bytes=int(memory),cpu_max=cpu,affinity=affinity,physical_cores=cores)


def source_inputs(root, sources):
    tracked = set(sources + [root/'rtl/tb/square_core27_stream_rootpipe_threaded.cpp',
        root/'rtl/tb/square_core27_stream_rootpipe.cpp',Path(__file__).resolve()])
    tracked |= {Path(m.__file__).resolve() for m in tuple(sys.modules.values())
                if getattr(m, '__file__', None) and Path(m.__file__).resolve().is_relative_to(root/'reference')}
    tracked |= {root/'rtl/kernel/genefer_square_core27_stream.sv',
                root/'rtl/kernel/genefer_ntt_banked27_host_engine.sv', root/'rtl/tb/square_core27_stream.cpp'}
    return {str(path.relative_to(root)): sha(path) for path in sorted(tracked)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--aw', type=int, nargs='+', required=True, choices=PROFILES)
    parser.add_argument('--compile-lock', type=Path, required=True)
    parser.add_argument('--reserve-mib', type=int, required=True)
    parser.add_argument('--other-reserve-mib', type=int, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(__debug__, 'Python optimization disables imported arithmetic assertions')
    require(socket.gethostname() == 'aethia', 'aethia only')
    require(args.execute, 'execution must be explicit')
    require(len(set(args.aw)) == len(args.aw), 'duplicate profiles')
    require(args.reserve_mib >= 256 and args.other_reserve_mib >= 0, 'invalid disk reservations')
    require(args.compile_lock.is_file() and args.compile_lock.resolve() == COMPILE_LOCK,
            'exact existing shared compile lock required')
    limits = execution_limits()
    root = Path(__file__).resolve().parents[1]
    sources = check_sources(root)
    independent_profile(sources[-1])
    wrapper = root/'rtl/tb/square_core27_stream_rootpipe_threaded.cpp'
    pins = source_inputs(root,sources)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(status='running', host=socket.gethostname(), aw=args.aw, ntt_lanes=64,
                  sources=pins, steps=[], metrics=[], vectors={}, builds=[], segments=[], artifacts={}, limits=limits,
                  model_threads=1, compile_workers=2, memory_limit_bytes=6*GiB,
                  command_timeout_seconds=900, reservation_mib=args.reserve_mib,
                  other_reservation_mib=args.other_reserve_mib, disk_floor_bytes=10*GiB,
                  full_profile_coverage=set(args.aw)==set(PROFILES),
                  limitation='Normal whole-core integration only; no board execution or full GFN16 PRP.')
    resource.setrlimit(resource.RLIMIT_AS, (6*GiB, 6*GiB))
    def guard():
        remaining = max(0, args.reserve_mib*(1<<20)-allocated_bytes(out))
        require(shutil.disk_usage(out).free >= 10*GiB+remaining+args.other_reserve_mib*(1<<20),
                'disk floor plus outstanding reservations')
    env = {k:v for k,v in os.environ.items() if k not in (
        'MAKEFLAGS','MFLAGS','CXXFLAGS','CFLAGS','CPPFLAGS','LDFLAGS','CC','CXX','AR',
        'OBJCACHE','OPT_FAST','OPT_SLOW','OPT_GLOBAL') and not k.startswith('NTT_')}
    def run(name, command):
        guard()
        log = out/(name+'.log'); started = time.monotonic(); failure = None
        with log.open('x') as stream:
            process = subprocess.Popen(command, cwd=root, env=env, stdout=stream,
                stderr=subprocess.STDOUT, start_new_session=True)
            try:
                while process.poll() is None:
                    guard()
                    require(time.monotonic()-started < 900, 'command timeout')
                    time.sleep(1)
            except BaseException as error:
                failure = error
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                process.wait()
        report['steps'].append(dict(name=name, command=command, returncode=process.returncode,
            seconds=time.monotonic()-started, log=log.name, sha256=sha(log), error=repr(failure) if failure else None))
        report['artifacts'][str(log.relative_to(out))] = sha(log)
        print(name, process.returncode, flush=True)
        if failure: raise failure
        require(process.returncode == 0, name+' failed')
        guard()
        return log.read_text()
    try:
        guard()
        with tarfile.open(out/'sources.tar.gz', 'x:gz') as archive:
            for name in pins: archive.add(root/name, arcname=name, recursive=False)
        report['source_archive_sha256'] = sha(out/'sources.tar.gz')
        report['artifacts']['sources.tar.gz'] = report['source_archive_sha256']
        report['tool_version'] = run('verilator-version', ['verilator','--version']).strip()
        report['compiler_version'] = run('compiler-version', ['g++','--version']).strip()
        report['python_version'] = sys.version
        report['tool_executable_sha256'] = {str(Path(path).resolve()): sha(Path(path).resolve())
            for path in (sys.executable, shutil.which('g++'), shutil.which('verilator'))}
        for aw in args.aw:
            vector = out/f'vectors-aw{aw}.txt'
            report['vectors'][str(aw)] = write_vectors(vector, aw, 20260929, True)
            vector_sha = report['vectors'][str(aw)]['sha256']
            report['artifacts'][vector.name] = vector_sha
            build = out/f'build-aw{aw}'
            command = ['verilator','--cc','--exe','--build','-j','2','--threads','1',
                '--top-module',TOP,f'-GAW={aw}','-GNTT_LANES=64','--Mdir',str(build),
                *map(str,sources),str(wrapper)]
            # Hold the existing advisory lock only during compiler work.
            with args.compile_lock.open('r') as lock:
                deadline = time.monotonic()+900
                while True:
                    try: fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB); break
                    except BlockingIOError:
                        guard(); require(time.monotonic()<deadline,'compile lock timeout'); time.sleep(1)
                require(all(sha(root/name)==value for name,value in pins.items()), 'source changed before build')
                run(f'build-aw{aw}', command)
            executable = build/('V'+TOP); exe_sha = sha(executable)
            report['builds'].append(dict(aw=aw, executable=str(executable), sha256=exe_sha))
            report['artifacts'][str(executable.relative_to(out))] = exe_sha
            check_probe(run(f'probe-aw{aw}', [str(executable),'--runtime-probe']), 1)
            raw = vector.read_bytes()
            require(hashlib.sha256(raw).hexdigest()==vector_sha, 'generated oracle changed before segmentation')
            if aw==16:
                _, parts, _, _ = segments(raw)
            else: parts = [(1,len(raw.splitlines()),raw)]
            for index,(start,end,payload) in enumerate(parts):
                piece = out/f'aw{aw}-segment{index}.txt'; piece.write_bytes(payload)
                piece_sha = hashlib.sha256(payload).hexdigest()
                report['segments'].append(dict(aw=aw,index=index,start=start,end=end,sha256=piece_sha))
                report['artifacts'][piece.name] = piece_sha
                require(sha(executable)==exe_sha, 'executable changed')
                require(sha(piece)==piece_sha, 'oracle segment changed before test')
                output = run(f'test-aw{aw}-segment{index}', [str(executable),str(piece),'cache'])
                report['metrics'] += validate_output(output, payload.decode(), aw)
                require(sha(executable)==exe_sha, 'executable changed during test')
                require(sha(piece)==piece_sha, 'oracle segment changed during test')
            rows = [row for row in report['metrics'] if row['aw']==aw]
            require(len(rows)==report['vectors'][str(aw)]['squares'], 'total square coverage')
            require(sum(row['readback'] for row in rows)==report['vectors'][str(aw)]['readbacks'], 'total readback coverage')
        require(all(sha(root/name)==value for name,value in pins.items()), 'source changed during gate')
        require(all(sha(out/name)==value for name,value in report['artifacts'].items()),
                'retained evidence changed during gate')
        guard()
        report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', error=repr(error)); raise
    finally:
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__': main()
