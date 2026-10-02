"""Measured threaded-long package with intrinsic full-window deadline guard."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='ef0da878723fd06184a2cb57396f628ad4c0546612830c595d4e075e056960b3'
EXECUTOR_SHA='8df98eae0fa2b82f868eadf2730cb1b47c11fdf02f07445b1c3b62983e1edfb4'


def module():
    raw=(HERE/'native_threaded_long_package_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen threaded long package')
    text=raw.decode().replace('native_threaded_long_package_v1.py','native_threaded_long_package_v2.py')
    text=text.replace('native_threaded_long_class_v1.py','native_threaded_long_class_v2.py').replace('8eeeabd2456fd29e10a8534e007c98baf5832e94cec753f509a97df38ab7c0db',EXECUTOR_SHA)
    result=types.ModuleType('_intrinsic_deadline_long_package');result.__file__=str(Path(__file__).resolve())
    exec(compile(text,'[intrinsic deadline package]','exec'),result.__dict__)
    return result


base=module()
duration=base.duration
bind_role=base.bind_role
meter=base.meter
source_identity=base.source_identity
binding=base.binding


def worker(budget):
    result=base.worker(budget);result.PINS['native_threaded_long_package_v1.py']=PARENT_SHA
    return result


def prepare(manifest,source_root,profile,job_id,phase,out,budget):
    if phase!='run' or profile!=duration.PROFILE:raise ValueError('exact measured threaded long profile')
    return worker(json.loads(Path(budget).read_text())).prepare(manifest,source_root,profile,job_id,phase,out,budget)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare')
    for name in ('manifest','source-root','output','budget'):prep.add_argument('--'+name,type=Path,required=True)
    prep.add_argument('--profile',required=True);prep.add_argument('--id',required=True);prep.add_argument('--phase',choices=['run'],required=True)
    run=sub.add_parser('run');run.add_argument('--ticket',type=Path,required=True);run.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.manifest.resolve(),args.source_root.resolve(),args.profile,args.id,args.phase,args.output.resolve(),args.budget.resolve())
    else:
        if hashlib.sha256(args.ticket.read_bytes()).hexdigest()!=args.ticket_sha256:raise ValueError('ticket before budget data')
        result=worker(json.loads(args.ticket.read_text())['budget']).run(args.ticket,args.ticket_sha256)
    print(json.dumps(result,indent=2))
