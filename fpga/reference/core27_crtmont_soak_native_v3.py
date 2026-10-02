"""Additive Azure 2.2.1 candidate oracle binding; no launcher/host mutation.

Preserves the frozen oracle and native-v2 staging contract. The actual source-
built Python package, metadata, bytecode, extension and linked runtime files are
closed external inputs, checked before import. GCP v2 remains unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/core27_crtmont_soak_native_v3.py'
PARENT = 'reference/core27_crtmont_soak_native_v2.py'
PARENT_SHA = '17c4d4a8830cf03f371a476836b942066552e9bcb44bf9858236194919717844'
SOURCE_SHA = 'e83e07567441b78cb87544910cb3cc4fe94e7da987e93ef7622e76fb96650432'
PYTHON_SHA = 'e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def parent():
    raw = (ROOT/PARENT).read_bytes()
    need(hashlib.sha256(raw).hexdigest() == PARENT_SHA, 'SOAK_AZURE_FROZEN_NATIVE_PARENT')
    text = raw.decode()
    replacements = [
        ("SELF = 'reference/core27_crtmont_soak_native_v2.py'", "SELF = '"+SELF+"'"),
        ("runtime['package_version'] == '2.3.1'", "runtime['package_version'] == '2.2.1'"),
        ('(BASE, SELF, module.BENCH, module.HEADER, module.TEST, INSTALLER)',
         "(BASE, SELF, '"+PARENT+"', module.BENCH, module.HEADER, module.TEST, INSTALLER)"),
        ('(SELF, INSTALLER)', "(SELF, '"+PARENT+"', INSTALLER)")]
    for old, new in replacements:
        need(old in text, 'SOAK_AZURE_PARENT_ANCHOR')
        text = text.replace(old, new)
    module = types.ModuleType('_soak_azure_native_parent'); module.__file__ = str(ROOT/SELF)
    exec(compile(text, str(ROOT/PARENT)+'[Azure-runtime-data]', 'exec'), module.__dict__)
    module.admit_runtime = admit_runtime
    return module


def admit_runtime(text):
    need(platform.system() == 'Linux', 'SOAK_AZURE_NATIVE_REFERENCE_LINUX')
    value = json.loads(text)
    need(value['schema'] == 'soak-azure-module-closure-observation-v1'
         and value['no_import_or_mutation'] is True and not value['symlinks']
         and value['source_archive_sha256'] == SOURCE_SHA
         and value['package_version'] == '2.2.1', 'SOAK_AZURE_RUNTIME_DESCRIPTOR')
    hosts = {'gfn16-azure-f16': ('native-tools-v4', 'azure-sim-setup-v6'),
             'gfn16-azure-sim-f32': ('native-tools-v3', 'azure-sim-f32-setup-v3')}
    need(value['host'] in hosts and value['host'] == platform.node()
         and value['user'] == 'azureuser', 'SOAK_AZURE_RUNTIME_HOST')
    prefix_name, setup_name = hosts[value['host']]
    worker = Path('/home/azureuser/gfn16-worker')
    prefix = worker/prefix_name/'python-env'
    site = prefix/'lib/python3.12/site-packages'
    roots = [site/'gmpy2', site/'gmpy2-2.2.1.dist-info']
    need(value['python_path'] == str(prefix/'bin/python3')
         and value['python_resolved'] == '/usr/bin/python3.12'
         and Path(sys.executable).resolve() == Path(value['python_resolved'])
         and (prefix/'bin/python3').resolve() == Path(value['python_resolved'])
         and value['python_version'] == platform.python_version() == '3.12.3'
         and sha(value['python_resolved']) == PYTHON_SHA, 'SOAK_AZURE_RUNTIME_INTERPRETER')
    need(value['module_roots'] == list(map(str, roots)), 'SOAK_AZURE_EXACT_PACKAGE_PLACEMENT')
    files = value['files_sha256']; inside = set()
    for root in roots:
        need(root.is_dir() and root.resolve() == root and not root.is_symlink(), 'SOAK_AZURE_RUNTIME_ROOT')
        for path in root.rglob('*'):
            need(not path.is_symlink(), 'SOAK_AZURE_RUNTIME_SYMLINK')
            if path.is_file():
                need(path.stat().st_nlink == 1, 'SOAK_AZURE_RUNTIME_HARDLINK')
                inside.add(str(path))
    libs = [Path('/usr/lib/x86_64-linux-gnu')/name for name in
        ('libgmp.so.10.5.0', 'libmpfr.so.6.2.1', 'libmpc.so.3.3.1',
         'libc.so.6', 'libm.so.6', 'ld-linux-x86-64.so.2')]
    expected = inside | set(map(str, libs)) | {'/usr/bin/python3.12', str(prefix/'pyvenv.cfg')}
    need(set(files) == expected and inside, 'SOAK_AZURE_RUNTIME_EXACT_CLOSURE')
    for name, pin in files.items():
        path = Path(name)
        need(path.is_file() and not path.is_symlink() and path.resolve() == path
             and sha(path) == pin, 'SOAK_AZURE_RUNTIME_FILE_DRIFT')
    source_archive = worker/setup_name/'gmpy2-2.2.1.tar.gz'
    need(source_archive.is_file() and not source_archive.is_symlink()
         and sha(source_archive) == SOURCE_SHA, 'SOAK_AZURE_RETAINED_SOURCE_ARCHIVE')
    direct = json.loads((roots[1]/'direct_url.json').read_text())
    need(direct['archive_info']['hashes']['sha256'] == SOURCE_SHA,
         'SOAK_AZURE_INSTALLED_SOURCE_PROVENANCE')
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(site))
    import gmpy2
    need(gmpy2.version() == '2.2.1' and gmpy2.mp_version() == 'GMP 6.3.0'
         and gmpy2.mpfr_version() == 'MPFR 4.2.1' and gmpy2.mpc_version() == 'MPC 1.3.1'
         and gmpy2.__file__ == str(roots[0]/'__init__.py'), 'SOAK_AZURE_EXACT_IMPORT')
    for name, module in sys.modules.items():
        if name == 'gmpy2' or name.startswith('gmpy2.'):
            path = getattr(module, '__file__', None)
            if path:
                need(path in files and sha(path) == files[path], 'SOAK_AZURE_LOADED_MODULE_ORIGIN')
    return dict(status='passed_exact_auxiliary_reference_runtime', files=len(files),
        runtime_manifest_sha256=hashlib.sha256(text.encode()).hexdigest(),
        python_sha256=PYTHON_SHA, import_root=str(site), package_version='2.2.1',
        retained_source_archive_sha256=SOURCE_SHA)


def stage(references, segment, output, runtime_file, host, remote_root):
    # Frozen staging checks a package_version field in addition to host. The
    # observed descriptor stores package metadata separately from module pins.
    return parent().stage(references, segment, output, runtime_file, host, remote_root)


def validate(stdout, stderr, returncode, config, assets):
    return parent().validate(stdout, stderr, returncode, config, assets)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    capture = commands.add_parser('capture')
    capture.add_argument('--output', type=Path, required=True); capture.add_argument('--runtime-file', type=Path, required=True)
    identity = commands.add_parser('identity'); identity.add_argument('--runtime-file', type=Path, required=True)
    generate = commands.add_parser('generate')
    generate.add_argument('--output', type=Path, required=True); generate.add_argument('--runtime-file', type=Path, required=True)
    for name, default in (('aw',16), ('base',604832956), ('squares',2), ('chunk-squares',2), ('checkpoint-every',1), ('seed',20261001)):
        generate.add_argument('--'+name, type=int, default=default)
    staged = commands.add_parser('stage')
    for name in ('references', 'output', 'runtime-file'):
        staged.add_argument('--'+name, type=Path, required=True)
    for name in ('segment', 'host', 'remote-root'):
        staged.add_argument('--'+name, required=True)
    args = parser.parse_args(); module = parent()
    if args.command == 'capture':
        result = module.prepare_reference_source(args.output, args.runtime_file)
    elif args.command == 'identity':
        result = admit_runtime(args.runtime_file.read_text())
    elif args.command == 'generate':
        plan = module.base().make_plan(args.aw, args.squares, args.chunk_squares, args.checkpoint_every, args.seed, args.base)
        result = module.generate(args.output, args.runtime_file, plan)
    else:
        result = stage(args.references, args.segment, args.output, args.runtime_file, args.host, args.remote_root)
    print(json.dumps(result, indent=2))
