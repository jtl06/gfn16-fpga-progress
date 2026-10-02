"""One fixed-allocation, short promoted-T5b 2/4/8-thread native pilot.

This additive runner retains the frozen threaded/class/static source adapters,
j2/exclusive compile lock, per-child wait4 evidence, declared runtime files,
quota/source/deadline guards and inherited physical/mode descriptors. It does
not admit other designs, long cases, four-core profiles or dynamic allocation.
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
import socket
import time
import types

HERE = Path(__file__).resolve().parent
SELF = 'tools/native_threaded_wide_v1.py'
BASE_SHA = '4633c3ca20a6560fdeed35590922a01de8cd572b1bf127e3d2faa4a96734751f'
PROFILE_SOURCE = 'cloud/azure-burst16-thread-wide-profiles-v1.json'
PROFILE_SHA = '6991626ec38018943ff4ff5c88eb7808301ef195d7e48686cbbbd4e4cc135808'
OBSERVATION = 'results/throughput-20260929/core27-t5b-thread-wide-topology-v1/observation-v2.json'
OBSERVATION_SHA = 'd001cb0cb31811ac965d0828dfdf2d6ffacf120d8d7a976b9944315a6fa646a3'
ROLE = 'results/throughput-20260929/core27-t5b-thread-pilot-source-v1/t5b-cold-warm-threads1-manifest.json'
ROLE_SHA = '42fb4fde0a6ca2cd7b8c2069c353974656b1bb726f841ce19723597ca6c5b1e6'
PROFILE_ID = 'azure-burst16-thread-wide07-v1'
DEADLINE = 1791162766
DRAIN_LEAD_SECONDS = 7200


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pinned(relative, digest):
    path = HERE.parent / relative
    need(path.is_file() and not path.is_symlink() and sha(path) == digest, 'exact wide pilot dependency: ' + relative)
    return path


def base():
    path = pinned('tools/native_threaded_class_v1.py', BASE_SHA)
    spec = importlib.util.spec_from_file_location('_fixed_wide_thread_parent', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def descriptor():
    data = json.loads(pinned(PROFILE_SOURCE, PROFILE_SHA).read_text())
    observed = json.loads(pinned(OBSERVATION, OBSERVATION_SHA).read_text())
    inherited = base().profile(data['base_profile'])
    need(data['schema'] == 'gfn16-fixed-wide-thread-pilot-profile-v1'
         and data['host'] == observed['host'] == inherited['host'] and observed['uid'] == inherited['uid'], 'fixed observed wide host')
    need(data['hardware_profile_source'] == inherited['profile_source']
         and data['hardware_profile_sha256'] == inherited['profile_sha256'], 'hardware identity separate from allocation overlay')
    need(data['topology_observation'] == OBSERVATION and data['topology_observation_sha256'] == OBSERVATION_SHA
         and observed['online'] == '0-15' and len(observed['cpus']) == 16, 'exact current topology/cache observation')
    selected = data['profiles'][PROFILE_ID]
    need(list(data['profiles']) == [PROFILE_ID] and selected['cpus'] == list(range(8))
         and selected['cpu_quota_percent'] == 800 and selected['memory_bytes'] == 8 << 30
         and selected['compile_workers'] == 2 and selected['model_thread_counts'] == [2, 4, 8], 'one fixed eight-physical-core pilot ceiling')
    parents = [base().profile(name) for name in selected['constituent_profiles']]
    need([cpu for item in parents for cpu in item['cpus']] == selected['cpus'], 'exact four constituent serial pairs')
    for cpu, row in observed['cpus'].items():
        need([row['physical_package_id'], row['core_id']] == inherited['topology'][cpu]
             and row['thread_siblings_list'] == cpu, 'sixteen observed physical cores without SMT inflation')
    for cpu in selected['cpus']:
        need(observed['cpus'][str(cpu)]['l3'] == [selected['observed_l3']], 'single observed L3 domain, not assumed CCD')
    for field in ('minimum_host_available_bytes', 'scratch_reservation_bytes', 'scratch_floor_bytes', 'scratch_abort_threshold_bytes'):
        need(data[field] == inherited[field], 'unchanged durable/host policy: ' + field)
    need(data['outer_seconds'] == 3700 and data['stop_grace_seconds'] == 15, 'retained finite duration envelope')
    return data, observed, inherited, parents


def dependencies():
    return dict(base().PINS, **{'tools/native_threaded_class_v1.py': BASE_SHA,
        PROFILE_SOURCE: PROFILE_SHA, OBSERVATION: OBSERVATION_SHA, ROLE: ROLE_SHA})


PINS = dependencies()
SELECTIONS = {PROFILE_ID: PROFILE_ID}


def profile(profile_id):
    need(profile_id == PROFILE_ID, 'only fixed wide short-pilot profile')
    data, observed, inherited, parents = descriptor()
    selected = copy.deepcopy(inherited)
    selected.update(data['profiles'][profile_id])
    selected.update(profile_id=profile_id, profile_source=PROFILE_SOURCE, profile_sha256=PROFILE_SHA,
        hardware_profile_source=data['hardware_profile_source'], hardware_profile_sha256=data['hardware_profile_sha256'],
        topology_observation=OBSERVATION, topology_observation_sha256=OBSERVATION_SHA,
        shared_locks=list(dict.fromkeys(name for item in parents for name in item['shared_locks'])),
        constituent_pair_locks=[item['pair_lock'] for item in parents],
        physical_locks=[name for item in parents for name in item['physical_locks']],
        fixed_placement=dict(id='burst16-wide07-v1', lane_ids=data['profiles'][profile_id]['constituent_profiles'], cpus=list(range(8))))
    selected['pair_lock'] = str(Path(selected['base']) / '.thread-wide-0-7.lock')
    selected['runtime_allocation'] = dict(cpus=selected['cpus'], physical_cores=[selected['topology'][str(cpu)] for cpu in selected['cpus']],
        cpu_quota_percent=800, compile_workers=2, memory_bytes=selected['memory_bytes'])
    base().load('native_thread_config_v1.py', base().RUNTIME_SHA).validate_allocation(selected['runtime_allocation'], 8)
    return selected


def validate_threaded(manifest):
    """Only the already-qualified two-square fixture may use this successor."""
    original = json.loads(pinned(ROLE, ROLE_SHA).read_text())
    runtime = base().load('native_thread_config_v1.py', base().RUNTIME_SHA)
    count = runtime.validate_build(manifest['build'], manifest['probe']['expected_json'])
    need(count in (2, 4, 8), 'wide short pilot counts two/four/eight only')
    build = copy.deepcopy(manifest['build'])
    build['runtime_threads'] = 1
    build['cflags'] = ['-DGFN16_RUNTIME_THREADS=1' if flag == f'-DGFN16_RUNTIME_THREADS={count}' else flag for flag in build['cflags']]
    need(build == original['build'] and manifest['steps'] == original['steps']
         and manifest['probe']['argv'] == original['probe']['argv'], 'exact promoted-T5b cold/warm compiled recipe and output contract')
    need(all(manifest['sources'].get(name) == digest for name, digest in original['sources'].items())
         and manifest['sources'].get(ROLE) == ROLE_SHA, 'unchanged complete 59-member T5b donor')
    return count


def guard_protected(selected):
    need(selected['profile_id'] == PROFILE_ID and selected['burst_deadline_epoch'] == DEADLINE, 'exact wide protected profile/deadline')
    need(time.time() + 3715 < DEADLINE - DRAIN_LEAD_SECONDS, 'full3715 wide pilot before unchanged two-hour drain')
    return base().source_policy().host.guard_protected(selected)


def guard_toolchain(selected):
    guard_protected(selected)
    host = base().source_policy().host
    prior = host.previous()
    return prior.load('tools/native_runtime_toolchain_v1.py', prior.RUNTIME_SHA).verify_files(selected)


def adapted_source(raw, selected):
    text = base().adapted_source(raw, selected)
    for old, new in [('SELF = ' + repr(base().SELF), 'SELF = ' + repr(SELF)),
                     ('    def guard():\n', '    def guard():\n        guard_protected(profile)\n')]:
        need(text.count(old) == 1, 'unique fixed-wide source anchor')
        text = text.replace(old, new, 1)
    return text


def parent(profile_id):
    inherited = base()
    source = inherited.source_policy()
    static = source.host.static_module()
    shared = static.load('tools/native_shared_v1.py')
    selected = profile(profile_id)
    module = types.ModuleType('_fixed_wide_thread_native_parent')
    module.__file__ = str(Path(__file__).resolve())
    module.__dict__.update(PROFILE_ID=profile_id, classify=source.classes.classify, LintClassError=source.classes.LintClassError,
        validate_output=shared.validate_output, check_scratch_quota=static.check_scratch_quota,
        guard_toolchain=guard_toolchain, guard_protected=guard_protected, RUNTIME_CHECK=None,
        runtime=inherited.load('native_thread_config_v1.py', inherited.RUNTIME_SHA),
        identity=inherited.load('build_identity_v2.py', inherited.IDENTITY_SHA),
        MeasuredPopen=inherited.load('native_child_usage_v1.py', inherited.USAGE_SHA), validate_threaded=validate_threaded)
    raw = static.pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
    exec(compile(adapted_source(raw, selected), str(Path(__file__).resolve()) + '[fixed-wide-short-pilot]', 'exec'), module.__dict__)
    module.PROFILES = {selected['host']: selected}
    return module


def execution_limits(selected):
    need(socket.gethostname() == selected['host'] and os.geteuid() == selected['uid']
         and pwd.getpwuid(os.geteuid()).pw_name == selected['user'], 'approved wide host and own user')
    need(sorted(os.sched_getaffinity(0)) == selected['cpus'], 'exact fixed eight-core affinity')
    syscpu = Path('/sys/devices/system/cpu')
    need((syscpu / 'online').read_text().strip() == '0-15', 'unchanged sixteen-core online shape')
    topology = {}
    for cpu in selected['topology']:
        directory = syscpu / ('cpu' + cpu)
        topology[cpu] = [int((directory / 'topology' / key).read_text()) for key in ('physical_package_id', 'core_id')]
        need((directory / 'topology/thread_siblings_list').read_text().strip() == cpu, 'one logical CPU per observed physical core')
        if int(cpu) in selected['cpus']:
            rows = [{key: (cache / key).read_text().strip() for key in ('level', 'type', 'id', 'shared_cpu_list')}
                    for cache in (directory / 'cache').glob('index*') if (cache / 'level').read_text().strip() == '3']
            need(rows == [selected['observed_l3']], 'live selected L3/cache domain identity')
    need(topology == selected['topology'], 'full wide physical topology identity')
    group = Path('/proc/self/cgroup').read_text().strip()
    need(group.startswith('0::/') and '\n' not in group, 'unified cgroup')
    directory = Path('/sys/fs/cgroup') / group[3:].lstrip('/')
    memory, quota = (directory / 'memory.max').read_text().strip(), (directory / 'cpu.max').read_text().split()
    need(memory == str(selected['memory_bytes']) and len(quota) == 2 and quota[0] != 'max'
         and int(quota[1]) > 0 and int(quota[0]) == 8 * int(quota[1]), 'exact eight-GiB and eight-core aggregate caps')
    need((directory / 'memory.swap.max').read_text().strip() == '0', 'wide zero swap')
    for ancestor in directory.parents:
        if ancestor == Path('/sys/fs/cgroup') or not ancestor.is_relative_to('/sys/fs/cgroup'):
            break
        q, m = (ancestor / 'cpu.max').read_text().split(), (ancestor / 'memory.max').read_text().strip()
        need((q[0] == 'max' or int(q[0]) >= 8 * int(q[1])) and (m == 'max' or int(m) >= selected['memory_bytes']), 'wide ancestor caps sufficient')
    available = int(next(row.split()[1] for row in Path('/proc/meminfo').read_text().splitlines() if row.startswith('MemAvailable:'))) * 1024
    need(available >= selected['memory_bytes'] + selected['minimum_host_available_bytes'], 'wide job plus host memory reserve')
    return dict(cgroup=group[3:], memory_max_bytes=int(memory), swap_max_bytes=0, cpu_max=quota,
        affinity=selected['cpus'], physical_cores=[topology[str(cpu)] for cpu in selected['cpus']], full_topology=topology,
        observed_l3=selected['observed_l3'], compile_workers=2, hardware_profile_sha256=selected['hardware_profile_sha256'])


def execute(manifest_path, pin, out):
    manifest_path, out = Path(manifest_path), Path(out)
    need(sha(manifest_path) == pin, 'wide manifest pin before locks/output')
    manifest = json.loads(manifest_path.read_text())
    selected = profile(manifest['cpu_profile'])
    module = parent(manifest['cpu_profile'])
    root = Path(manifest['source_root'])
    need(Path.cwd() == root, 'exact wide source cwd')
    module.load_manifest(manifest_path, pin)
    for name, digest in PINS.items():
        need(manifest['sources'].get(name) == digest, 'closed wide runtime dependency: ' + name)
    validate_threaded(manifest)
    need(manifest.get('phase') in ('lint', 'run') and len(manifest['steps']) == 1, 'finite short-pilot phase only')
    need(not (Path(selected['base']) / 'PAUSE').exists() and not (root / 'docs/briefs/PAUSE').exists(), 'native wide PAUSE')
    scratch_base = Path(selected['scratch_base'])
    need(scratch_base.is_dir() and scratch_base.resolve() == scratch_base and scratch_base.is_relative_to(selected['base']), 'existing canonical wide durable scratch')
    module.execution_limits = lambda cpus: execution_limits(selected)
    execution_limits(selected)
    guard_protected(selected)
    static = base().source_policy().host.static_module()
    shared = static.load('tools/native_shared_v1.py')
    with ExitStack() as stack:
        fds = [stack.enter_context(shared.lock(Path(selected['interop']), True))]
        fds += [stack.enter_context(shared.lock(Path(name), True)) for name in selected['shared_locks']]
        fds += [stack.enter_context(shared.lock(Path(name))) for name in [selected['pair_lock'], *selected['constituent_pair_locks'], *selected['physical_locks']]]
        module.LEASE_FDS = tuple(fds)
        static.check_scratch_quota(scratch_base, 0, 0, selected)
        return module.execute(manifest_path, pin, out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.manifest, args.manifest_sha256, args.output), indent=2))
