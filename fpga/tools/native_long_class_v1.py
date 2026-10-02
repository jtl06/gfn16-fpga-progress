"""Finite single-model duration extension; unchanged GCP pair/memory profiles."""
import hashlib
import importlib.util
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
SELF = 'tools/native_long_class_v1.py'
BASE_SHA = '13697e0cf18f4fddfc896b35d32e6fa26123639b304e5ae42ff99a03890a8fff'
DURATION_SHA = 'aed7092d33ddedf19405e8da4df4e4bc1b31e29d1054369dd2ef4805f8d89b2c'


def load(name, pin):
    path = HERE / name
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
        raise ValueError('exact long runtime dependency')
    spec = importlib.util.spec_from_file_location('_long_' + path.stem, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


base = load('native_class_gcp24_v1.py', BASE_SHA)
duration = load('native_long_duration_v1.py', DURATION_SHA)
PINS = dict(base.PINS, **{'tools/native_class_gcp24_v1.py': BASE_SHA,
                         'tools/native_long_duration_v1.py': DURATION_SHA})
SELECTIONS = {name: name for name in ('gcp-c4d-static01-v1', 'gcp-c4d-static23-v1',
                                     'gcp-c4d-static24g01-v1', 'gcp-c4d-static24g23-v1')}
execution_limits = base.execution_limits


def profile(name):
    if name not in SELECTIONS:
        raise ValueError('long duration admitted GCP profiles only')
    return base.profile(name)


def adapted_source(raw, selected):
    policy = base.policy.policy
    text = policy.adapted_source(raw, selected)
    changes = [('SELF = ' + repr(policy.SELF), 'SELF = ' + repr(SELF)),
               ('bounds=dict(command_seconds=1800, overall_seconds=3600, lock_wait_seconds=1800,',
                'duration_admission=LONG_RECEIPT, bounds=dict(command_seconds=10450, ancillary_command_seconds=1800, overall_seconds=10700, outer_seconds=10800, stop_grace_seconds=15, lock_wait_seconds=1800,'),
               ("time.monotonic() - started < 3600, 'overall timeout'",
                "time.monotonic() - started < 10700, 'overall timeout'"),
               ("time.monotonic()-begin < 1800, 'command timeout'",
                "time.monotonic()-begin < (10450 if name == LONG_RECEIPT['model_step'] else 1800), 'command timeout'")]
    for old, new in changes:
        if text.count(old) != 1:
            raise ValueError('unique finite duration source anchor: ' + old)
        text = text.replace(old, new, 1)
    return text


def parent(name, receipt=None):
    selected = profile(name)
    original = base.parent(name)
    namespace = dict(original.__dict__, LONG_RECEIPT=receipt)
    raw = base.policy.policy.host.static_module().pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
    exec(compile(adapted_source(raw, selected), '[measured finite long duration]', 'exec'), namespace)
    result = types.ModuleType('_long_parent'); result.__dict__.update(namespace)
    result.PROFILES = {selected['host']: selected}
    return result


def execute(manifest_path, pin, out):
    path = Path(manifest_path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != pin:
        raise ValueError('long manifest identity')
    manifest = json.loads(path.read_text()); selected = profile(manifest['cpu_profile'])
    receipt = duration.validate(manifest, Path(manifest['source_root']), selected['host'])
    return base.policy.policy.host.execute_with_parent(lambda name: parent(name, receipt), PINS, path, pin, out)
