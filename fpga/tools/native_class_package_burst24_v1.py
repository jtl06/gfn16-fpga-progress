"""Finite class package for observed r49 hardware and qualified meter v3."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = 'a8c42095d5d174b6bc622eb10774a0a581e6060b8366d981afabc39084ddcfdd'
EXECUTOR_SHA = 'bac59e83c7d65bd6e99d209789121ea6109657bdef9dc7c5f482ffbfadf90911'
METER_SHA = 'd133b301ff0dc193774090f991ffa8bc6ee51f06fd318d21ff89673b1632a20c'


def module():
    raw = (HERE / 'native_class_package_v3.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError('frozen source-bound Azure package')
    text = raw.decode()
    changes = [('native_class_package_v3.py', 'native_class_package_burst24_v1.py'),
               ('native_class_v2.py', 'native_class_burst24_v1.py'),
               ('5a3ab8b8306e74de9d6dd9fcbe26ee185a25dff95ac6a5e1b51503ce00e543c3', EXECUTOR_SHA),
               ('host_hours_azure_v2.py', 'host_hours_azure_v3.py'),
               ('b0875ec8fb12780c637548e9664d25d47a2b77bb8ef7d3ff997bbdfc640a8c9e', METER_SHA)]
    for old, new in changes:
        if old not in text:
            raise ValueError('resized package source anchor')
        text = text.replace(old, new)
    result = types.ModuleType('_resized_azure_package')
    result.__file__ = str(Path(__file__).resolve())
    exec(compile(text, str(HERE / 'native_class_package_v3.py') + '[r49-observed]', 'exec'), result.__dict__)
    return result


base = module()
meter = base.meter
source_identity = base.source_identity
binding = base.binding


def worker(budget):
    result = base.worker(budget)
    result.PINS['native_class_package_v3.py'] = PARENT_SHA
    return result


def prepare(manifest, source_root, profile, job_id, phase, out, budget):
    return worker(json.loads(budget.read_text())).prepare(manifest, source_root, profile, job_id, phase, out, budget)


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
        result = prepare(args.manifest.resolve(), args.source_root.resolve(), args.profile, args.id,
                         args.phase, args.output.resolve(), args.budget.resolve())
    else:
        if hashlib.sha256(args.ticket.read_bytes()).hexdigest() != args.ticket_sha256:
            raise ValueError('ticket identity before budget')
        result = worker(json.loads(args.ticket.read_text())['budget']).run(args.ticket, args.ticket_sha256)
    print(json.dumps(result, indent=2))
