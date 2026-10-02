"""One source-pinned ordinal3300 model inside the existing3700s GCP package."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
STATIC_SHA = '92f87083f3b70a3d64110d18ac3ff89af0783c2c4d15ab7ed65bfd2b4f217693'
EXECUTOR_SHA = '744f041a01b7104762f3220a2a7e60141b19ebd4c472c24301d7c45b7d11a8f0'
DURATION_SHA = 'b68a3984f581b4ae3170b1e48b62fc9d6214fe1e6bf47daf1bb30c96aa25c8d6'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def load(name, pin):
    path = HERE / name
    need(not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
         'exact ordinal package dependency')
    spec = importlib.util.spec_from_file_location('_ordinal_package_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


duration = load('native_ordinal_duration_v1.py', DURATION_SHA)


def ordinal_source(text):
    changes = [
        ('max_seconds=3700,', 'max_seconds=3700,runtime_duration=duration_policy.SHAPE,'),
        ("ticket['max_seconds']==3700", "ticket['max_seconds']==3700 and ticket['runtime_duration']==duration_policy.SHAPE"),
        ("original=json.loads(manifest_path.read_text());snapshot.closed_inputs(source_root,original['sources'])",
         "original=json.loads(manifest_path.read_text());snapshot.closed_inputs(source_root,original['sources']);duration_policy.validate(original,source_root,shared.profile(profile_id)['host'],require_policy=False)"),
        ('m=json.loads(json.dumps(original));m.update(',
         "m=json.loads(json.dumps(original));m['runtime_duration']=duration_policy.descriptor(original);m.update("),
        ("queue.identifier(ticket['id']);need(root==",
         "duration_policy.validate(m,source,profile['host']);queue.identifier(ticket['id']);need(root=="),
    ]
    for old, new in changes:
        need(text.count(old) == 1, 'unique ordinal package anchor: ' + old)
        text = text.replace(old, new, 1)
    return text


def worker():
    raw = (HERE / 'native_static_package_v1.py').read_bytes()
    need(hashlib.sha256(raw).hexdigest() == STATIC_SHA, 'frozen static package')
    text = raw.decode()
    changes = [
        ('native_static_package_v1.py', 'native_ordinal_package_v1.py'),
        ('native_static_v1.py', 'native_ordinal_class_v1.py'),
        ('5b1b0f0dc584df8d6887235a9ddf1610f4956823aa84131438de7b8054f1e0ab', EXECUTOR_SHA),
        ("name.startswith('cloud/')", "'/' in name"),
        ("pins.update({'native_package_v1.py':PARENT_SHA,'native_ordinal_class_v1.py':STATIC_SHA})",
         "pins.update({'native_package_v1.py':PARENT_SHA,'native_ordinal_class_v1.py':STATIC_SHA,'native_static_package_v1.py':'" + STATIC_SHA + "'})"),
        ('budget_binding=budget_binding)', 'budget_binding=budget_binding,duration_policy=DURATION)'),
        ('    return text\n', '    return ORDINAL_SOURCE(text)\n'),
    ]
    for old, new in changes:
        need(old in text, 'ordinal package adapter anchor: ' + old)
        text = text.replace(old, new)
    module = types.ModuleType('_ordinal_finite_package')
    module.__file__ = str(Path(__file__).resolve())
    module.__dict__.update(DURATION=duration, ORDINAL_SOURCE=ordinal_source)
    exec(compile(text, '[single ordinal3300 package]', 'exec'), module.__dict__)
    return module.worker()


def prepare(manifest, source_root, profile, job_id, phase, out, budget):
    need(phase == 'run', 'ordinal is explicit full model run only')
    return worker().prepare(manifest, source_root, profile, job_id, phase, out, budget)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    for name in ('manifest', 'source-root', 'output', 'budget'):
        prep.add_argument('--' + name, type=Path, required=True)
    prep.add_argument('--profile', required=True)
    prep.add_argument('--id', required=True)
    prep.add_argument('--phase', choices=['run'], required=True)
    run = commands.add_parser('run')
    run.add_argument('--ticket', type=Path, required=True)
    run.add_argument('--ticket-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.manifest.resolve(), args.source_root.resolve(), args.profile,
                         args.id, args.phase, args.output.resolve(), args.budget.resolve())
    else:
        result = worker().run(args.ticket, args.ticket_sha256)
    print(json.dumps(result, indent=2))
