"""Pinned, source-only native component launcher. No preparation or dispatch.

Execute only on an explicit approved Linux host after external manifest review.
No project module is imported. Completion means command evidence, not correctness.
Frozen runners and their exclusive global compile lock are unchanged.
"""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
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

GIB = 1 << 30
MIB = 1 << 20
SELF = 'tools/native_source_gate_aethia_cpu02_v2.py'
COMMON = {
    'verilator': '672a1ccf3468902f66387049f001b04f254bbcece7d5e816e3861715889bf252',
    'verilator_bin': '90fe12f3b2c752b607690cb05a566646398d1e07f38e83f5f7a7f35c20560247',
}
PROFILES = {
    'aethia': dict(base='/home/jtl/gfn-fpga-lab/agent-work', cpus=[0, 2],
        lock='/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock',
        verilator_dir='/home/jtl/gfn-fpga-lab/tools/verilator/usr/bin',
        hashes=dict(COMMON, compiler='e6718f7e0c7d057c3ff77b550c603da9bc4030e3ede3c053705acce1293dbe4d',
                    python='52e0a13e60a981d8c4b6478be2ba5176f69da07948a056bf49cf6f077e30cb41',
                    make='27c9f6d806aee15882b01c2c61848f7aa75caa14bc7b6f608ba422f9e46a7d49',
                    taskset='42acb8e233943873f3bf9eeb1e15bd3281498b5603a5b10d0f9bc37067a12d57')),

}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative(name):
    require(type(name) is str, 'source name type')
    p = PurePosixPath(name)
    require(name not in ('', '.') and str(p) == name and not p.is_absolute()
            and '..' not in p.parts, 'unsafe source name')
    return name


def check_sources(root, pins):
    require(root.is_dir() and root.resolve() == root and type(pins) is dict and pins, 'source root/closure')
    actual = set()
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'source symlink')
        if path.is_file():
            actual.add(str(path.relative_to(root)))
    require(actual == set(pins), 'exact source file closure')
    for name, digest in pins.items():
        relative(name)
        require(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'source hash type')
        path = root / name
        require(path.is_file() and path.stat().st_nlink == 1 and path.suffix not in ('.pyc', '.so', '.pyd')
                and sha(path) == digest, 'source pin/type drift: ' + name)


