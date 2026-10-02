"""r38 class-gated serial execution over the frozen observed-host adapter.

All host, quota, source, process and compile-lock guards remain inherited.
Style diagnostics are retained, while defects/unknown classes fail closed in
both lint and the actual Verilator build. This is exploration, not promotion.
"""
import hashlib
import importlib.util
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
SELF = 'tools/native_class_v1.py'
HOST_SHA = '6bfe9e244e50da02f9d3b3b1f47b0b7273158fc0b640c4311352a818b1705f6f'
CLASS_SHA = '0f9b3cfd9a2723a8fb10f4b30614da253e04e3eab52e220241403fec8908d031'


def load(name, pin):
    path = HERE / name
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
        raise ValueError('exact class policy dependency: ' + name)
    spec = importlib.util.spec_from_file_location('_class_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load('native_static_v2.py', HOST_SHA)
classes = load('native_lint_classes_v1.py', CLASS_SHA)
PINS = dict(host.PINS, **{'tools/native_static_v2.py': HOST_SHA,
                        'tools/native_lint_classes_v1.py': CLASS_SHA})
SELECTIONS = host.SELECTIONS
profile = host.profile
execution_limits = host.execution_limits


def adapted_source(raw, selected):
    text = host.adapted_source(raw, selected)
    changes = [
        ('SELF = ' + repr(host.SELF), 'SELF = ' + repr(SELF)),
        ("'--cc', '--exe', '--build', '-j'", "'--cc', '--exe', '--build', '-Wall', '-Wno-fatal', '-j'"),
        ("'--lint-only', '-Wall', '--threads'", "'--lint-only', '-Wall', '-Wno-fatal', '--threads'"),
        ("if name == 'lint':\n            report['lint_admission'] = admit_lint(child.returncode, log.read_bytes(), error_log.read_bytes(), manifest, profile, root)\n            save()",
         "if name in ('lint', 'build'):\n            try:\n                report[name + '_admission'] = classify(child.returncode, log.read_bytes(), error_log.read_bytes(), manifest, root)\n            except LintClassError as error:\n                report[name + '_admission'] = error.receipt\n                save()\n                raise\n            save()")]
    for old, new in changes:
        if text.count(old) != 1:
            raise ValueError('unique class policy source anchor: ' + old)
        text = text.replace(old, new, 1)
    return text


def parent(profile_id):
    selected = profile(profile_id)
    static = host.static_module()
    base = static.load('tools/native_shared_v1.py')
    module = types.ModuleType('_class_native_parent')
    module.__file__ = str(Path(__file__).resolve())
    module.__dict__.update(PROFILE_ID=profile_id, classify=classes.classify,
        LintClassError=classes.LintClassError, validate_output=base.validate_output,
        check_scratch_quota=static.check_scratch_quota)
    exec(compile(adapted_source(static.pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes(), selected),
                 str(HERE / 'native_static_v2.py') + '[r38-class-policy]', 'exec'), module.__dict__)
    module.PROFILES = {selected['host']: selected}
    return module


def execute(manifest_path, pin, out):
    static = host.static_module()
    namespace = dict(static.execute.__globals__, profile=profile, parent=parent, PINS=PINS)
    return types.FunctionType(static.execute.__code__, namespace)(manifest_path, pin, out)
