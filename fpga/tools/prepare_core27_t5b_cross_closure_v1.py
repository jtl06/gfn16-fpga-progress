"""Close the exact archived T5b parent dependencies of the frozen bridge.

Source/data copying and isolated metadata validation only. No GMP import,
integer reference computation, HDL, native unit or lifecycle operation.
"""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = 'reference/core27_t5b_soak_v1.py'
REFERENCE_SHA = '636460b5fd8e96696112d53ca792a340f5d2ad1ad843f6f23135877bae6ce962'
BRIDGE = 'reference/core27_t5b_soak_cross_runtime_v1.py'
BRIDGE_SHA = '3be94f597e09455a2b9f3f363dfc6a4ac36a240eb26b22a1717e91a072ea1e83'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path, pin):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and sha(path) == pin, 'regular frozen source')
    spec = importlib.util.spec_from_file_location('_closed_soak_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def validate(manifest_file, source_root):
    """Exercise the actual bridge binding against ONLY the closed tree."""
    source_root = Path(source_root).resolve()
    need(not any(name == 'gmpy2' or name.startswith('gmpy2.') for name in sys.modules), 'metadata process must not import GMP')
    need(source_root.name == 'fpga', 'closed fpga source root')
    manifest = json.loads(Path(manifest_file).read_text())
    for name, pin in manifest['sources'].items():
        path = source_root / name
        need(path.resolve().is_relative_to(source_root) and path.is_file()
             and not path.is_symlink() and sha(path) == pin, 'complete immutable package closure ' + name)
    need(manifest['sources'][BRIDGE] == BRIDGE_SHA, 'unchanged reviewed bridge source')
    bridge = load(source_root / BRIDGE, BRIDGE_SHA)
    results = []
    for step in manifest['steps']:
        callback = step['validator']
        need(callback['source'] == BRIDGE and callback['function'] == 'validate', 'exact bridge callback')
        assets = {name: (source_root / relative).read_text() for name, relative in callback['assets'].items()}
        generation, replay, oracle = bridge.binding(assets)
        results.append(dict(step=step['name'], generation_host=generation['host'], replay_host=replay['host'],
                            case_id=oracle['plan']['case_id'], boundaries=len(oracle['segment']['checkpoints'])))
    need(not any(name == 'gmpy2' or name.startswith('gmpy2.') for name in sys.modules), 'metadata binding imported GMP')
    return dict(status='PASS_closed_package_metadata_binding_not_numeric_or_HDL',
                manifest_sha256=sha(manifest_file), sources=len(manifest['sources']), bindings=results,
                arithmetic_executed=False, GMP_imported=False, HDL_executed=False)


def prepare(manifest_file, source_root, output):
    manifest_file, source_root, output = map(lambda p: Path(p).resolve(), (manifest_file, source_root, output))
    need(not output.exists(), 'fresh parent closure successor')
    original = json.loads(manifest_file.read_text())
    need(original['sources'][BRIDGE] == BRIDGE_SHA, 'unchanged reviewed bridge')
    lineage = load(ROOT / REFERENCE, REFERENCE_SHA)
    order, _ = lineage.parent_sources()  # Source/receipt hashes only; never arithmetic.
    additions = {lineage.FIT + '/' + name: sha(ROOT / lineage.FIT / name)
                 for name in ('manifest.json', 'probe.qsf', *('rtl/' + name for name in order))}
    need(len(additions) == 18 and not (set(additions) & set(original['sources'])), 'exact missing eighteen parent inputs')
    source = output / 'source/fpga'
    source.mkdir(parents=True)
    manifest = deepcopy(original)
    for name, pin in {**original['sources'], **additions}.items():
        path = (ROOT if name in additions else source_root) / name
        need(path.is_file() and not path.is_symlink() and sha(path) == pin, 'source pin before copy ' + name)
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        need(sha(target) == pin, 'copy identity')
    manifest['sources'].update(additions)
    manifest['parent_closure_successor'] = dict(original_manifest_sha256=sha(manifest_file),
                                              added_sources=additions, validator_unchanged=True)
    path = output / 'cross-runtime-manifest.json'
    dump(path, manifest)
    result = validate(path, source)
    result.update(status='prepared_exact_parent_closure_successor_not_dispatched',
                  original_manifest_sha256=sha(manifest_file), manifest=str(path), source_root=str(source),
                  added_sources=additions, validator_sha256=BRIDGE_SHA)
    dump(output / 'prepare-receipt.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    for name in ('manifest', 'source-root', 'output'):
        prep.add_argument('--' + name, type=Path, required=True)
    check = commands.add_parser('validate')
    for name in ('manifest', 'source-root'):
        check.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.manifest, args.source_root, args.output) if args.command == 'prepare' \
        else validate(args.manifest, args.source_root)
    print(json.dumps(result, indent=2))
