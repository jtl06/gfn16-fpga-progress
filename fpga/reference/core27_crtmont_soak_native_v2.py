"""Soak candidate adapter for the frozen serial-v1 shared worker.

Preserves the frozen v1 oracle/harness. A pinned auxiliary runtime descriptor is
candidate data: validate its entire interpreter/module/library/wheel inventory
before adding the isolated import path. No shared launcher/profile/lease upgrade.
"""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import shutil
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/core27_crtmont_soak_native_v2.py'
BASE = 'reference/core27_crtmont_soak_v1.py'
BASE_SHA = '8075e2033a01b09b9bbc344b72f23df4ebbc90b8489caadfbd0546e6f3bcfe3a'
INSTALLER = 'tools/native_gmpy2_runtime_v1.py'
INSTALLER_SHA = '56cf38c3dd18279e68309e98bf224bde97a95e776660c9ff5b91c3178a258d1c'
WHEEL_SHA = '8749196c8bcd51612d989f5e509ea77d5c97c40b57eda9a863938facbe2b9eab'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def base():
    need(sha(ROOT/BASE) == BASE_SHA, 'SOAK_FROZEN_V1_SOURCE')
    spec = importlib.util.spec_from_file_location('_soak_frozen_v1', ROOT/BASE)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def regular_inventory(root, pins):
    root = Path(root)
    need(root.is_absolute() and root.resolve() == root and root.is_dir() and not root.is_symlink(), 'SOAK_RUNTIME_ROOT')
    actual = set()
    for path in root.rglob('*'):
        need(not path.is_symlink(), 'SOAK_RUNTIME_SYMLINK')
        if path.is_file():
            need(path.stat().st_nlink == 1, 'SOAK_RUNTIME_HARDLINK')
            actual.add(str(path))
    inside = {name for name in pins if Path(name).is_relative_to(root)}
    need(actual == inside and inside, 'SOAK_RUNTIME_EXACT_CLOSURE')
    for name in inside:
        need(sha(name) == pins[name], 'SOAK_RUNTIME_FILE_DRIFT')
    return inside


def admit_runtime(text):
    need(platform.system() == 'Linux', 'SOAK_NATIVE_REFERENCE_LINUX')
    runtime = json.loads(text)
    need(runtime['schema'] == 'native-python-module-runtime-v1'
        and runtime['status'] == 'installed_dependency_requires_shared_profile_admission'
        and runtime['package'] == 'gmpy2' and runtime['package_version'] == '2.3.1', 'SOAK_RUNTIME_DESCRIPTOR')
    need(runtime['host'] == platform.node() and runtime['python_path'] == str(Path(sys.executable).resolve())
        and runtime['python_sha256'] == sha(Path(sys.executable).resolve()), 'SOAK_RUNTIME_HOST_INTERPRETER')
    need(type(runtime['python_module_paths']) is list and len(runtime['python_module_paths']) == 1, 'SOAK_ONE_EXACT_IMPORT_ROOT')
    root = Path(runtime['python_module_paths'][0])
    need(root.name == 'gmpy2-2.3.1-v1' and root.parent.name == 'runtime', 'SOAK_ISOLATED_RUNTIME_PLACEMENT')
    pins = runtime['toolchain_files_sha256']
    inside = regular_inventory(root, pins)
    wheel = root.parent/(root.name+'.whl')
    need(set(pins) == inside | {str(wheel)} and not wheel.is_symlink() and wheel.stat().st_nlink == 1
        and pins[str(wheel)] == sha(wheel) == WHEEL_SHA, 'SOAK_EXACT_ORIGINAL_WHEEL')
    origin = json.loads((root/'wheel-origin.json').read_text())
    need(origin == runtime['origin'] and origin['installer_sha256'] == INSTALLER_SHA
        and origin['wheel_sha256'] == WHEEL_SHA and origin['no_system_or_user_site_mutation'] is True,
        'SOAK_RUNTIME_ORIGIN_BINDING')
    need(str(root/'gmpy2/__init__.py') in pins and any(name.endswith('.so') for name in pins), 'SOAK_NATIVE_MODULE_CLOSURE')
    sys.path.insert(0, str(root))
    import gmpy2
    need(gmpy2.version() == runtime['package_version'] and gmpy2.mp_version() == runtime['gmp_version']
        and str(Path(gmpy2.__file__)) == runtime['import_origin'], 'SOAK_EXACT_GMPY2_IMPORT')
    for name, module in sys.modules.items():
        if name == 'gmpy2' or name.startswith('gmpy2.'):
            path = getattr(module, '__file__', None)
            if path:
                need(path in pins and sha(path) == pins[path], 'SOAK_LOADED_GMPY2_ORIGIN')
    return dict(status='passed_exact_auxiliary_reference_runtime', files=len(pins),
        runtime_manifest_sha256=hashlib.sha256(text.encode()).hexdigest(),
        python_sha256=runtime['python_sha256'], import_root=str(root), package_version=gmpy2.version())


