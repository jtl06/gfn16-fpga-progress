"""Additive threaded shared launcher hooks with separate job/compile leases.

This source successor does not dispatch. The scheduler must provide a fresh,
complete live-workload observer and its admitted pool policy. Missing observer,
occupied physical cores, or an unavailable legacy compile lock stops admission.
Frozen v1 source/evidence and its serial default are preserved.
"""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import socket
import sys
import types

HERE = Path(__file__).resolve().parent
SELF = 'tools/native_shared_v2.py'
HOST_PROFILE = 'cloud/aethia-native-thread-profiles-v2.json'
HOST_PROFILE_SHA = '837b27f292704ce8f46d03d37bed9b520aedc02da33a9b389b12588a71c5c916'
GCP_HOST_PROFILE = 'cloud/gcp-native-thread-profiles-v1.json'
GCP_HOST_PROFILE_SHA = 'c91d5c5519c9ef5c14aa1d1c014f2f4f0152170f77404cfd63dbabf4b5035fa5'
PINS = {
    'native_shared_v1.py': '7bae7c05f7a3a5a83c55f9eb4f9dc33476b3051841661da8a45627d20424e10b',
    'native_thread_config_v1.py': '900b4b7598a6f405ec87ceaa1e82dd391e02c18c4ddbb36f64fa93b5ac613be2',
    'native_resource_leases_v1.py': '7e6fbdb2b973a750a59261aab3c32b6a188c9a990201d13d3096266f68698e35',
    'native_user_quota_v1.py': 'a55c3192c85b272dad59acc5d4b782b69f78e927e2f559106534b27ba6aab3c3',
    'native_user_quota_v2.py': '1a628027f1f083866cd3ddb7246c2da27523623d05a5fd107b43271bdefccfe3',
}
SHARED_HELPERS = {
    'tools/native_source_gate_aethia_cpu02_v2.py', 'tools/native_shared_v1.py', SELF,
    'tools/native_package_v1.py', 'tools/native_package_v2.py', 'tools/build_identity_v1.py',
    'tools/build_identity_v2.py', 'tools/native_thread_config_v1.py',
    'tools/native_resource_leases_v1.py', 'tools/native_test_queue_v1.py',
    'tools/native_user_quota_v1.py',
    'tools/native_user_quota_v2.py',
    'tools/snapshot_native_sources_v2.py',
}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(name):
    path = HERE/name
    need(name in PINS and sha(path) == PINS[name], 'exact shared helper pin')
    spec = importlib.util.spec_from_file_location('_native_v2_'+path.stem, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def profile(profile_id):
    base = load('native_shared_v1.py')
    if profile_id in base.PROFILES:
        result = dict(base.PROFILES[profile_id])
        result.update(pool_max_jobs=2, pool_max_job_cpus=2,
                      pool_max_job_memory_bytes=result['memory_bytes'], cpu_quota_percent=200,
                      scratch_base='/dev/shm', scratch_floor_bytes=2*(1<<30),
                      scratch_reservation_bytes=768*(1<<20), scratch_abort_threshold_bytes=None,
                      scratch_reservation_evidence='Inherited 768MiB estimate; not a measured per-build upper bound.')
    else:
        descriptor, descriptor_sha = ((GCP_HOST_PROFILE, GCP_HOST_PROFILE_SHA)
            if profile_id.startswith('gcp-c4d-') else (HOST_PROFILE, HOST_PROFILE_SHA))
        path = HERE.parent/descriptor
        need(sha(path) == descriptor_sha, 'exact host/tool/topology profile')
        host = json.loads(path.read_text())
        need(host['schema'] == 'gfn16-native-thread-host-v1'
             and profile_id in host['profiles'], 'approved host profile')
        result = {name: host[name] for name in ('host', 'user', 'base', 'topology', 'verilator_dir',
            'hashes', 'lock', 'interop', 'minimum_host_available_bytes', 'pool_max_jobs',
            'pool_max_job_cpus', 'pool_max_job_memory_bytes',
            'scratch_base', 'scratch_floor_bytes', 'scratch_reservation_bytes',
            'scratch_abort_threshold_bytes', 'scratch_reservation_evidence')}
        if 'observed_total_memory_bytes' in host:
            result['observed_total_memory_bytes'] = host['observed_total_memory_bytes']
        for name in ('compiler_path', 'compiler_alias', 'python_path'):
            if name in host:
                result[name] = host[name]
        result.update(host['profiles'][profile_id])
        result.update(host_profile_path=descriptor, host_profile_sha256=descriptor_sha)
    result.setdefault('compiler_path', '/usr/bin/x86_64-linux-gnu-g++-15')
    result.setdefault('compiler_alias', '/usr/bin/g++')
    result.setdefault('python_path', '/usr/bin/python3.14')
    result['tool_paths'] = dict(verilator=result['verilator_dir']+'/verilator',
        verilator_bin=result['verilator_dir']+'/verilator_bin', compiler=result['compiler_path'],
        python=result['python_path'], make='/usr/bin/make', taskset='/usr/bin/taskset', compiler_alias=result['compiler_alias'])
    result['runtime_allocation'] = dict(cpus=result['cpus'],
        physical_cores=[result['topology'][str(cpu)] for cpu in result['cpus']],
        cpu_quota_percent=result['cpu_quota_percent'], compile_workers=2, memory_bytes=result['memory_bytes'])
    return result


def lint_identity(manifest, selected):
    runtime = load('native_thread_config_v1.py')
    count = runtime.validate_build(manifest['build'], manifest['probe']['expected_json'])
    excluded = set(SHARED_HELPERS)
    baseline = manifest.get('lint_baseline')
    if baseline:
        excluded.update(baseline[key] for key in ('baseline', 'review'))
    compiled = set(manifest['build']['sv_sources']) | {manifest['build']['cpp_source']}
    # A source's directory never exempts it: even a compiled tools/ file is
    # included. Only exact shared control files and circular baseline receipts
    # are excluded; adapters, oracles, ROMs and runtime fixtures remain bound.
    sources = {name: pin for name, pin in manifest['sources'].items()
               if name not in excluded or name in compiled}
    return dict(build=manifest['build'], sources=sources, tool_hashes=selected['hashes'],
        host=selected['host'], lint_flags=['--lint-only', '-Wall', '--threads', str(count)])


def adapted_source(raw, selected):
    base = load('native_shared_v1.py')
    text = base.adapted_source(raw, selected['memory_bytes'])
    single = ("    require(manifest['probe']['expected_json'] == dict(context_threads=1, model_threads=1, expected_threads=1)\n"
              "            and all(type(v) is int for v in manifest['probe']['expected_json'].values()), 'single-thread runtime probe contract')")
    compile_block = ("        with lockpath.open('r') as lock:\n"
                     "            deadline = time.monotonic() + 1800\n"
                     "            while True:\n"
                     "                try:\n"
                     "                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                     "                    break\n"
                     "                except BlockingIOError:\n"
                     "                    guard(); require(time.monotonic() < deadline, 'compile lock timeout'); time.sleep(.25)")
    changes = [
        ('SELF = '+repr(base.SELF), 'SELF = '+repr(SELF)),
        ("compiler=Path('/usr/bin/x86_64-linux-gnu-g++-15')", 'compiler=Path(COMPILER_PATH)'),
        ("python=Path('/usr/bin/python3.14')", 'python=Path(PYTHON_PATH)'),
        ("Path('/usr/bin/g++')", 'Path(COMPILER_ALIAS)'),
        ("CXX='/usr/bin/x86_64-linux-gnu-g++-15'", 'CXX=COMPILER_PATH'),
        (single, "    runtime.validate_build(build, manifest['probe']['expected_json'])"),
        ("compile_workers=2, model_threads=1,", "compile_workers=2, model_threads=manifest['build']['runtime_threads'],\n"
         "                  context_threads=manifest['build']['runtime_threads'], runtime_allocation=profile['runtime_allocation'],"),
        ("'--cc', '--exe', '--build', '-j', '2', '--threads', '1',",
         "'--cc', '--exe', '--build', '-j', '2', '--threads', str(config['runtime_threads']),"),
        ("'--lint-only', '-Wall', '--threads', '1',",
         "'--lint-only', '-Wall', '--threads', str(config['runtime_threads']),"),
        (compile_block, '        with compile_slot(lockpath, guard, report, save):'),
        ("pass_fds=LEASE_FDS + ((lock.fileno(),) if name in ('lint', 'build') else ())",
         'pass_fds=inherited_fds(name)'),
        ("        guard(); begin = time.monotonic(); failure = None; log = out / (name + '.log')",
         "        guard(); cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)\n"
         "        begin = time.monotonic(); failure = None; log = out / (name + '.log')"),
        ("seconds=time.monotonic()-begin, error=repr(failure) if failure else None,",
         "seconds=time.monotonic()-begin,\n"
         "                                    user_seconds=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime-cpu_before.ru_utime,\n"
         "                                    system_seconds=resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime-cpu_before.ru_stime,\n"
         "                                    error=repr(failure) if failure else None,"),
        ("    def guard():\n        require(time.monotonic() - started < 3600, 'overall timeout')",
         "    def guard():\n        check_lease()\n        require(time.monotonic() - started < 3600, 'overall timeout')"),
        ("dir='/dev/shm'", 'dir=SCRATCH_BASE'),
        ("scratch_reserve_bytes=768*MIB, scratch_floor_bytes=2*GIB,",
         'scratch_reserve_bytes=SCRATCH_RESERVATION_BYTES, scratch_floor_bytes=SCRATCH_FLOOR_BYTES,'),
        ("        require(shutil.disk_usage(scratch).free >= 2*GIB + max(0, 768*MIB-allocated(scratch)), 'scratch reservation/floor')",
         "        used_scratch = allocated(scratch)\n"
         "        report['peak_scratch_allocated_bytes'] = max(report.get('peak_scratch_allocated_bytes', 0), used_scratch)\n"
         "        report['scratch_reservation_evidence'] = SCRATCH_RESERVATION_EVIDENCE\n"
         "        if SCRATCH_ABORT_THRESHOLD_BYTES is not None:\n"
         "            require(used_scratch <= SCRATCH_ABORT_THRESHOLD_BYTES, 'scratch abort threshold exceeded; possible polling overshoot')\n"
         "        outstanding_scratch = max(0, SCRATCH_RESERVATION_BYTES-used_scratch)\n"
         "        require(shutil.disk_usage(scratch).free >= SCRATCH_FLOOR_BYTES+outstanding_scratch, 'scratch reservation/floor')\n"
         "        report['scratch_quota_admission'] = check_scratch_quota(scratch, outstanding_scratch)"),
    ]
    for old, new in changes:
        need(text.count(old) == 1, 'unique threaded source adapter anchor')
        text = text.replace(old, new, 1)
    return text


def parent(profile_id):
    base = load('native_shared_v1.py')
    selected = profile(profile_id)
    runtime = load('native_thread_config_v1.py')
    module = types.ModuleType('_shared_native_thread_parent')
    module.__file__ = str(Path(__file__).resolve())
    # Replace only the independently reviewed baseline identity computation in
    # the pinned v1 function; normalization and exact diagnostics are inherited.
    lint_namespace = dict(base.admit_lint.__globals__, lint_identity=lint_identity)
    admit = types.FunctionType(base.admit_lint.__code__, lint_namespace, base.admit_lint.__name__)
    module.__dict__.update(PROFILE_ID=profile_id, runtime=runtime, admit_lint=admit,
        validate_output=base.validate_output, SCRATCH_BASE=selected['scratch_base'],
        COMPILER_PATH=selected['compiler_path'], COMPILER_ALIAS=selected['compiler_alias'],
        PYTHON_PATH=selected['python_path'],
        SCRATCH_RESERVATION_BYTES=selected['scratch_reservation_bytes'],
        SCRATCH_FLOOR_BYTES=selected['scratch_floor_bytes'],
        SCRATCH_ABORT_THRESHOLD_BYTES=selected['scratch_abort_threshold_bytes'],
        SCRATCH_RESERVATION_EVIDENCE=selected['scratch_reservation_evidence'])
    exec(compile(adapted_source((HERE/base.PARENT).read_bytes(), selected),
                 str(HERE/base.PARENT)+'[threaded-shared-profile]', 'exec'), module.__dict__)
    module.PROFILES = {selected['host']: selected}
    return module


def execution_limits(selected):
    need(socket.gethostname() == selected['host'] and pwd.getpwuid(os.geteuid()).pw_name == selected['user'], 'approved host/user')
    need(sorted(os.sched_getaffinity(0)) == selected['cpus'], 'exact physical-core affinity')
    topology = {}
    for cpu in sorted(map(int, selected['topology'])):
        path = Path('/sys/devices/system/cpu')/f'cpu{cpu}/topology'
        topology[str(cpu)] = [int((path/key).read_text()) for key in ('physical_package_id', 'core_id')]
    need(topology == selected['topology'], 'full topology/SMT sibling identity')
    group = Path('/proc/self/cgroup').read_text().strip()
    need(group.startswith('0::/') and '\n' not in group, 'unified cgroup')
    path = Path('/sys/fs/cgroup')/group[3:].lstrip('/')
    memory = (path/'memory.max').read_text().strip()
    quota = (path/'cpu.max').read_text().split()
    percent = selected['cpu_quota_percent']
    need(memory == str(selected['memory_bytes']) and len(quota) == 2 and quota[0] != 'max'
         and int(quota[0])*100 == percent*int(quota[1]), 'exact aggregate memory/CPU cap')
    need((path/'memory.swap.max').read_text().strip() == '0', 'zero swap')
    for ancestor in path.parents:
        if ancestor == Path('/sys/fs/cgroup'):
            break
        if not ancestor.is_relative_to('/sys/fs/cgroup'):
            break
        q = (ancestor/'cpu.max').read_text().split()
        m = (ancestor/'memory.max').read_text().strip()
        need((q[0] == 'max' or int(q[0])*100 >= percent*int(q[1]))
             and (m == 'max' or int(m) >= selected['memory_bytes']), 'ancestor cap sufficient')
    mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    available = int(mem['MemAvailable'].split()[0])*1024
    total = int(mem['MemTotal'].split()[0])*1024
    need(available >= selected['minimum_host_available_bytes'], 'host memory reserve')
    if 'observed_total_memory_bytes' in selected:
        need(total == selected['observed_total_memory_bytes'], 'observed host total memory')
    actual = dict(cgroup=group[3:], memory_max_bytes=int(memory), swap_max_bytes=0, cpu_max=quota,
        affinity=selected['cpus'], physical_cores=[topology[str(cpu)] for cpu in selected['cpus']],
        full_topology=topology, host_total_memory_bytes=total)
    runtime = load('native_thread_config_v1.py')
    runtime.validate_allocation(selected['runtime_allocation'], 1)
    need(actual['physical_cores'] == selected['runtime_allocation']['physical_cores'], 'actual physical-core allocation')
    return actual


def pool_policy(selected, supplied, total_memory_bytes):
    topology = [dict(cpu=int(cpu), package_id=core[0], core_id=core[1])
                for cpu, core in sorted(selected['topology'].items(), key=lambda item: int(item[0]))]
    interop = Path(selected['interop'])
    cores = set(map(tuple, selected['topology'].values()))
    core_locks = {core: interop.parent/(f'.physical-p{core[0]}-c{core[1]}.lock'
        if selected['host'] == 'aethia' else f'.physical-core-{core[1]}.lock') for core in cores}
    expected = dict(directory=Path(selected['base'])/'leases-v1', topology=topology,
        total_memory_bytes=total_memory_bytes, memory_floor_bytes=selected['minimum_host_available_bytes'],
        max_jobs=selected['pool_max_jobs'], max_job_cpus=selected['pool_max_job_cpus'],
        max_job_memory_bytes=selected['pool_max_job_memory_bytes'], core_locks=core_locks,
        mode_lock=interop)
    need(supplied == expected, 'exact scheduler pool policy and live total memory')
    return expected


def execute(manifest_path, pin, out, *, lease_id, resource_profile, observer):
    """Called by a finite scheduler after its host observation/policy admission."""
    base = load('native_shared_v1.py')
    need(sha(manifest_path) == pin, 'manifest pin')
    manifest = json.loads(manifest_path.read_text())
    selected = profile(manifest['cpu_profile'])
    root = Path(manifest['source_root'])
    need(Path.cwd() == root, 'exact source cwd')
    need(Path(__file__).resolve() == root/SELF, 'threaded launcher inside pinned snapshot')
    # The frozen closure checker imports no role modules. Every snapshot file
    # is checked before importing resource or role validator code from it.
    # This exact frozen checker has no host assertion. Its parent constructor
    # receives its own known v1 profile, never a new profile it cannot load.
    base.parent('gcp-c4d-sim01-v1').check_sources(root, manifest['sources'])
    need(manifest['sources'].get(SELF) == sha(Path(__file__)), 'threaded launcher in source closure')
    if 'host_profile_path' in selected:
        need(manifest['sources'].get(selected['host_profile_path']) == selected['host_profile_sha256'],
             'exact host profile in source closure')
    if len(selected['cpus']) > 2:
        need(manifest['build']['parameters'].get('AW') == 16, 'full physical allocation only for long AW16')
    runtime = load('native_thread_config_v1.py')
    count = runtime.validate_build(manifest['build'], manifest['probe']['expected_json'])
    runtime.validate_allocation(selected['runtime_allocation'], count)
    limits = execution_limits(selected)
    need(callable(observer), 'scheduler fresh complete workload observer required')
    sys.path[:0] = [str(root.parent), str(root)]
    quota = load('native_user_quota_v2.py')
    for name in ('native_user_quota_v1.py', 'native_user_quota_v2.py'):
        need(manifest['sources'].get('tools/'+name) == PINS[name], 'exact own-UID quota guard in source closure')
    # Refuse before reserving cores or starting a compiler when tmpfs's
    # per-user blocks/inodes cannot cover the existing reservation plus floor.
    quota.validate_headroom(Path(selected['scratch_base']), selected['scratch_reservation_bytes'],
                           floor_bytes=selected['scratch_floor_bytes'])
    need(not (Path(selected['base'])/'PAUSE').exists() and not (root/'docs/briefs/PAUSE').exists(), 'native PAUSE')
    need(manifest.get('phase') in ('lint', 'run') and 1 <= len(manifest['steps']) <= 64, 'finite explicit native phase')
    for step in manifest['steps']:
        need('validator' in step or ('expected_stdout' in step and 'expected_stderr' in step), 'explicit output contract')
    total = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemTotal:')))*1024
    policy = pool_policy(selected, resource_profile, total)
    leases = load('native_resource_leases_v1.py')
    module = parent(manifest['cpu_profile'])
    module.execution_limits = lambda cpus: execution_limits(selected)
    module.load_manifest(manifest_path, pin)
    active_compile = []
    with leases.ResourcePool(**policy).acquire(lease_id, selected['cpus'], selected['memory_bytes'],
            observer=observer, wait_seconds=0) as job:
        def check_lease():
            job.check()
            for held in active_compile:
                held.check()
            execution_limits(selected)
            need(not (Path(selected['base'])/'PAUSE').exists(), 'live host PAUSE')

        @contextmanager
        def compile_slot(lockpath, guard, report, save):
            slots = leases.CompileSlots(lockpath, Path(selected['base'])/'compile-slots-v1')
            with slots.acquire(wait_seconds=0, guard=guard) as held:
                active_compile.append(held)
                report['compile_slot'] = held.receipt
                report['resource_lease'] = job.receipt
                report['admitted_limits'] = limits
                save()
                try:
                    yield held
                finally:
                    active_compile.pop()

        def inherited_fds(name):
            return job.pass_fds + (active_compile[0].pass_fds if name in ('lint', 'build') else ())

        def check_scratch_quota(scratch, reservation):
            result = quota.validate_headroom(scratch, reservation, floor_bytes=selected['scratch_floor_bytes'])
            if hasattr(observer, 'validate_disk'):
                result['aggregate_admission'] = observer.validate_disk()
            need(type(result) is dict, 'scratch quota admission receipt')
            json.dumps(result)
            return result

        module.__dict__.update(check_lease=check_lease, compile_slot=compile_slot,
                              inherited_fds=inherited_fds, check_scratch_quota=check_scratch_quota)
        return module.execute(manifest_path, pin, out)
