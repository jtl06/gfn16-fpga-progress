"""Static serial native lanes: exact shared-v1 execution, durable quota guard.

One model thread, two compiler workers, and the original exclusive compile
lock are retained. No dynamic resource pool, observer or compile-slot upgrade.
Scratch reservations are conservative estimates, not filesystem hard quotas.
"""
import argparse
from contextlib import ExitStack
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import socket
import sys
import types

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SELF = 'tools/native_static_v1.py'
GIB = 1 << 30
PINS = {
    'tools/native_shared_v1.py': '7bae7c05f7a3a5a83c55f9eb4f9dc33476b3051841661da8a45627d20424e10b',
    'tools/native_source_gate_aethia_cpu02_v2.py': '452f9bfdebc535d39c1e493b61378de50720088788698435fd6d11974eb670b3',
    'tools/native_user_quota_v1.py': 'a55c3192c85b272dad59acc5d4b782b69f78e927e2f559106534b27ba6aab3c3',
    'tools/native_user_quota_v2.py': '1a628027f1f083866cd3ddb7246c2da27523623d05a5fd107b43271bdefccfe3',
    'cloud/gcp-native-thread-profiles-v1.json': 'c91d5c5519c9ef5c14aa1d1c014f2f4f0152170f77404cfd63dbabf4b5035fa5',
    'cloud/aethia-native-thread-profiles-v2.json': '837b27f292704ce8f46d03d37bed9b520aedc02da33a9b389b12588a71c5c916',
}
SELECTIONS = {
    'gcp-c4d-static01-v1': ('cloud/gcp-native-thread-profiles-v1.json', 'gcp-c4d-sim01-v2', 2),
    'gcp-c4d-static23-v1': ('cloud/gcp-native-thread-profiles-v1.json', 'gcp-c4d-sim23-v2', 2),
    'aethia-static02-v1': ('cloud/aethia-native-thread-profiles-v2.json', 'aethia-sim02-v2', 3),
    'aethia-static46-v1': ('cloud/aethia-native-thread-profiles-v2.json', 'aethia-sim46-v2', 3),
    'aethia-static810-v1': ('cloud/aethia-native-thread-profiles-v2.json', 'aethia-sim810-v2', 3),
}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pinned(relative):
    path = HERE.parent / relative
    need(path.is_file() and not path.is_symlink() and sha(path) == PINS[relative], 'static dependency pin: ' + relative)
    return path


