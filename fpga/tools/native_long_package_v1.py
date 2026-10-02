"""Source-bound finite long package; GCP only, no dispatcher or automatic retry."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import types

HERE = Path(__file__).resolve().parent
STATIC_SHA = '92f87083f3b70a3d64110d18ac3ff89af0783c2c4d15ab7ed65bfd2b4f217693'
EXECUTOR_SHA = 'ed9c3bbc8796862effc9409beff9a440cb2d13cd4b4cb55f822925ab5ecf1c4f'
DURATION_SHA = 'aed7092d33ddedf19405e8da4df4e4bc1b31e29d1054369dd2ef4805f8d89b2c'


def need(ok, why):
    if not ok: raise ValueError(why)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name, pin):
    path = HERE / name; need(sha(path) == pin, 'exact long package dependency')
    spec = importlib.util.spec_from_file_location('_longpackage_' + path.stem, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


duration = load('native_long_duration_v1.py', DURATION_SHA)


def long_budget_check(value, now=None):
    now = now or datetime.now(timezone.utc)
    stamp = datetime.fromisoformat(value['observed_at'].replace('Z', '+00:00'))
    age = (now - stamp).total_seconds()
    need(stamp.tzinfo is not None and 0 <= age <= 21600, 'fresh six-hour GCP accounting')
    need(value['provider'] == 'gcp' and value['total_allowance_usd'] == 100
         and value['planning_usd_per_hour'] >= 1, 'existing GCP allowance/rate')
    need(value['remaining_after_reserves_usd'] >= value['planning_usd_per_hour'] * (age / 3600 + 10815 / 3600),
         'elapsed host burn plus full10815-second long bound')
    need(value['actual_billing'] is False and type(value['source_receipt_sha256']) is str
         and len(value['source_receipt_sha256']) == 64, 'conservative pinned accounting')


def worker():
    raw = (HERE / 'native_static_package_v1.py').read_bytes()
    need(hashlib.sha256(raw).hexdigest() == STATIC_SHA, 'frozen static package')
    text = raw.decode()
    changes = [
        ('native_static_package_v1.py', 'native_long_package_v1.py'),
        ('native_static_v1.py', 'native_long_class_v1.py'),
        ('5b1b0f0dc584df8d6887235a9ddf1610f4956823aa84131438de7b8054f1e0ab', EXECUTOR_SHA),
        ("name.startswith('cloud/')", "'/' in name"),
        ("pins.update({'native_package_v1.py':PARENT_SHA,'native_long_class_v1.py':STATIC_SHA})",
         "pins.update({'native_package_v1.py':PARENT_SHA,'native_long_class_v1.py':STATIC_SHA,'native_static_package_v1.py':'" + STATIC_SHA + "'})"),
        ('else:parent.budget_check(value,now)', 'else:LONG_BUDGET_CHECK(value,now)'),
        ('budget_binding=budget_binding)', 'budget_binding=budget_binding,duration_policy=DURATION)'),
        ('    return text\n', "    return LONG_SOURCE(text)\n")]
    for old, new in changes:
        need(old in text, 'long package adapter anchor: ' + old)
        text = text.replace(old, new)
    module = types.ModuleType('_long_finite_package'); module.__file__ = str(Path(__file__).resolve())
    module.__dict__.update(DURATION=duration, LONG_BUDGET_CHECK=long_budget_check, LONG_SOURCE=long_source)
    exec(compile(text, '[finite10800 package]', 'exec'), module.__dict__)
    return module.worker()


def long_source(text):
    changes = [('max_seconds=3700,', 'max_seconds=10800,runtime_duration=duration_policy.SHAPE,'),
               ("ticket['max_seconds']==3700", "ticket['max_seconds']==10800 and ticket['runtime_duration']==duration_policy.SHAPE"),
               ("original=json.loads(manifest_path.read_text());snapshot.closed_inputs(source_root,original['sources'])",
                "original=json.loads(manifest_path.read_text());snapshot.closed_inputs(source_root,original['sources']);duration_policy.validate(original,source_root,shared.profile(profile_id)['host'])"),
               ("queue.identifier(ticket['id']);need(root==", "duration_policy.validate(m,source,profile['host']);queue.identifier(ticket['id']);need(root==")]
    for old, new in changes:
        need(text.count(old) == 1, 'unique duration package anchor: ' + old)
        text = text.replace(old, new, 1)
    return text


def bind_role(manifest_path, source_root, evidence_paths, output):
    """Add four immutable measurement inputs without editing the donor role."""
    manifest = json.loads(Path(manifest_path).read_text())
    need(set(evidence_paths) == set(duration.EVIDENCE), 'four evidence paths')
    values = {key: json.loads(Path(path).read_text()) for key, path in evidence_paths.items()}
    pins = {key: sha(path) for key, path in evidence_paths.items()}
    admission = duration.assess(manifest, values, pins, 'gfn16-pilot-c4d')
    snapshot = load('snapshot_native_sources_v2.py', 'db9786b52e0bb53545aa9a800f45dc00beec6663346cfa77f3ec2d0b1c6c5f83')
    source_root, output = Path(source_root), Path(output)
    snapshot.closed_inputs(source_root, manifest['sources'])
    need(output.is_absolute() and output.resolve() == output and not output.exists(), 'fresh bound role destination')
    output.mkdir(parents=True)
    source = output / 'source/fpga'; source.mkdir(parents=True)
    try:
        for name, pin in manifest['sources'].items():
            target = source / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_root / name, target); need(sha(target) == pin, 'unchanged donor source')
        evidence = {}
        for key, path in evidence_paths.items():
            name = 'long-duration/' + key + '.json'; target = source / name
            need(name not in manifest['sources'] and not target.exists(), 'fresh evidence namespace')
            target.parent.mkdir(exist_ok=True); shutil.copyfile(path, target)
            need(sha(target) == pins[key], 'measurement changed during binding')
            manifest['sources'][name] = pins[key]; evidence[key] = dict(path=name, sha256=pins[key])
        manifest['runtime_duration'] = dict(shape=duration.SHAPE, evidence=evidence, contract_sha256=admission['contract_sha256'])
        duration.validate(manifest, source, 'gfn16-pilot-c4d')
        snapshot.closed_inputs(source, manifest['sources'])
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (output / 'duration-admission.json').write_text(json.dumps(admission, indent=2) + '\n')
        return dict(manifest=str(output / 'manifest.json'), source_root=str(source), admission=admission)
    except BaseException as error:
        (output / 'failure.json').write_text(json.dumps(dict(error=repr(error), status='failed_binding_preserved')) + '\n')
        raise


def prepare(manifest, source_root, profile, job_id, phase, out, budget):
    need(phase == 'run', 'long profile is explicit run only')
    return worker().prepare(manifest, source_root, profile, job_id, phase, out, budget)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    bind = sub.add_parser('bind')
    for name in ('manifest', 'source-root', 'output', 'forecast', 'pilot-manifest', 'pilot-report', 'pilot-gate'):
        bind.add_argument('--' + name, type=Path, required=True)
    prep = sub.add_parser('prepare')
    for name in ('manifest', 'source-root', 'output', 'budget'): prep.add_argument('--' + name, type=Path, required=True)
    prep.add_argument('--profile', required=True); prep.add_argument('--id', required=True); prep.add_argument('--phase', choices=['run'], required=True)
    run = sub.add_parser('run'); run.add_argument('--ticket', type=Path, required=True); run.add_argument('--ticket-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'bind':
        result = bind_role(args.manifest, args.source_root, {key: getattr(args, key) for key in duration.EVIDENCE}, args.output)
    elif args.command == 'prepare':
        result = prepare(args.manifest, args.source_root, args.profile, args.id, args.phase, args.output, args.budget)
    else:
        result = worker().run(args.ticket, args.ticket_sha256)
    print(json.dumps(result, indent=2))
