"""One finite r38 package/worker binding; no role-specific dispatch framework.

Uses the exact frozen static packager and changes only its executor binding,
closed dependency paths and own filename. Existing claims, budgets, snapshots,
typed output validation and stop-on-failure remain intact.
"""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = '92f87083f3b70a3d64110d18ac3ff89af0783c2c4d15ab7ed65bfd2b4f217693'
EXECUTOR_SHA = '1a50703e0554575e323697a11d5bbf43778603f78b1c978406734d7678529516'


def worker():
    raw = (HERE / 'native_static_package_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError('frozen static package identity')
    text = raw.decode()
    changes = [
        ('native_static_package_v1.py', 'native_class_package_v1.py'),
        ('native_static_v1.py', 'native_class_v1.py'),
        ('5b1b0f0dc584df8d6887235a9ddf1610f4956823aa84131438de7b8054f1e0ab', EXECUTOR_SHA),
        ("name.startswith('cloud/')", "'/' in name"),
        ("pins.update({'native_package_v1.py':PARENT_SHA,'native_class_v1.py':STATIC_SHA})",
         "pins.update({'native_package_v1.py':PARENT_SHA,'native_class_v1.py':STATIC_SHA, 'native_static_package_v1.py': '" + PARENT_SHA + "'})")]
    for old, new in changes:
        if old not in text:
            raise ValueError('class package source anchor: ' + old)
        text = text.replace(old, new)
    module = types.ModuleType('_class_package_binding')
    module.__file__ = str(Path(__file__).resolve())
    exec(compile(text, str(HERE / 'native_static_package_v1.py') + '[r38]', 'exec'), module.__dict__)
    return module.worker()


def prepare(manifest, source_root, profile, job_id, phase, out, budget):
    return worker().prepare(manifest, source_root, profile, job_id, phase, out, budget)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    for name in ('manifest', 'source-root', 'output', 'budget'):
        prep.add_argument('--' + name, type=Path, required=True)
    prep.add_argument('--profile', required=True)
    prep.add_argument('--id', required=True)
    prep.add_argument('--phase', choices=('lint', 'run'), required=True)
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
