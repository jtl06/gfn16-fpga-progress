"""Observed F16 static lanes with fit interop and pinned runtime inventory.

An additive binding over frozen v2/v1: no changed historical runner or packet.
The F16 slot lock is shared for the whole job and inherited alongside exclusive
physical locks. Complete declared runtime files/symlinks are checked outside
timed commands; the earlier protected deadline is read-only and preserved.
"""
import argparse
from contextlib import ExitStack
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import types

HERE = Path(__file__).resolve().parent
SELF = 'tools/native_static_v3.py'
V2_SHA = '6bfe9e244e50da02f9d3b3b1f47b0b7273158fc0b640c4311352a818b1705f6f'
RUNTIME_SHA = '1556444c29fa2ae2e891cced55220ac81d11dd9fa51294db75571d5eb5f8bd5b'
F16_PROFILE = 'cloud/azure-native-static-profiles-v1.json'
F16_PROFILE_SHA = 'c6d0dd6cc08f305492f7569eb0dfd08a855e1c75373917c3c971efae8fc871eb'
F16_OBSERVATION = 'results/throughput-20260929/azure-simulation-setup-v6/toolchain-observation-v1.json'
F16_OBSERVATION_SHA = 'f837ea7803e820e22ee08bf5bf9ff3e166924745737c7c595278f1cd5fe4b01b'
PROTECTED = 'cloud/azure-protected-admission-earlier-v1.json'
PROTECTED_SHA = 'c2913b1c3c24e85cacbe46fe4de6c6935d5acbcb819a8867e96453d16ed1b6c0'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(relative, digest):
    path = HERE.parent / relative
    need(sha(path) == digest, 'observed F16 dependency pin: ' + relative)
    spec = importlib.util.spec_from_file_location('_static_v3_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def v2():
    return load('tools/native_static_v2.py', V2_SHA)


def static_module():
    return v2().static_module()


def descriptor():
    for name, pin in ((F16_PROFILE, F16_PROFILE_SHA), (F16_OBSERVATION, F16_OBSERVATION_SHA), (PROTECTED, PROTECTED_SHA)):
        need(sha(HERE.parent / name) == pin, 'closed observed F16 descriptor')
    data = json.loads((HERE.parent / F16_PROFILE).read_text())
    observed = json.loads((HERE.parent / F16_OBSERVATION).read_text())
    protected = json.loads((HERE.parent / PROTECTED).read_text())
    need(data['schema'] == 'gfn16-static-native-host-v3' and observed['schema'] == 'azure-native-toolchain-observation-v1', 'actual F16 data schema')
    need(data['toolchain_observation_path'] == F16_OBSERVATION and data['toolchain_observation_sha256'] == F16_OBSERVATION_SHA, 'observed F16 tool inventory correspondence')
    for key in ('host', 'user', 'uid', 'hashes', 'topology', 'observed_total_memory_bytes'):
        need(data[key] == observed[key], 'observed F16 field correspondence: ' + key)
    paths = dict(compiler='compiler_path', compiler_alias='compiler_alias', python='python_path', make='make_path', taskset='taskset_path')
    for name, field in paths.items():
        need(data[field] == observed['paths'][name], 'observed F16 runtime path')
    need(data['verilator_dir'] + '/verilator' == observed['paths']['verilator'] and data['verilator_dir'] + '/verilator_bin' == observed['paths']['verilator_bin'], 'observed Verilator paths')
    need(data['protected_admission_path'] == PROTECTED and data['protected_admission_sha256'] == PROTECTED_SHA
         and data['protected_deadline_epoch'] == protected['authorized_epoch'] == 1791153913
         and data['host'] == protected['hostname'], 'preserved earlier protected F16 deadline')
    need(data['static_lanes'] == 8 and data['compile_workers'] == 2 and data['model_threads'] == 1, 'static F16 lane policy')
    cores = set()
    for item in data['profiles'].values():
        need(len(item['cpus']) == 2 and item['memory_bytes'] == 8 * (1 << 30) and item['cpu_quota_percent'] == 200, 'serial F16 physical-pair cap')
        pair = {tuple(data['topology'][str(cpu)]) for cpu in item['cpus']}
        need(len(pair) == 2 and not pair & cores and len(item['shared_locks']) == 1, 'disjoint F16 pairs with fit-slot interop')
        cores.update(pair)
    need(len(cores) == 16 and 8 * (8 << 30) + data['minimum_host_available_bytes'] < data['observed_total_memory_bytes'], 'aggregate F16 RAM and topology')
    return data, observed, protected


def dependencies():
    return dict(v2().dependencies(), **{'tools/native_static_v2.py': V2_SHA,
        'tools/native_runtime_toolchain_v1.py': RUNTIME_SHA, F16_PROFILE: F16_PROFILE_SHA,
        F16_OBSERVATION: F16_OBSERVATION_SHA, PROTECTED: PROTECTED_SHA})


PINS = dependencies()
SELECTIONS = dict(v2().SELECTIONS, **{name: name for name in descriptor()[0]['profiles']})


def profile(profile_id):
    previous = v2()
    if profile_id in previous.SELECTIONS:
        selected = previous.profile(profile_id)
        selected['shared_locks'] = []
    else:
        data, observed, protected = descriptor()
        need(profile_id in data['profiles'], 'approved observed F16 pair')
        selected = copy.deepcopy(data)
        selected.update(selected.pop('profiles')[profile_id])
        files = dict(observed['toolchain_files_sha256'])
        for name, pin in data['toolchain_files_sha256'].items():
            need(name not in files or files[name] == pin, 'supplemental runtime inventory conflict')
            files[name] = pin
        links = dict(observed['toolchain_symlinks'])
        for name, target in data['toolchain_symlinks'].items():
            need(name not in links or links[name] == target, 'supplemental symlink state conflict')
            links[name] = target
        selected.update(profile_id=profile_id, profile_source=F16_PROFILE, profile_sha256=F16_PROFILE_SHA,
            toolchain_files_sha256=files, toolchain_symlinks=links, protected_sha256=protected['protected_sha256'])
        selected['physical_locks'] = [data['physical_lock_pattern'].format(package=package, core=core)
            for package, core in [data['topology'][str(cpu)] for cpu in selected['cpus']]]
        selected['pair_lock'] = str(Path(data['base']) / ('.static-pair-' + '-'.join(map(str, selected['cpus'])) + '.lock'))
    runtime = load('tools/native_runtime_toolchain_v1.py', RUNTIME_SHA)
    return runtime.configure(selected)


def guard_protected(selected):
    if 'protected_deadline_epoch' not in selected:
        return
    need(time.time() + 3715 < selected['protected_deadline_drain_epoch'] < selected['protected_deadline_epoch'], 'finite job plus grace before earlier F16 drain/deadline')
    for name, pin in selected['protected_sha256'].items():
        need(sha(name) == pin, 'protected F16 state drift; never modify it')
    for command, expected in (('is-active', b'active\n'), ('is-enabled', b'enabled\n')):
        result = subprocess.run(['/usr/bin/systemctl', command, 'gfn16-deadline.timer'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
        need(result.returncode == 0 and result.stdout == expected and result.stderr == b'', 'protected F16 timer active/enabled')


def guard_toolchain(selected):
    guard_protected(selected)
    return load('tools/native_runtime_toolchain_v1.py', RUNTIME_SHA).verify_files(selected)


def adapted_source(raw, selected):
    previous = v2()
    text = previous.adapted_source(raw, selected)
    changes = [('SELF = ' + repr(previous.SELF), 'SELF = ' + repr(SELF)),
        ('    return paths', "    global RUNTIME_CHECK\n    RUNTIME_CHECK = guard_toolchain(profile)\n    return paths"),
        ("PYTHONPATH=str(root.parent) + ':' + str(root)", "PYTHONPATH=':'.join([str(root.parent), str(root), *profile['python_module_paths']])"),
        ('tool_sha256={str(p): sha(p) for p in toolpaths.values()}, limits=limits,',
         'tool_sha256={str(p): sha(p) for p in toolpaths.values()}, limits=limits, runtime_dependency_admission=RUNTIME_CHECK,'),
        ('guard(); begin = time.monotonic(); usage_before =', 'guard_protected(profile); guard(); begin = time.monotonic(); usage_before =')]
    for old, new in changes:
        need(text.count(old) == 1, 'unique F16 static runtime anchor')
        text = text.replace(old, new, 1)
    return text


def parent(profile_id):
    previous = v2()
    static = previous.static_module()
    selected = profile(profile_id)
    base = static.load('tools/native_shared_v1.py')
    module = types.ModuleType('_static_host_v3_parent')
    module.__file__ = str(Path(__file__).resolve())
    module.__dict__.update(PROFILE_ID=profile_id, admit_lint=base.admit_lint,
        validate_output=base.validate_output, check_scratch_quota=static.check_scratch_quota,
        guard_toolchain=guard_toolchain, guard_protected=guard_protected, RUNTIME_CHECK=None)
    raw = static.pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
    exec(compile(adapted_source(raw, selected), str(HERE / 'native_static_v2.py') + '[observed-F16-interop]', 'exec'), module.__dict__)
    module.PROFILES = {selected['host']: selected}
    return module


def execution_limits(selected):
    return v2().execution_limits(selected)


def execute_with_parent(parent_factory, closed_pins, manifest_path, pin, out):
    """Policy wrappers retain fit-slot locks/FDs instead of bypassing them."""
    need(callable(parent_factory) and all(closed_pins.get(name) == digest for name, digest in PINS.items()), 'closed additive execution policy')
    static = static_module()
    need(static.sha(manifest_path) == pin, 'manifest pin before fit-slot acquisition')
    manifest = json.loads(Path(manifest_path).read_text())
    selected = profile(manifest['cpu_profile'])
    base = static.load('tools/native_shared_v1.py')
    with ExitStack() as stack:
        shared_fds = tuple(stack.enter_context(base.lock(Path(name), True)) for name in selected['shared_locks'])
        def with_shared_fds(profile_id):
            module = parent_factory(profile_id)
            original = module.execute
            def run(path, digest, output):
                module.LEASE_FDS += shared_fds
                return original(path, digest, output)
            module.execute = run
            return module
        namespace = dict(static.execute.__globals__, profile=profile, parent=with_shared_fds, PINS=closed_pins)
        function = types.FunctionType(static.execute.__code__, namespace, static.execute.__name__)
        return function(Path(manifest_path), pin, Path(out))


def execute(manifest_path, pin, out):
    return execute_with_parent(parent, PINS, manifest_path, pin, out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.manifest, args.manifest_sha256, args.output), indent=2))
