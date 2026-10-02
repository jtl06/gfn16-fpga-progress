"""Measured two-thread Azure long package; fixed pair/caps and 5000s outer."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = 'a8c42095d5d174b6bc622eb10774a0a581e6060b8366d981afabc39084ddcfdd'
EXECUTOR_SHA = '8eeeabd2456fd29e10a8534e007c98baf5832e94cec753f509a97df38ab7c0db'
DURATION_SHA = '5107d198cca687d1305161d9f1a8ffd952b7691aa92e88f12326ddee65e13fb5'
BINDER_SHA = '84f806d3b6a5a09acd652849418e65f55f05e443ee325980b30085c1f9cdc64f'


def exact(name, pin):
    raw = (HERE / name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin: raise ValueError('frozen dependency: ' + name)
    return raw.decode()


def module():
    text = exact('native_class_package_v3.py', PARENT_SHA)
    changes = [('native_class_package_v3.py', 'native_threaded_long_package_v1.py'),
      ('native_class_v2.py', 'native_threaded_long_class_v1.py'),
      ('5a3ab8b8306e74de9d6dd9fcbe26ee185a25dff95ac6a5e1b51503ce00e543c3', EXECUTOR_SHA),
      ('host_hours_azure_v2.py', 'host_hours_azure_v3.py'),
      ('b0875ec8fb12780c637548e9664d25d47a2b77bb8ef7d3ff997bbdfc640a8c9e', 'd133b301ff0dc193774090f991ffa8bc6ee51f06fd318d21ff89673b1632a20c'),
      ('3715', '5015'),
      ('    changes=[', "    adapted=adapted.replace(\"load('build_identity_v1.py')\", \"load('build_identity_v2.py')\")\n    adapted=LONG_SOURCE(adapted)\n    changes=["),
      ('budget_binding=binding)', 'budget_binding=binding,duration_policy=DURATION)')]
    for old, new in changes:
        if old not in text: raise ValueError('threaded long package anchor: ' + old)
        text = text.replace(old, new)
    result = types.ModuleType('_threaded_long_package'); result.__file__ = str(Path(__file__).resolve())
    result.__dict__.update(LONG_SOURCE=long_source, DURATION=duration)
    exec(compile(text, '[threaded long package]', 'exec'), result.__dict__)
    return result


def long_source(text):
    changes = [('max_seconds=3700,', 'max_seconds=5000,runtime_duration=duration_policy.SHAPE,'),
      ("ticket['max_seconds']==3700", "ticket['max_seconds']==5000 and ticket['runtime_duration']==duration_policy.SHAPE"),
      ("original=json.loads(manifest_path.read_text());snapshot.closed_inputs(source_root,original['sources'])", "original=json.loads(manifest_path.read_text());snapshot.closed_inputs(source_root,original['sources']);duration_policy.validate(original,source_root,shared.profile(profile_id)['host'])"),
      ("queue.identifier(ticket['id']);need(root==", "duration_policy.validate(m,source,profile['host']);queue.identifier(ticket['id']);need(root==")]
    for old, new in changes:
        if text.count(old) != 1: raise ValueError('unique long source anchor: ' + old)
        text = text.replace(old, new, 1)
    return text


# Reuse only the exact data-copy binder, substituting the separately measured
# policy and host. No GCP financial function is exported or called.
_binder = types.ModuleType('_threaded_measurement_binder'); _binder.__file__ = str(Path(__file__).resolve())
_text = exact('native_long_package_v1.py', BINDER_SHA)
_text = _text.replace('native_long_duration_v1.py', 'native_threaded_duration_v1.py').replace('aed7092d33ddedf19405e8da4df4e4bc1b31e29d1054369dd2ef4805f8d89b2c', DURATION_SHA).replace('gfn16-pilot-c4d', 'gfn16-azure-sim-f32')
exec(compile(_text, '[exact measurement binder]', 'exec'), _binder.__dict__)
duration = _binder.duration
bind_role = _binder.bind_role
base = module()
meter = base.meter
source_identity = base.source_identity
binding = base.binding


def worker(budget):
    if budget.get('provider') != 'azure' or budget.get('host') != duration.HOST:
        raise ValueError('exact measured Azure host budget')
    result = base.worker(budget)
    result.PINS.update({'native_class_package_v3.py': PARENT_SHA, 'native_long_package_v1.py': BINDER_SHA})
    return result


def prepare(manifest, source_root, profile, job_id, phase, out, budget):
    if phase != 'run' or profile != duration.PROFILE: raise ValueError('exact measured threaded long run/profile')
    return worker(json.loads(Path(budget).read_text())).prepare(manifest, source_root, profile, job_id, phase, out, budget)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    for name in ('manifest','source-root','output','budget'): prep.add_argument('--'+name,type=Path,required=True)
    prep.add_argument('--profile',required=True); prep.add_argument('--id',required=True); prep.add_argument('--phase',choices=['run'],required=True)
    run = sub.add_parser('run'); run.add_argument('--ticket',type=Path,required=True); run.add_argument('--ticket-sha256',required=True)
    args = parser.parse_args()
    if args.command == 'prepare': result = prepare(args.manifest.resolve(),args.source_root.resolve(),args.profile,args.id,args.phase,args.output.resolve(),args.budget.resolve())
    else:
        if hashlib.sha256(args.ticket.read_bytes()).hexdigest()!=args.ticket_sha256: raise ValueError('ticket before budget data')
        result = worker(json.loads(args.ticket.read_text())['budget']).run(args.ticket,args.ticket_sha256)
    print(json.dumps(result,indent=2))
