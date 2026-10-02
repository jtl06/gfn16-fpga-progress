"""Single declared ordinal model3300s; all inherited guards/bounds unchanged."""
import hashlib
import importlib.util
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
SELF = 'tools/native_ordinal_class_v1.py'
BASE_SHA = '1a50703e0554575e323697a11d5bbf43778603f78b1c978406734d7678529516'
DURATION_SHA = 'b68a3984f581b4ae3170b1e48b62fc9d6214fe1e6bf47daf1bb30c96aa25c8d6'


def load(name, pin):
    path = HERE / name
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
        raise ValueError('exact ordinal dependency: ' + name)
    spec = importlib.util.spec_from_file_location('_ordinal_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load('native_class_v1.py', BASE_SHA)
duration = load('native_ordinal_duration_v1.py', DURATION_SHA)
PINS = dict(base.PINS, **{'tools/native_class_v1.py': BASE_SHA,
                         'tools/native_ordinal_duration_v1.py': DURATION_SHA})
SELECTIONS = {name: name for name in ('gcp-c4d-static01-v1', 'gcp-c4d-static23-v1')}
execution_limits = base.execution_limits


def profile(name):
    if name not in SELECTIONS:
        raise ValueError('ordinal existing GCP8GiB physical pairs only')
    return base.profile(name)


def adapted_source(raw, selected):
    text = base.adapted_source(raw, selected)
    changes = [
        ('SELF = ' + repr(base.SELF), 'SELF = ' + repr(SELF)),
        ('bounds=dict(command_seconds=1800, overall_seconds=3600, lock_wait_seconds=1800,',
         'duration_admission=ORDINAL_RECEIPT, bounds=dict(command_seconds=1800, model_command_seconds=3300, overall_seconds=3600, outer_seconds=3700, stop_grace_seconds=15, lock_wait_seconds=1800,'),
        ("guard(); begin = time.monotonic(); usage_before = resource.getrusage(resource.RUSAGE_CHILDREN); failure = None; log = out / (name + '.log')",
         "guard(); command_limit = ordinal_command_seconds(name, argv, expected, ORDINAL_RECEIPT); begin = time.monotonic(); usage_before = resource.getrusage(resource.RUSAGE_CHILDREN); failure = None; log = out / (name + '.log')"),
        ("time.monotonic()-begin < 1800, 'command timeout'",
         "time.monotonic()-begin < command_limit, 'command timeout'"),
    ]
    for old, new in changes:
        if text.count(old) != 1:
            raise ValueError('unique ordinal source anchor: ' + old)
        text = text.replace(old, new, 1)
    return text


def parent(name, receipt=None):
    selected = profile(name)
    original = base.parent(name)
    module = types.ModuleType('_ordinal_exact_parent')
    module.__dict__.update(original.__dict__, ORDINAL_RECEIPT=receipt,
                           ordinal_command_seconds=duration.command_seconds,
                           __file__=str(Path(__file__).resolve()))
    raw = base.host.static_module().pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
    # Execute directly in the final module namespace: profiles and live lease
    # descriptors must remain visible to all inherited generated functions.
    exec(compile(adapted_source(raw, selected), '[single ordinal3300]', 'exec'), module.__dict__)
    module.PROFILES = {selected['host']: selected}
    return module


def execute(manifest_path, pin, out):
    path = Path(manifest_path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != pin:
        raise ValueError('ordinal approved manifest identity')
    manifest = json.loads(path.read_text())
    selected = profile(manifest['cpu_profile'])
    receipt = duration.validate(manifest, Path(manifest['source_root']), selected['host'])
    static = base.host.static_module()
    namespace = dict(static.execute.__globals__, profile=profile,
                     parent=lambda name: parent(name, receipt), PINS=PINS)
    return types.FunctionType(static.execute.__code__, namespace)(path, pin, out)
