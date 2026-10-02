"""Additive static host/tool-path binding; frozen serial-v1 remains unchanged.

Consumes actual F32 toolchain evidence, never borrowed GCP fingerprints.
One model thread and two compiler workers on each fixed physical pair;
original exclusive host compile lock and own-UID durable quota guard retained.
Warning-class policy is an independently owned shared wrapper, not this file.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
SELF = 'tools/native_static_v2.py'
STATIC_SHA = '5b1b0f0dc584df8d6887235a9ddf1610f4956823aa84131438de7b8054f1e0ab'
F32_PROFILE = 'cloud/azure-f32-static-profiles-v1.json'
F32_PROFILE_SHA = '7919c768a8f39cbf98fdaf687ee562ef152a4de922b0abe7ce10de44972c88a2'
F32_RECEIPT = 'results/throughput-20260929/azure-sim-f32-admission-v1/toolchain-terminal-v1.json'
F32_RECEIPT_SHA = '07a3b872a4446a617bcd29f6d6ef96666c4df207f00d54c2c1d4fecde0ac54e2'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def static_module():
    path = HERE / 'native_static_v1.py'
    need(sha(path) == STATIC_SHA, 'frozen serial static identity')
    spec = importlib.util.spec_from_file_location('_static_v2_parent', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def descriptor():
    need(sha(HERE.parent / F32_PROFILE) == F32_PROFILE_SHA, 'actual F32 profile pin')
    need(sha(HERE.parent / F32_RECEIPT) == F32_RECEIPT_SHA, 'actual F32 toolchain capture pin')
    data = json.loads((HERE.parent / F32_PROFILE).read_text())
    receipt = json.loads((HERE.parent / F32_RECEIPT).read_text())
    need(data['schema'] == 'gfn16-static-native-host-v2'
         and data['toolchain_receipt'] == F32_RECEIPT and data['toolchain_receipt_sha256'] == F32_RECEIPT_SHA,
         'F32 descriptor/evidence correspondence')
    need(receipt['schema'] == 'azure-sim-f32-toolchain-terminal-v1'
         and receipt['status'] == 'PASS_native_tool_setup_not_RTL_admission' and receipt['exit_status'] == 0,
         'observed successful tool setup, not RTL validation')
    need(data['host'] == receipt['vm'] and data['user'] == receipt['user'] and data['uid'] == receipt['uid']
         and data['base'] == receipt['base'] and data['scratch_base'] == receipt['scratch']['path'],
         'exact F32 placement/own user')
    need(data['static_lanes'] == 8 and data['memory_bytes_per_lane'] == 4 * (1 << 30)
         and data['cpu_quota_percent'] == 200 and data['compile_workers'] == 2 and data['model_threads'] == 1,
         'fixed eight serial pair ceilings')
    need(data['static_lanes'] * data['memory_bytes_per_lane'] + data['minimum_host_available_bytes']
         < data['observed_total_memory_bytes'], 'aggregate fixed lane RAM plus host reserve')
    need(data['scratch_reservation_bytes'] == 4 * (1 << 30) and data['scratch_floor_bytes'] == 10 * (1 << 30), 'durable reservation/floor')
    pairs = list(data['profiles'].values())
    need(pairs == receipt['proposed_static']['pairs'] and len(pairs) == data['static_lanes'], 'actual proposed static pair correspondence')
    need(len({tuple(receipt['topology'][str(cpu)]) for pair in pairs for cpu in pair}) == 2 * len(pairs), 'static pairs physically disjoint')
    return data, receipt


def dependencies():
    return dict(static_module().PINS, **{'tools/native_static_v1.py': STATIC_SHA,
        F32_PROFILE: F32_PROFILE_SHA, F32_RECEIPT: F32_RECEIPT_SHA})


PINS = dependencies()
SELECTIONS = dict(static_module().SELECTIONS, **{name: name for name in descriptor()[0]['profiles']})


def profile(profile_id):
    static = static_module()
    if profile_id in static.SELECTIONS:
        selected = static.profile(profile_id)
        selected.update(compiler_path='/usr/bin/x86_64-linux-gnu-g++-15', compiler_alias='/usr/bin/g++',
                        python_path='/usr/bin/python3.14', make_path='/usr/bin/make', taskset_path='/usr/bin/taskset',
                        cc_path='/usr/bin/gcc')
    else:
        data, receipt = descriptor()
        need(profile_id in data['profiles'], 'approved observed static host profile')
        selected = copy.deepcopy(data)
        selected.pop('profiles')
        selected.update(profile_id=profile_id, cpus=data['profiles'][profile_id],
            memory_bytes=data['memory_bytes_per_lane'], topology=receipt['topology'],
            verilator_dir=receipt['verilator_dir'], hashes=receipt['hashes'],
            compiler_path=receipt['compiler_path'], compiler_alias=receipt['compiler_alias'], python_path=receipt['python_path'],
            profile_source=F32_PROFILE, profile_sha256=F32_PROFILE_SHA)
        selected['physical_locks'] = [data['physical_lock_pattern'].format(package=package, core=core)
            for package, core in [receipt['topology'][str(cpu)] for cpu in selected['cpus']]]
        selected['pair_lock'] = str(Path(selected['base']) / ('.static-pair-' + '-'.join(map(str, selected['cpus'])) + '.lock'))
    selected['env_path'] = selected['verilator_dir'] + ':/usr/bin:/bin'
    selected['tool_paths'] = dict(verilator=selected['verilator_dir'] + '/verilator',
        verilator_bin=selected['verilator_dir'] + '/verilator_bin', compiler=selected['compiler_path'],
        compiler_alias=selected['compiler_alias'], python=selected['python_path'], make=selected['make_path'], taskset=selected['taskset_path'])
    return selected


def adapted_source(raw, selected):
    static = static_module()
    text = static.adapted_source(raw, selected)
    changes = [
        ('SELF = ' + repr(static.SELF), 'SELF = ' + repr(SELF)),
        ("compiler=Path('/usr/bin/x86_64-linux-gnu-g++-15')", "compiler=Path(profile['compiler_path'])"),
        ("python=Path('/usr/bin/python3.14')", "python=Path(profile['python_path'])"),
        ("make=Path('/usr/bin/make')", "make=Path(profile['make_path'])"),
        ("taskset=Path('/usr/bin/taskset')", "taskset=Path(profile['taskset_path'])"),
        ("Path('/usr/bin/g++')", "Path(profile['compiler_alias'])"),
        ("PATH=profile['verilator_dir'] + ':/usr/bin:/bin'", "PATH=profile['env_path']"),
        ("CXX='/usr/bin/x86_64-linux-gnu-g++-15'", "CXX=profile['compiler_path']"),
        ("CC='/usr/bin/gcc'", "CC=profile['cc_path']"),
        (f"host_memory_floor_bytes={selected['memory_bytes']}", "host_memory_floor_bytes=profile['minimum_host_available_bytes']"),
    ]
    for old, new in changes:
        need(text.count(old) == 1, 'unique static tool-path anchor: ' + old)
        text = text.replace(old, new, 1)
    return text


def parent(profile_id):
    static = static_module()
    selected = profile(profile_id)
    base = static.load('tools/native_shared_v1.py')
    module = types.ModuleType('_static_host_v2_parent')
    module.__file__ = str(Path(__file__).resolve())
    module.__dict__.update(PROFILE_ID=profile_id, admit_lint=base.admit_lint,
                           validate_output=base.validate_output, check_scratch_quota=static.check_scratch_quota)
    exec(compile(adapted_source(static.pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes(), selected),
                 str(HERE / 'native_static_v1.py') + '[observed-host-tools]', 'exec'), module.__dict__)
    module.PROFILES = {selected['host']: selected}
    return module


def execution_limits(selected):
    return static_module().execution_limits(selected)


def execute(manifest_path, pin, out):
    static = static_module()
    namespace = dict(static.execute.__globals__, profile=profile, parent=parent, PINS=dependencies())
    function = types.FunctionType(static.execute.__code__, namespace, static.execute.__name__)
    return function(manifest_path, pin, out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.manifest, args.manifest_sha256, args.output), indent=2))
