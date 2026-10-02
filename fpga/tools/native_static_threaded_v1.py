"""Small matched AW16 thread pilot hook over exact static serial admission.

Candidates keep native_static_v1. This additive hook changes model/context
thread flags and build identity only; compiler concurrency stays two and the
original exclusive compile lock, static physical locks and quota guard stay.
It permits one/two threads on the admitted two-physical-core static pairs.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
SELF = 'tools/native_static_threaded_v1.py'
STATIC_SHA = '5b1b0f0dc584df8d6887235a9ddf1610f4956823aa84131438de7b8054f1e0ab'
RUNTIME_SHA = '900b4b7598a6f405ec87ceaa1e82dd391e02c18c4ddbb36f64fa93b5ac613be2'
IDENTITY_SHA = 'd59fcd49049107ceeb7b3f832a7da9b664363fb3a4b94664ec236502448a1329'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def load(name, digest):
    path = HERE / name
    with path.open('rb') as stream:
        need(hashlib.file_digest(stream, 'sha256').hexdigest() == digest, 'thread pilot exact helper: ' + name)
    spec = importlib.util.spec_from_file_location('_static_thread_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dependencies():
    static = load('native_static_v1.py', STATIC_SHA)
    return dict(static.PINS, **{
        'tools/native_static_v1.py': STATIC_SHA,
        'tools/native_thread_config_v1.py': RUNTIME_SHA,
        'tools/build_identity_v2.py': IDENTITY_SHA})


# Same selector/closed-dependency interface as the serial adapter, for a
# generic finite-package binding. The serial host profile remains authoritative.
PINS = dependencies()
SELECTIONS = load('native_static_v1.py', STATIC_SHA).SELECTIONS


def profile(profile_id):
    static = load('native_static_v1.py', STATIC_SHA)
    selected = static.profile(profile_id)
    selected['model_threads'] = 'manifest_exact_runtime_threads'
    selected['runtime_allocation'] = dict(cpus=selected['cpus'],
        physical_cores=[selected['topology'][str(cpu)] for cpu in selected['cpus']],
        cpu_quota_percent=200, compile_workers=2, memory_bytes=selected['memory_bytes'])
    selected['tool_paths'] = dict(verilator=selected['verilator_dir'] + '/verilator',
        verilator_bin=selected['verilator_dir'] + '/verilator_bin', compiler='/usr/bin/x86_64-linux-gnu-g++-15',
        compiler_alias='/usr/bin/g++', python='/usr/bin/python3.14', make='/usr/bin/make', taskset='/usr/bin/taskset')
    return selected


def validate_threaded(manifest):
    runtime = load('native_thread_config_v1.py', RUNTIME_SHA)
    count = runtime.validate_build(manifest['build'], manifest['probe']['expected_json'])
    need(count in (1, 2), 'pilot only one/two threads on two physical cores')
    need(manifest['build']['parameters'].get('AW') == 16, 'current full-size AW16 pilot only')


def lint_identity(manifest, selected):
    static = load('native_static_v1.py', STATIC_SHA)
    base = static.load('tools/native_shared_v1.py')
    value = base.lint_identity(manifest, selected)
    value['lint_flags'][-1] = str(manifest['build']['runtime_threads'])
    return value


def adapted_source(raw, selected):
    static = load('native_static_v1.py', STATIC_SHA)
    text = static.adapted_source(raw, selected)
    single = ("    require(manifest['probe']['expected_json'] == dict(context_threads=1, model_threads=1, expected_threads=1)\n"
              "            and all(type(v) is int for v in manifest['probe']['expected_json'].values()), 'single-thread runtime probe contract')")
    changes = [
        ('SELF = ' + repr(static.SELF), 'SELF = ' + repr(SELF)),
        (single, "    validate_threaded(manifest)\n    runtime.validate_allocation(profile['runtime_allocation'], build['runtime_threads'])"),
        ("'--cc', '--exe', '--build', '-j', '2', '--threads', '1',",
         "'--cc', '--exe', '--build', '-j', '2', '--threads', str(config['runtime_threads']),"),
        ("'--lint-only', '-Wall', '--threads', '1',",
         "'--lint-only', '-Wall', '--threads', str(config['runtime_threads']),"),
        ('compile_workers=2, model_threads=1,',
         "compile_workers=2, model_threads=manifest['build']['runtime_threads'],\n"
         "                  context_threads=manifest['build']['runtime_threads'],\n"
         "                  exact_build_identity=identity.build_identity(manifest, profile),")]
    for old, new in changes:
        need(text.count(old) == 1, 'unique matched thread source anchor')
        text = text.replace(old, new, 1)
    return text


def parent(profile_id):
    static = load('native_static_v1.py', STATIC_SHA)
    selected = profile(profile_id)
    base = static.load('tools/native_shared_v1.py')
    runtime = load('native_thread_config_v1.py', RUNTIME_SHA)
    identity = load('build_identity_v2.py', IDENTITY_SHA)
    namespace = dict(base.admit_lint.__globals__, lint_identity=lint_identity)
    admit = types.FunctionType(base.admit_lint.__code__, namespace, base.admit_lint.__name__)
    module = types.ModuleType('_static_matched_thread_parent')
    module.__file__ = str(Path(__file__).resolve())
    module.__dict__.update(PROFILE_ID=profile_id, runtime=runtime, identity=identity,
        validate_threaded=validate_threaded, admit_lint=admit, validate_output=base.validate_output,
        check_scratch_quota=static.check_scratch_quota)
    raw = static.pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
    exec(compile(adapted_source(raw, selected), str(HERE / 'native_static_v1.py') + '[matched-thread-hook]', 'exec'), module.__dict__)
    module.PROFILES = {selected['host']: selected}
    return module


def execution_limits(selected):
    return load('native_static_v1.py', STATIC_SHA).execution_limits(selected)


def execute(manifest_path, pin, out):
    static = load('native_static_v1.py', STATIC_SHA)
    # Reuse the entire pinned static execution/admission function, rather than
    # copy it into a threaded runner. Only explicit hook globals are changed.
    namespace = dict(static.execute.__globals__, profile=profile, parent=parent,
                     validate_serial=validate_threaded, PINS=dependencies())
    function = types.FunctionType(static.execute.__code__, namespace, static.execute.__name__)
    return function(manifest_path, pin, out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.manifest, args.manifest_sha256, args.output), indent=2))