def load_manifest(path, digest):
    require(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest)
            and path.is_file() and not path.is_symlink() and sha(path) == digest, 'approved manifest SHA')
    manifest = json.loads(path.read_text())
    require(manifest['schema'] == 'native-source-gate-v1' and manifest['status'] == 'prepared_not_executed', 'manifest schema/status')
    require(manifest['host'] in PROFILES and socket.gethostname() == manifest['host'], 'explicit approved native host')
    require(manifest.get('cpu_profile') == 'aethia-physical-0-2-v1', 'explicit CPU0/2 profile required')
    profile = PROFILES[manifest['host']]
    root = Path(manifest['source_root'])
    require(root.is_absolute() and root.name == 'fpga' and root.is_relative_to(profile['base']), 'approved source placement')
    check_sources(root, manifest['sources'])
    require(SELF in manifest['sources'] and Path(__file__).resolve() == root / SELF, 'launcher inside pinned snapshot')
    require(not path.resolve().is_relative_to(root), 'manifest outside source closure')
    parent = Path(manifest['output_parent'])
    require(parent.is_dir() and parent.resolve() == parent and parent.is_relative_to(profile['base'])
            and not parent.is_relative_to(root), 'approved output parent')
    build = manifest['build']
    require(re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', build['top']), 'top identifier')
    require(type(build['sv_sources']) is list and build['sv_sources'] and len(set(build['sv_sources'])) == len(build['sv_sources']), 'ordered unique SV sources')
    for name in build['sv_sources'] + [build['cpp_source']]:
        require(relative(name) in manifest['sources'], 'compiled source outside closure')
    require(type(build['parameters']) is dict and all(re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', k)
            and type(v) is int for k, v in build['parameters'].items()), 'typed HDL parameters')
    require(type(build['cflags']) is list and all(type(x) is str and
            re.fullmatch(r'(-std=c\+\+17|-Werror=return-type|-O[0123s]|-D[A-Za-z_][A-Za-z_0-9]*=-?[0-9]+)', x)
            for x in build['cflags'])
            and '-Werror=return-type' in build['cflags'], 'explicit return-type compile gate')
    names = [step['name'] for step in manifest['steps']]
    require(names and len(names) == len(set(names)) and all(re.fullmatch('[a-z][a-z0-9-]*', n)
            and n not in ('lint', 'build', 'probe', 'verilator-version', 'compiler-version') for n in names), 'unique step names')
    require(manifest['probe']['expected_json'] == dict(context_threads=1, model_threads=1, expected_threads=1)
            and all(type(v) is int for v in manifest['probe']['expected_json'].values()), 'single-thread runtime probe contract')
    for step in [manifest['probe']] + manifest['steps']:
        require(type(step['argv']) is list and step['argv'] and step['argv'][0] == '{exe}'
                and all(type(a) is str for a in step['argv']), 'only built executable may run')
        require(type(step.get('expected_returncode', 0)) is int, 'typed return code')
    return manifest, profile, root


def tools_for(profile):
    directory = Path(profile['verilator_dir'])
    paths = dict(verilator=directory / 'verilator', verilator_bin=directory / 'verilator_bin',
                 compiler=Path('/usr/bin/x86_64-linux-gnu-g++-15'), python=Path('/usr/bin/python3.14'),
                 make=Path('/usr/bin/make'), taskset=Path('/usr/bin/taskset'))
    require(Path(sys.executable).resolve() == paths['python'].resolve(), 'approved Python executable')
    for name, path in paths.items():
        require(path.is_file() and sha(path) == profile['hashes'][name], 'tool hash drift: ' + name)
    require(sha(Path('/usr/bin/g++')) == profile['hashes']['compiler'], 'default compiler alias drift')
    return paths


def execution_limits(cpus):
    group = next(row.split('::', 1)[1] for row in Path('/proc/self/cgroup').read_text().splitlines() if row.startswith('0::'))
    directory = Path('/sys/fs/cgroup') / group.lstrip('/')
    memory = (directory / 'memory.max').read_text().strip()
    quota = (directory / 'cpu.max').read_text().split()
    require((directory / 'memory.swap.max').read_text().strip() == '0', 'requires cgroup no swap')
    require(memory != 'max' and 0 < int(memory) <= 4 * GIB, 'finite aggregate <=4GiB cgroup')
    require(len(quota) == 2 and quota[0] != 'max' and 0 < int(quota[0]) <= 2 * int(quota[1]), 'finite aggregate <=200% CPU')
    actual = sorted(os.sched_getaffinity(0))
    require(actual == cpus, 'effective taskset affinity')
    cores = []
    for cpu in cpus:
        topology = Path('/sys/devices/system/cpu') / f'cpu{cpu}/topology'
        cores.append([int((topology / key).read_text()) for key in ('physical_package_id', 'core_id')])
    require(cpus == [0, 2] and cores == [[0, 0], [0, 1]], 'exact observed CPU0/2 physical topology')
    other_cores = []
    for cpu in (4, 6):
        topology = Path('/sys/devices/system/cpu') / f'cpu{cpu}/topology'
        other_cores.append([int((topology / key).read_text()) for key in ('physical_package_id', 'core_id')])
    require(other_cores == [[0, 2], [0, 3]], 'CPU4/6 topology drift; separate slot required')
    require(not {tuple(row) for row in cores} & {tuple(row) for row in other_cores}, 'CPU0/2 overlaps CPU4/6 physical cores')
    return dict(cgroup=group, memory_max_bytes=int(memory), swap_max_bytes=0, cpu_max=quota, affinity=actual, physical_cores=cores, excluded_cpu46_physical_cores=other_cores)


def clean_env(root, temporary, profile):
    return dict(PATH=profile['verilator_dir'] + ':/usr/bin:/bin', PYTHONPATH=str(root.parent) + ':' + str(root),
                PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', LC_ALL='C', LANG='C',
                TMPDIR=str(temporary), TMP=str(temporary), TEMP=str(temporary), CCACHE_DISABLE='1',
                CXX='/usr/bin/x86_64-linux-gnu-g++-15', CC='/usr/bin/gcc')


def allocated(path):
    total = 0
    for directory, _, names in os.walk(path):
        for name in names:
            try:
                total += (Path(directory) / name).stat().st_blocks * 512
            except FileNotFoundError:
                pass  # Compilers remove temporary files while this guard runs.
    return total


def expand(argv, exe, root):
    result = [a.replace('{exe}', str(exe)).replace('{root}', str(root)) for a in argv]
    require(not any('{' in a or '}' in a for a in result), 'unknown command token')
    return result


def execute(path, digest, out):
    require(__debug__, 'assertions required')
    manifest, profile, root = load_manifest(path, digest)
    require(out.is_absolute() and not out.exists() and out.parent == Path(manifest['output_parent'])
            and out.resolve() == out, 'fresh approved output')
    toolpaths = tools_for(profile)
    limits = execution_limits(profile['cpus'])
    lockpath = Path(profile['lock'])
    require(lockpath.is_file() and lockpath.resolve() == lockpath, 'pre-existing exclusive compiler lock')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (4 * GIB, 4 * GIB))
    out.mkdir()
    scratch = Path(tempfile.mkdtemp(prefix='gfn16-source-gate-', dir='/dev/shm'))
    temporary = scratch / 'tmp'; temporary.mkdir()
    build = scratch / 'build'
    env = clean_env(root, temporary, profile)
    started = time.monotonic()
    report = dict(status='running', scope='native component command evidence, not correctness qualification',
                  host=manifest['host'], source_root=str(root), manifest_sha256=digest, sources=manifest['sources'],
                  tool_sha256={str(p): sha(p) for p in toolpaths.values()}, limits=limits,
                  scratch=str(scratch), compile_lock=str(lockpath), compile_workers=2, model_threads=1,
                  steps=[], artifacts={}, cleanup='All scratch, failures, source and binary evidence retained; no deletion.',
                  bounds=dict(command_seconds=1800, overall_seconds=3600, lock_wait_seconds=1800,
                              memory_bytes=4*GIB, scratch_reserve_bytes=768*MIB, scratch_floor_bytes=2*GIB,
                              durable_reserve_bytes=128*MIB, durable_floor_bytes=10*GIB, host_memory_floor_bytes=4*GIB))

    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

    def remember(file):
        report['artifacts'][str(file.relative_to(out))] = sha(file)

    def guard():
        require(time.monotonic() - started < 3600, 'overall timeout')
        check_sources(root, manifest['sources'])
        require(sha(path) == digest, 'manifest drift')
        require(shutil.disk_usage(scratch).free >= 2*GIB + max(0, 768*MIB-allocated(scratch)), 'scratch reservation/floor')
        require(shutil.disk_usage(out).free >= 10*GIB + max(0, 128*MIB-allocated(out)), 'durable reservation/floor')
        mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024 >= 4*GIB, 'host memory floor')

    def run(name, argv, expected=0):
        guard(); begin = time.monotonic(); failure = None; log = out / (name + '.log')
        error_log = out / (name + '.stderr.log')
        command = [str(toolpaths['taskset']), '-c', ','.join(map(str, profile['cpus'])), *argv]
        with log.open('x') as stream, error_log.open('x') as error_stream:
            child = subprocess.Popen(command, cwd=root, env=env, stdout=stream, stderr=error_stream, start_new_session=True)
            try:
                while child.poll() is None:
                    guard(); require(time.monotonic()-begin < 1800, 'command timeout'); time.sleep(.25)
            except BaseException as exc:
                failure = exc
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        remember(log); remember(error_log)
        report['steps'].append(dict(name=name, command=command, returncode=child.returncode,
                                    seconds=time.monotonic()-begin, error=repr(failure) if failure else None,
                                    log=log.name, sha256=sha(log), stderr_log=error_log.name, stderr_sha256=sha(error_log)))
        save()
        if failure:
            raise failure
        require(child.returncode == expected, 'unexpected return code: ' + name)
        guard()
        return log.read_text()

    def interrupted(number, frame):
        raise RuntimeError('termination signal ' + str(number))

    prior = signal.signal(signal.SIGTERM, interrupted)
    try:
        save(); guard()
        shutil.copyfile(path, out / 'approved-manifest.json'); remember(out / 'approved-manifest.json')
        with tarfile.open(out / 'sources.tar.gz', 'x:gz') as tar:
            for name in sorted(manifest['sources']):
                tar.add(root / name, arcname=name, recursive=False)
        remember(out / 'sources.tar.gz')
        report['verilator_version'] = run('verilator-version', [str(toolpaths['verilator']), '--version']).strip()
        report['compiler_version'] = run('compiler-version', [str(toolpaths['compiler']), '--version']).strip()
        config = manifest['build']
        command = [str(toolpaths['verilator']), '--cc', '--exe', '--build', '-j', '2', '--threads', '1',
                   '--top-module', config['top'], *[f'-G{k}={v}' for k,v in config['parameters'].items()],
                   '-CFLAGS', ' '.join(config['cflags']), '--Mdir', str(build),
                   *[str(root / name) for name in config['sv_sources']], str(root / config['cpp_source'])]
        with lockpath.open('r') as lock:
            deadline = time.monotonic() + 1800
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    guard(); require(time.monotonic() < deadline, 'compile lock timeout'); time.sleep(.25)
            lint = [str(toolpaths['verilator']), '--lint-only', '-Wall', '--threads', '1',
                    '--top-module', config['top'], *[f'-G{k}={v}' for k,v in config['parameters'].items()],
                    '--Mdir', str(build), *[str(root / name) for name in config['sv_sources']]]
            run('lint', lint)
            run('build', command)
        exe = build / ('V' + config['top'])
        require(exe.is_file(), 'built executable')
        report['executable_sha256'] = sha(exe)
        with exe.open('rb') as source, (out / 'model.gz').open('xb') as target:
            with gzip.GzipFile(filename='', mode='wb', fileobj=target, mtime=0) as compressed:
                shutil.copyfileobj(source, compressed)
        remember(out / 'model.gz')
        with gzip.open(out / 'model.gz', 'rb') as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == report['executable_sha256'], 'preserved executable identity')
        generated = {p.name: sha(p) for p in build.iterdir() if p.is_file() and p.suffix in ('.cpp', '.h', '.mk', '.dat')}
        require(generated, 'generated-source inventory')
        report['generated_source_sha256'] = generated
        with tarfile.open(out / 'generated-sources.tar.gz', 'x:gz') as tar:
            for name in sorted(generated):
                tar.add(build / name, arcname=name, recursive=False)
        remember(out / 'generated-sources.tar.gz')
        probe = json.loads(run('probe', expand(manifest['probe']['argv'], exe, root)))
        require(probe == manifest['probe']['expected_json'] and all(type(v) is int for v in probe.values()), 'runtime thread probe')
        report['probe'] = probe
        for step in manifest['steps']:
            require(sha(exe) == report['executable_sha256'], 'executable drift')
            text = run(step['name'], expand(step['argv'], exe, root), step.get('expected_returncode', 0))
            if 'expected_stdout' in step:
                require(text == step['expected_stdout'], 'exact stdout contract: ' + step['name'])
            if 'expected_stderr' in step:
                require((out / (step['name'] + '.stderr.log')).read_text() == step['expected_stderr'],
                        'exact stderr contract: ' + step['name'])
        guard(); tools_for(profile)
        require(all(sha(out/name) == value for name,value in report['artifacts'].items()), 'terminal artifact drift')
        report['status'] = 'completed_native_commands_unreviewed'
    except BaseException as exc:
        report['status'] = 'failed_native_commands'; report['error'] = repr(exc)
        raise
    finally:
        report['seconds'] = time.monotonic()-started; save(); signal.signal(signal.SIGTERM, prior)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.manifest, args.manifest_sha256, args.output), indent=2))


if __name__ == '__main__':
    main()
