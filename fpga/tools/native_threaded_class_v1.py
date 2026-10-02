"""S4 P3 matched AW16 thread pilot over immutable admitted class/static hosts.

One/two model threads fit the existing two-physical-core profiles. All original
source/tool/physical/fit/compile/quota/deadline guards remain inherited. Compiler
concurrency stays j2. Linux wait4 records each child's CPU and peak RSS. No new
host, allocator, cache reuse, or higher-thread production admission is provided.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
SELF = 'tools/native_threaded_class_v1.py'
CLASS_SHA = 'ff1e738729c91758073b03739933172a5e578531d4bffc22d28c109c7384e505'
RUNTIME_SHA = '900b4b7598a6f405ec87ceaa1e82dd391e02c18c4ddbb36f64fa93b5ac613be2'
IDENTITY_SHA = 'd59fcd49049107ceeb7b3f832a7da9b664363fb3a4b94664ec236502448a1329'
USAGE_SHA = '207d5aefbc6ff435ed79dcc2796a731ae944991587a04ccce6eaeac8ca9eaf19'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def load(name, digest):
    path = HERE / name
    with path.open('rb') as stream:
        need(hashlib.file_digest(stream, 'sha256').hexdigest() == digest, 'exact threaded class dependency: ' + name)
    spec = importlib.util.spec_from_file_location('_threaded_class_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def policy():
    return load('native_class_v3.py', CLASS_SHA)


def source_policy():
    value = policy().policy.policy
    need(value.SELF == 'tools/native_class_v3.py' and value.host.SELF == 'tools/native_static_v4.py', 'exact nested class/static source adapter')
    return value


def dependencies():
    return dict(policy().PINS, **{'tools/native_class_v3.py': CLASS_SHA,
        'tools/native_thread_config_v1.py': RUNTIME_SHA, 'tools/build_identity_v2.py': IDENTITY_SHA,
        'tools/native_child_usage_v1.py': USAGE_SHA})


PINS = dependencies()
SELECTIONS = policy().SELECTIONS


def profile(profile_id):
    value = policy().profile(profile_id)
    value['model_threads'] = 'manifest_exact_runtime_threads'
    value['runtime_allocation'] = dict(cpus=value['cpus'],
        physical_cores=[value['topology'][str(cpu)] for cpu in value['cpus']],
        cpu_quota_percent=value['cpu_quota_percent'], compile_workers=2, memory_bytes=value['memory_bytes'])
    return value


def validate_threaded(manifest):
    runtime = load('native_thread_config_v1.py', RUNTIME_SHA)
    count = runtime.validate_build(manifest['build'], manifest['probe']['expected_json'])
    need(count in (1, 2) and manifest['build']['parameters'].get('AW') == 16, 'pilot AW16 one/two threads only')
    return count


def adapted_source(raw, selected):
    parent = source_policy()
    text = parent.adapted_source(raw, selected)
    single = ("    require(manifest['probe']['expected_json'] == dict(context_threads=1, model_threads=1, expected_threads=1)\n"
              "            and all(type(v) is int for v in manifest['probe']['expected_json'].values()), 'single-thread runtime probe contract')")
    changes = [
        ('SELF = ' + repr(parent.SELF), 'SELF = ' + repr(SELF)),
        (single, "    validate_threaded(manifest)\n    runtime.validate_allocation(profile['runtime_allocation'], build['runtime_threads'])"),
        ("'--cc', '--exe', '--build', '-Wall', '-Wno-fatal', '-j', '2', '--threads', '1',",
         "'--cc', '--exe', '--build', '-Wall', '-Wno-fatal', '-j', '2', '--threads', str(config['runtime_threads']),"),
        ("'--lint-only', '-Wall', '-Wno-fatal', '--threads', '1',",
         "'--lint-only', '-Wall', '-Wno-fatal', '--threads', str(config['runtime_threads']),"),
        ('compile_workers=2, model_threads=1,',
         "compile_workers=2, model_threads=manifest['build']['runtime_threads'],\n"
         "                  context_threads=manifest['build']['runtime_threads'], exact_build_identity=identity.build_identity(manifest, profile),"),
        ('child = subprocess.Popen(', 'child = MeasuredPopen('),
        ('returncode=child.returncode,\n                                    seconds=',
         'returncode=child.returncode, native_child_usage=child.resource_receipt(),\n                                    seconds=')]
    for old, new in changes:
        need(text.count(old) == 1, 'unique threaded-class source anchor: ' + old[:60])
        text = text.replace(old, new, 1)
    return text


def parent(profile_id):
    inherited = source_policy()
    selected = profile(profile_id)
    host = inherited.host
    static = host.static_module()
    base = static.load('tools/native_shared_v1.py')
    module = types.ModuleType('_threaded_class_native_parent')
    module.__file__ = str(Path(__file__).resolve())
    module.__dict__.update(PROFILE_ID=profile_id, classify=inherited.classes.classify,
        LintClassError=inherited.classes.LintClassError, validate_output=base.validate_output,
        check_scratch_quota=static.check_scratch_quota, guard_toolchain=host.guard_toolchain,
        guard_protected=host.guard_protected, RUNTIME_CHECK=None,
        runtime=load('native_thread_config_v1.py', RUNTIME_SHA), identity=load('build_identity_v2.py', IDENTITY_SHA),
        MeasuredPopen=load('native_child_usage_v1.py', USAGE_SHA).MeasuredPopen, validate_threaded=validate_threaded)
    raw = static.pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
    exec(compile(adapted_source(raw, selected), str(HERE / 'native_class_v3.py') + '[matched-thread-pilot]', 'exec'), module.__dict__)
    module.PROFILES = {selected['host']: selected}
    return module


def execution_limits(selected):
    return policy().execution_limits(selected)


def execute(manifest_path, pin, out):
    host = source_policy().host
    def threaded_static():
        module = host.static_module()
        namespace = dict(module.execute.__globals__, validate_serial=validate_threaded)
        module.execute = types.FunctionType(module.execute.__code__, namespace, module.execute.__name__)
        return module
    # Retain the exact host's outer fit-slot lock frame and FD augmentation.
    namespace = dict(host.execute_with_parent.__globals__, profile=profile, PINS=PINS, static_module=threaded_static)
    function = types.FunctionType(host.execute_with_parent.__code__, namespace, host.execute_with_parent.__name__)
    return function(parent, PINS, manifest_path, pin, out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.manifest, args.manifest_sha256, args.output), indent=2))
