"""Qualified user75 accounting on unchanged serial burst4/8GiB executors."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = 'a8c42095d5d174b6bc622eb10774a0a581e6060b8366d981afabc39084ddcfdd'
EXECUTOR_SHA = '8c7234c341ad20823520761c429e030f26b8ed4e90cb4b171f3f91f328cfe767'
METER_SHA = '9c3d902e3da0969145c4148f06a51ec9ca22a322513068074f7b338cb8ddf137'


def module():
    raw = (HERE / 'native_class_package_v3.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError('frozen source-bound package')
    text = raw.decode()
    for old, new in [
        ('native_class_package_v3.py', 'native_class_package_azure75_v1.py'),
        ('native_class_v2.py', 'native_class_burst8_v1.py'),
        ('5a3ab8b8306e74de9d6dd9fcbe26ee185a25dff95ac6a5e1b51503ce00e543c3', EXECUTOR_SHA),
        ('host_hours_azure_v2.py', 'host_hours_azure_signed_v1.py'),
        ('b0875ec8fb12780c637548e9664d25d47a2b77bb8ef7d3ff997bbdfc640a8c9e', METER_SHA),
    ]:
        if old not in text:
            raise ValueError('exact75 source binding anchor')
        text = text.replace(old, new)
    value = types.ModuleType('_qualified_azure75_package')
    value.__file__ = str(Path(__file__).resolve())
    exec(compile(text, '[user75 source-bound accounting]', 'exec'), value.__dict__)
    return value


base = module()
accounting_meter = base.meter

def descriptor_binding(value,host,max_seconds=3715,now=None,source_sha256=None,profile_sha256=None):
    """Packet identity only. Live money/credit is checked by the hourly queue."""
    if (value.get('schema')!='azure-host-hours-budget-v5' or value.get('kind')!='azure-host-hours-v5'
        or value.get('provider')!='azure' or value.get('host')!=host or host!='gfn16-azure-sim-f32'
        or type(value.get('max_seconds')) is not int or value['max_seconds']!=max_seconds
        or max_seconds!=3715 or value.get('checker_sha256')!=METER_SHA):
        raise ValueError('exact packet provider/host/runtime/checker identity')
    for pin in (value.get('source_sha256'),value['provider_inputs']['sha256']):
        if type(pin) is not str or len(pin)!=64 or any(c not in '0123456789abcdef' for c in pin):
            raise ValueError('canonical source/input digest')
    if source_sha256 is not None and value['source_sha256']!=source_sha256:
        raise ValueError('role source/config identity drift')
    if profile_sha256 is not None and value['profile']['sha256']!=profile_sha256:
        raise ValueError('selected profile identity drift')
    return dict(status='BOUND_packet_identity_not_financial_admission',host=host,max_seconds=max_seconds)

def meter():
    value=accounting_meter()
    value.validate_budget=descriptor_binding
    return value

base.meter=meter
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
            raise ValueError('ticket identity before source-bound budget')
        result = worker(json.loads(args.ticket.read_text())['budget']).run(args.ticket, args.ticket_sha256)
    print(json.dumps(result, indent=2))
