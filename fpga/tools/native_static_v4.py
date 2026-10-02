"""r49 resized burst binding over immutable static-v3/v2 predecessors.

Only new observed hardware/profile data and its read-only deadline guard change.
The 32-core profile remains intact and cannot admit the new 16-core topology.
Eight serial pairs retain model1, j2, 4GiB, existing locks and quota checks.
Strict accrued-cost/rate admission is independently enforced by meter-v3.
"""
import argparse
import copy
import json
from pathlib import Path
import time
import types

from importlib import util
import hashlib

HERE = Path(__file__).resolve().parent
SELF = 'tools/native_static_v4.py'
PREVIOUS_SHA = '3fcd90e5a92ec332f350aa3be31eab16f106666cae42275cc2cce625960e0ac9'
PROFILE = 'cloud/azure-burst16-static-profiles-v1.json'
PROFILE_SHA = 'eef2a816c7fc6ae5e53919b24b2bb135a16808d7ef7ccb7341395b0c030b596d'
OBSERVATION = 'results/throughput-20260929/azure-sim-resize-r49-v1/toolchain-observation-v1.json'
OBSERVATION_SHA = '5f79de9b9387eb7ae62fa1d644290aa7fa46d6001972686987a0707b294f6a8e'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def previous():
    path = HERE / 'native_static_v3.py'
    need(sha(path) == PREVIOUS_SHA, 'immutable observed static-v3 source')
    spec = util.spec_from_file_location('_resized_static_parent', path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def static_module():
    return previous().static_module()


def descriptor():
    need(sha(HERE.parent / PROFILE) == PROFILE_SHA and sha(HERE.parent / OBSERVATION) == OBSERVATION_SHA, 'exact r49 resize data/capture')
    data = json.loads((HERE.parent / PROFILE).read_text())
    observed = json.loads((HERE.parent / OBSERVATION).read_text())
    need(data['schema'] == 'gfn16-resized-burst-static-host-v1'
         and observed['schema'] == 'azure-native-toolchain-observation-v2'
         and data['toolchain_observation_path'] == OBSERVATION
         and data['toolchain_observation_sha256'] == OBSERVATION_SHA, 'resized host schema/capture correspondence')
    for key in ('host', 'user', 'uid', 'logical_cpus', 'physical_cores', 'observed_total_memory_bytes'):
        need(data[key] == observed[key], 'observed resized host field: ' + key)
    need(data['hardware_sku'] == 'Standard_F16as_v7' and data['logical_cpus'] == data['physical_cores'] == 16
         and observed['topology'] == {str(cpu): [0, cpu] for cpu in range(16)}, 'sixteen observed physical cores, no SMT inflation')
    need(data['burst_deadline_epoch'] == observed['protected_deadline_epoch'] == 1791162766, 'unchanged burst deadline')
    need(data['static_lanes'] == 8 and data['memory_bytes_per_lane'] == 4 << 30
         and data['minimum_host_available_bytes'] == 8 << 30 and data['compile_workers'] == 2
         and data['model_threads'] == 1 and data['cpu_quota_percent'] == 200, 'eight unchanged serial-pair ceilings')
    cpus = [cpu for pair in data['profiles'].values() for cpu in pair]
    need(cpus == list(range(16)) and all(len(pair) == 2 for pair in data['profiles'].values()), 'eight disjoint observed physical pairs')
    need(data['static_lanes'] * data['memory_bytes_per_lane'] + data['minimum_host_available_bytes']
         < observed['observed_total_memory_bytes'], 'aggregate pair RAM plus host floor')
    need(data['scratch_reservation_bytes'] == 4 << 30 and data['scratch_floor_bytes'] == 10 << 30, 'retained conservative scratch quota policy')
    old = previous().profile('azure-f32-static01-v1')
    need(observed['hashes'] == old['hashes'] and observed['compiler_alias_sha256'] == old['hashes']['compiler'], 'same-disk tool fingerprints unchanged by resize')
    return data, observed


def dependencies():
    return dict(previous().dependencies(), **{'tools/native_static_v3.py': PREVIOUS_SHA,
                                             PROFILE: PROFILE_SHA, OBSERVATION: OBSERVATION_SHA})


PINS = dependencies()
SELECTIONS = dict(previous().SELECTIONS, **{name: name for name in descriptor()[0]['profiles']})


def profile(profile_id):
    prior = previous()
    if profile_id in prior.SELECTIONS:
        return prior.profile(profile_id)
    data, observed = descriptor()
    need(profile_id in data['profiles'], 'approved resized burst static pair')
    selected = copy.deepcopy(data)
    selected.pop('profiles')
    selected.update(profile_id=profile_id, cpus=data['profiles'][profile_id], shared_locks=[],
        memory_bytes=data['memory_bytes_per_lane'], topology=observed['topology'], hashes=observed['hashes'],
        compiler_path=observed['paths']['compiler'], compiler_alias=observed['paths']['compiler_alias'],
        python_path=observed['paths']['python'], verilator_dir=str(Path(observed['paths']['verilator']).parent),
        profile_source=PROFILE, profile_sha256=PROFILE_SHA,
        toolchain_files_sha256=observed['toolchain_files_sha256'], toolchain_symlinks=observed['toolchain_symlinks'])
    need(selected['make_path'] == observed['paths']['make'] and selected['taskset_path'] == observed['paths']['taskset'], 'observed standard tool paths')
    selected['env_path'] = selected['verilator_dir'] + ':' + str(Path(selected['python_path']).parent) + ':/usr/bin:/bin'
    selected['physical_locks'] = [selected['physical_lock_pattern'].format(package=package, core=core)
        for package, core in [selected['topology'][str(cpu)] for cpu in selected['cpus']]]
    selected['pair_lock'] = str(Path(selected['base']) / ('.static-pair-' + '-'.join(map(str, selected['cpus'])) + '.lock'))
    return prior.load('tools/native_runtime_toolchain_v1.py', prior.RUNTIME_SHA).configure(selected)


def guard_protected(selected):
    prior = previous()
    if 'burst_deadline_epoch' not in selected:
        return prior.guard_protected(selected)
    need(time.time() + 3715 < selected['burst_deadline_epoch'], 'bounded job and kill grace before unchanged burst deadline')
    for name, pin in selected['burst_protected_sha256'].items():
        need(sha(name) == pin, 'read-only resized burst guard/deadline identity')
    for command, expected in (('is-active', b'active\n'), ('is-enabled', b'enabled\n')):
        result = prior.subprocess.run(['/usr/bin/systemctl', command, selected['burst_timer']],
            stdout=prior.subprocess.PIPE, stderr=prior.subprocess.PIPE, timeout=10,
            env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
        need(result.returncode == 0 and result.stdout == expected and result.stderr == b'', 'resized burst timer active/enabled')


def guard_toolchain(selected):
    guard_protected(selected)
    prior = previous()
    return prior.load('tools/native_runtime_toolchain_v1.py', prior.RUNTIME_SHA).verify_files(selected)


def adapted_source(raw, selected):
    prior = previous()
    text = prior.adapted_source(raw, selected)
    old = 'SELF = ' + repr(prior.SELF)
    need(text.count(old) == 1, 'unique resized hardware source adapter')
    return text.replace(old, 'SELF = ' + repr(SELF), 1)


def parent(profile_id):
    prior = previous()
    selected = profile(profile_id)
    static = static_module()
    base = static.load('tools/native_shared_v1.py')
    module = types.ModuleType('_resized_serial_native_parent')
    module.__file__ = str(Path(__file__).resolve())
    module.__dict__.update(PROFILE_ID=profile_id, admit_lint=base.admit_lint, validate_output=base.validate_output,
        check_scratch_quota=static.check_scratch_quota, guard_toolchain=guard_toolchain,
        guard_protected=guard_protected, RUNTIME_CHECK=None)
    raw = static.pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
    exec(compile(adapted_source(raw, selected), str(HERE / 'native_static_v3.py') + '[r49-sixteen-core-hardware]', 'exec'), module.__dict__)
    module.PROFILES = {selected['host']: selected}
    return module


def execution_limits(selected):
    return previous().execution_limits(selected)


def execute_with_parent(parent_factory, closed_pins, manifest_path, pin, out):
    prior = previous()
    namespace = dict(prior.execute_with_parent.__globals__, profile=profile, PINS=PINS, static_module=static_module)
    function = types.FunctionType(prior.execute_with_parent.__code__, namespace, prior.execute_with_parent.__name__)
    return function(parent_factory, closed_pins, manifest_path, pin, out)


def execute(manifest_path, pin, out):
    return execute_with_parent(parent, PINS, manifest_path, pin, out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.manifest, args.manifest_sha256, args.output), indent=2))