def validate(stdout, stderr, returncode, config, assets):
    need(set(assets) == {'oracle', 'runtime'}, 'SOAK_SERIAL_V1_VALIDATOR_ASSETS')
    admitted = admit_runtime(assets['runtime'])
    result = base().validate(stdout, stderr, returncode, config, {'oracle':assets['oracle']})
    result['auxiliary_reference_runtime'] = admitted
    return result


def dump(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')


def prepare_reference_source(out, runtime_file):
    """Portable project-only mirror for Linux oracle generation and staging."""
    module = base()
    need(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    out, runtime_file = Path(out).resolve(), Path(runtime_file).resolve()
    need(not out.exists(), 'SOAK_FRESH_REFERENCE_CAPTURE')
    order, pins = module.parent_sources()
    for name in (BASE, SELF, module.BENCH, module.HEADER, module.TEST, INSTALLER):
        pins[name] = sha(ROOT/name)
    need(pins[INSTALLER] == INSTALLER_SHA, 'SOAK_INSTALLER_SOURCE_BINDING')
    for name in ('manifest.json', 'probe.qsf', *('rtl/'+name for name in order)):
        relative = module.PARENT+'/'+name; pins[relative] = sha(ROOT/relative)
    pins[module.AUDIT] = sha(ROOT/module.AUDIT)
    source = out/'source/fpga'; source.mkdir(parents=True)
    for name, digest in pins.items():
        need(not (ROOT/name).is_symlink(), 'SOAK_CAPTURE_SOURCE_SYMLINK')
        target = source/name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target); need(sha(target) == digest, 'SOAK_REFERENCE_SOURCE_CAPTURE')
    target = source/'soak/runtime.json'; target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(runtime_file, target); pins['soak/runtime.json'] = sha(target)
    with (out/'reference-source.tar.gz').open('xb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as archive:
            for name in sorted(pins):
                content = (source/name).read_bytes()
                need(hashlib.sha256(content).hexdigest() == pins[name], 'SOAK_REFERENCE_ARCHIVE_DRIFT')
                entry = tarfile.TarInfo('source/fpga/'+name); entry.mode = 0o644; entry.mtime = 0; entry.size = len(content)
                archive.addfile(entry, io.BytesIO(content))
    receipt = dict(status='captured_reference_sources_not_executed', sources=pins,
        archive_sha256=sha(out/'reference-source.tar.gz'), archive_bytes=(out/'reference-source.tar.gz').stat().st_size,
        runtime_manifest_sha256=sha(runtime_file), frozen_v1_source_sha256=BASE_SHA,
        scope='Project sources/results and a pinned runtime descriptor only. No native binaries or credentials in this source archive.')
    dump(out/'reference-source.json', receipt)
    return receipt


def generate(out, runtime_file, plan):
    text = Path(runtime_file).read_text()
    admitted = admit_runtime(text)
    result = base().generate(out, plan, 'gmpy2')
    admitted.update(adapter_sha256=sha(ROOT/SELF), reference_generation_sha256=sha(Path(out)/'generation.json'))
    dump(Path(out)/'auxiliary-runtime-admission.json', admitted)
    return result


def stage(reference_dir, name, out, runtime_file, host, remote_root):
    module = base(); out = Path(out).resolve()
    need(not out.exists(), 'SOAK_FRESH_SERIAL_STAGE')
    out.mkdir(parents=True)
    original = out/'original-stage'
    module.stage_segment(reference_dir, name, original, host, remote_root, 1)
    manifest = json.loads((original/'manifest.json').read_text())
    source = out/'source/fpga'
    shutil.copytree(original/'source/fpga', source)
    for name in (SELF, INSTALLER):
        target = source/name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target); manifest['sources'][name] = sha(target)
    target = source/'soak/runtime.json'; shutil.copyfile(runtime_file, target)
    manifest['sources']['soak/runtime.json'] = sha(target)
    runtime = json.loads(target.read_text())
    need(runtime['host'] == host and runtime['package_version'] == '2.3.1', 'SOAK_STAGE_RUNTIME_HOST')
    admission = json.loads((Path(reference_dir)/'auxiliary-runtime-admission.json').read_text())
    need(admission['status'] == 'passed_exact_auxiliary_reference_runtime'
        and admission['runtime_manifest_sha256'] == sha(target), 'SOAK_STAGE_REFERENCE_RUNTIME_BINDING')
    # Frozen serial v1's model/context default is one. Threaded APIs are unused.
    manifest['build'].pop('runtime_threads')
    manifest['build']['cflags'].remove('-DGFN16_RUNTIME_THREADS=1')
    manifest.pop('model_threads')
    for step in manifest['steps']:
        step['validator']['source'] = SELF
        step['validator']['assets']['runtime'] = 'soak/runtime.json'
    manifest['auxiliary_reference_runtime_manifest_sha256'] = sha(target)
    dump(out/'manifest.json', manifest)
    result = dict(status='staged_serial_v1_candidate_not_dispatched', manifest_sha256=sha(out/'manifest.json'),
        source_root=str(source), sources=manifest['sources'], runtime_manifest_sha256=sha(target),
        original_stage_manifest_sha256=sha(original/'manifest.json'), shared_launcher_upgraded=False,
        model_threads=1, promotion_allowed=False)
    dump(out/'stage.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    capture = commands.add_parser('capture')
    capture.add_argument('--output', type=Path, required=True); capture.add_argument('--runtime-file', type=Path, required=True)
    identity = commands.add_parser('identity'); identity.add_argument('--runtime-file', type=Path, required=True)
    oracle = commands.add_parser('generate')
    oracle.add_argument('--runtime-file', type=Path, required=True); oracle.add_argument('--output', type=Path, required=True)
    oracle.add_argument('--aw', type=int, default=5); oracle.add_argument('--base', type=int, default=69)
    oracle.add_argument('--squares', type=int, default=4); oracle.add_argument('--chunk-squares', type=int, default=2)
    oracle.add_argument('--checkpoint-every', type=int, default=2); oracle.add_argument('--seed', type=int, default=20261001)
    staged = commands.add_parser('stage')
    staged.add_argument('--references', type=Path, required=True); staged.add_argument('--segment', required=True)
    staged.add_argument('--output', type=Path, required=True); staged.add_argument('--runtime-file', type=Path, required=True)
    staged.add_argument('--host', required=True); staged.add_argument('--remote-root', required=True)
    args = parser.parse_args()
    if args.command == 'capture':
        result = prepare_reference_source(args.output, args.runtime_file)
    elif args.command == 'identity':
        result = admit_runtime(args.runtime_file.read_text())
    elif args.command == 'generate':
        result = generate(args.output, args.runtime_file, base().make_plan(args.aw, args.squares, args.chunk_squares,
            args.checkpoint_every, args.seed, args.base))
    else:
        result = stage(args.references, args.segment, args.output, args.runtime_file, args.host, args.remote_root)
    print(json.dumps(result, indent=2))
