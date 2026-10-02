"""Finite/typed accounting repair over immutable long package v1.

Runtime, source contracts, duration and resources are unchanged. This successor
rejects non-finite financial values and noncanonical receipt digests before any
preparation or run-side destination/claim effects.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = '84f806d3b6a5a09acd652849418e65f55f05e443ee325980b30085c1f9cdc64f'


def module():
    raw = (HERE / 'native_long_package_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError('frozen long package v1')
    text = raw.decode().replace('native_long_package_v1.py', 'native_long_package_v2.py')
    result = types.ModuleType('_strict_long_package'); result.__file__ = str(Path(__file__).resolve())
    exec(compile(text, '[finite typed long budget]', 'exec'), result.__dict__)
    return result


base = module()
prior_budget_check = base.long_budget_check


def long_budget_check(value, now=None):
    for key in ('total_allowance_usd', 'planning_usd_per_hour', 'remaining_after_reserves_usd'):
        if type(value.get(key)) not in (int, float) or not math.isfinite(value[key]):
            raise ValueError('finite typed financial field: ' + key)
    if not 0 <= value['remaining_after_reserves_usd'] <= value['total_allowance_usd']:
        raise ValueError('remaining budget within total allowance')
    pin = value.get('source_receipt_sha256')
    if type(pin) is not str or re.fullmatch('[0-9a-f]{64}', pin) is None:
        raise ValueError('canonical SHA256 accounting receipt')
    return prior_budget_check(value, now)


base.long_budget_check = long_budget_check
duration = base.duration
bind_role = base.bind_role


def worker():
    result = base.worker()
    result.PINS['native_long_package_v1.py'] = PARENT_SHA
    return result


def prepare(manifest, source_root, profile, job_id, phase, out, budget):
    if phase != 'run': raise ValueError('long profile is explicit run only')
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