def load(relative):
    path = pinned(relative)
    spec = importlib.util.spec_from_file_location('_native_static_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def profile(profile_id):
    need(profile_id in SELECTIONS, 'approved static pair profile')
    filename, selected, lanes = SELECTIONS[profile_id]
    data = json.loads(pinned(filename).read_text())
    need(data['schema'] == 'gfn16-native-thread-host-v1', 'static host data schema')
    value = copy.deepcopy(data)
    value.update(value.pop('profiles')[selected])
    need(len(value['cpus']) == 2 and value['cpu_quota_percent'] == 200, 'two physical compiler cores')
    cores = [value['topology'][str(cpu)] for cpu in value['cpus']]
    need(len(set(map(tuple, cores))) == 2, 'static pair excludes SMT siblings')
    need(value['scratch_reservation_bytes'] == 4 * GIB and value['scratch_floor_bytes'] == 10 * GIB,
         'durable four-GiB estimate and ten-GiB floor')
    value.update(profile_id=profile_id, static_lanes=lanes, model_threads=1, compile_workers=2,
                 profile_source=filename, profile_sha256=PINS[filename])
    interop = Path(value['interop'])
    value['pair_lock'] = str(Path(value['base']) / ('.static-pair-' + '-'.join(map(str, value['cpus'])) + '.lock'))
    value['physical_locks'] = [str(interop.parent / (f'.physical-core-{core}.lock' if value['host'] == 'gfn16-pilot-c4d'
                                                   else f'.physical-p{package}-c{core}.lock')) for package, core in cores]
    return value


def validate_serial(manifest):
    build = manifest['build']
    need(type(build.get('runtime_threads', 1)) is int and build.get('runtime_threads', 1) == 1, 'static model thread count is one')
    for flag in build['cflags']:
        match = re.fullmatch(r'-D[A-Za-z_][A-Za-z_0-9]*THREADS=(-?[0-9]+)', flag)
        need(match is None or int(match[1]) == 1, 'static runtime thread macro is one')
    need(manifest['probe']['expected_json'] == dict(context_threads=1, model_threads=1, expected_threads=1)
         and all(type(value) is int for value in manifest['probe']['expected_json'].values()), 'static exact one-thread probe')


def quota_module():
    # Imports happen only after complete snapshot validation in execute().
    # The dependency itself additionally verifies the frozen quota-v1 parent.
    pinned('tools/native_user_quota_v1.py')
    sys.path[:0] = [str(HERE.parent.parent), str(HERE.parent)]
    module = load('tools/native_user_quota_v2.py')
    need(Path(module.parent.__file__).resolve() == pinned('tools/native_user_quota_v1.py').resolve(), 'quota imported from exact snapshot')
    return module


def check_scratch_quota(path, used_bytes, used_inodes, selected):
    # Fixed static-lane worst-case reservation, without a new dynamic ledger.
    # Other jobs' allocated blocks are already reflected in kernel headroom;
    # only our own allocation is deducted. This may conservatively double-count
    # another active lane, but never silently omits its future build space.
    return quota_module().validate_headroom(Path(path),
        max(0, selected['static_lanes'] * selected['scratch_reservation_bytes'] - used_bytes),
        floor_bytes=selected['scratch_floor_bytes'],
        outstanding_reservation_inodes=max(0, selected['static_lanes'] * 4096 - used_inodes), floor_inodes=256)


def adapted_source(raw, selected):
    base = load('tools/native_shared_v1.py')
    text = base.adapted_source(raw, selected['memory_bytes'])
    def replace(old, new):
        nonlocal text
        need(text.count(old) == 1, 'unique static source anchor: ' + old[:60])
        text = text.replace(old, new, 1)
    replace("SELF = 'tools/native_shared_v1.py'", 'SELF = ' + repr(SELF))
    replace("scratch = Path(tempfile.mkdtemp(prefix='gfn16-source-gate-', dir='/dev/shm'))",
            "scratch = Path(tempfile.mkdtemp(prefix='gfn16-static-', dir=profile['scratch_base']))")
    replace("require(shutil.disk_usage(scratch).free >= 2*GIB + max(0, 768*MIB-allocated(scratch)), 'scratch reservation/floor')",
            "used = allocated(scratch)\n        inodes = sum(len(dirs) + len(names) for _, dirs, names in os.walk(scratch)) + 1\n"
            "        report['scratch_peak_allocated_bytes'] = max(report.get('scratch_peak_allocated_bytes', 0), used)\n"
            "        report['scratch_peak_observed_inodes'] = max(report.get('scratch_peak_observed_inodes', 0), inodes)\n"
            "        report['scratch_quota_admission'] = check_scratch_quota(scratch, used, inodes, profile)\n"
            "        require(used <= profile['scratch_abort_threshold_bytes'], 'scratch abort threshold; not a hard quota')")
    replace("scratch_reserve_bytes=768*MIB, scratch_floor_bytes=2*GIB,",
            "scratch_reserve_bytes=profile['scratch_reservation_bytes'], scratch_floor_bytes=profile['scratch_floor_bytes'],\n"
            "                              static_lane_reservation_bytes=profile['static_lanes']*profile['scratch_reservation_bytes'],\n"
            "                              scratch_reservation_evidence=profile['scratch_reservation_evidence'],")
    replace(f"require(int(mem['MemAvailable'].split()[0])*1024 >= {selected['memory_bytes']}, 'host memory floor')",
            "require(int(mem['MemAvailable'].split()[0])*1024 >= profile['minimum_host_available_bytes'], 'host memory floor')")
    replace("guard(); begin = time.monotonic(); failure = None; log = out / (name + '.log')",
            "guard(); begin = time.monotonic(); usage_before = resource.getrusage(resource.RUSAGE_CHILDREN); failure = None; log = out / (name + '.log')")
    replace("seconds=time.monotonic()-begin, error=repr(failure) if failure else None,",
            "seconds=time.monotonic()-begin, user_seconds=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime-usage_before.ru_utime,\n"
            "                                    system_seconds=resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime-usage_before.ru_stime,\n"
            "                                    cumulative_children_peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,\n"
            "                                    error=repr(failure) if failure else None,")
    return text


def parent(profile_id):
    selected = profile(profile_id)
    base = load('tools/native_shared_v1.py')
    module = types.ModuleType('_static_native_parent')
    module.__file__ = str(Path(__file__).resolve())
    module.__dict__.update(PROFILE_ID=profile_id, admit_lint=base.admit_lint,
                           validate_output=base.validate_output, check_scratch_quota=check_scratch_quota)
    exec(compile(adapted_source(pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes(), selected),
                 str(HERE / 'native_source_gate_aethia_cpu02_v2.py') + '[static-serial]', 'exec'), module.__dict__)
    module.PROFILES = {selected['host']: selected}
    return module


def execution_limits(selected):
    need(socket.gethostname() == selected['host'] and pwd.getpwuid(os.geteuid()).pw_name == selected['user'], 'approved static host/user')
    need(sorted(os.sched_getaffinity(0)) == selected['cpus'], 'exact static pair affinity')
    topology = {}
    for cpu in selected['topology']:
        directory = Path('/sys/devices/system/cpu') / f'cpu{cpu}/topology'
        topology[cpu] = [int((directory / key).read_text()) for key in ('physical_package_id', 'core_id')]
    need(topology == selected['topology'], 'full physical topology identity')
    group = Path('/proc/self/cgroup').read_text().strip()
    need(group.startswith('0::/') and '\n' not in group, 'unified cgroup')
    path = Path('/sys/fs/cgroup') / group[3:].lstrip('/')
    memory = (path / 'memory.max').read_text().strip()
    quota = (path / 'cpu.max').read_text().split()
    need(memory == str(selected['memory_bytes']) and len(quota) == 2 and quota[0] != 'max'
         and int(quota[0]) == 2 * int(quota[1]), 'exact static memory and two-core CPU caps')
    need((path / 'memory.swap.max').read_text().strip() == '0', 'zero swap')
    for ancestor in path.parents:
        if ancestor == Path('/sys/fs/cgroup') or not ancestor.is_relative_to('/sys/fs/cgroup'):
            break
        q = (ancestor / 'cpu.max').read_text().split()
        m = (ancestor / 'memory.max').read_text().strip()
        need((q[0] == 'max' or int(q[0]) >= 2 * int(q[1])) and (m == 'max' or int(m) >= selected['memory_bytes']), 'ancestor caps sufficient')
    available = int(next(row.split()[1] for row in Path('/proc/meminfo').read_text().splitlines() if row.startswith('MemAvailable:'))) * 1024
    need(available >= selected['memory_bytes'] + selected['minimum_host_available_bytes'], 'job plus host memory reserve')
    return dict(cgroup=group[3:], memory_max_bytes=int(memory), swap_max_bytes=0, cpu_max=quota,
                affinity=selected['cpus'], physical_cores=[topology[str(cpu)] for cpu in selected['cpus']], full_topology=topology)


def execute(manifest_path, pin, out):
    manifest_path, out = Path(manifest_path), Path(out)
    need(sha(manifest_path) == pin, 'manifest pin')
    manifest = json.loads(manifest_path.read_text())
    selected = profile(manifest['cpu_profile'])
    module = parent(manifest['cpu_profile'])
    root = Path(manifest['source_root'])
    need(Path.cwd() == root, 'exact source cwd')
    module.load_manifest(manifest_path, pin)
    for name, digest in PINS.items():
        need(manifest['sources'].get(name) == digest, 'closed static dependency: ' + name)
    validate_serial(manifest)
    need(manifest.get('phase') in ('lint', 'run') and 1 <= len(manifest['steps']) <= 64, 'explicit finite phase/steps')
    for step in manifest['steps']:
        need('validator' in step or ('expected_stdout' in step and 'expected_stderr' in step), 'explicit output contract')
    need(not (Path(selected['base']) / 'PAUSE').exists() and not (root / 'docs/briefs/PAUSE').exists(), 'native PAUSE')
    scratch_base = Path(selected['scratch_base'])
    need(scratch_base.is_dir() and scratch_base.resolve() == scratch_base and scratch_base.is_relative_to(selected['base']), 'pre-existing canonical durable scratch')
    module.execution_limits = lambda cpus: execution_limits(selected)
    execution_limits(selected)
    base = load('tools/native_shared_v1.py')
    with ExitStack() as stack:
        descriptors = [stack.enter_context(base.lock(Path(selected['interop']), True)),
                       stack.enter_context(base.lock(Path(selected['pair_lock'])))]
        descriptors += [stack.enter_context(base.lock(Path(name))) for name in selected['physical_locks']]
        module.LEASE_FDS = tuple(descriptors)
        check_scratch_quota(scratch_base, 0, 0, selected)
        return module.execute(manifest_path, pin, out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.manifest, args.manifest_sha256, args.output), indent=2))
