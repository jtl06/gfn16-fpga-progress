"""Fixed-wide package selecting the callable child-wrapper repair only."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='9632fc4f55038052add52cc8bdce1cdc2398093baf5d9561677637cdad9b2d56'
EXECUTOR_SHA='0342e1a85f70ec3ba0afe3612f408d9e2ccffb770ebcef7b2e4352f228ff7ff5'


def module():
    raw=(HERE/'native_threaded_wide_package_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen fixed-wide package')
    text=raw.decode().replace('native_threaded_wide_package_v1.py','native_threaded_wide_package_v2.py')
    text=text.replace('native_threaded_wide_v1.py','native_threaded_wide_v2.py').replace('75bd5bae7ffa549db530c02a46c527d5d996391980385e2a28c3d5c39adac9a1',EXECUTOR_SHA)
    value=types.ModuleType('_callable_wide_package');value.__file__=str(Path(__file__).resolve())
    exec(compile(text,'[wide callable selector repair]','exec'),value.__dict__)
    return value


base=module()
runtime=base.runtime
execution_contract=base.execution_contract
wide_binding=base.wide_binding
meter=base.meter
source_identity=base.source_identity


def worker(budget):
    value=base.worker(budget);value.PINS['native_threaded_wide_package_v1.py']=PARENT_SHA;return value


def prepare(manifest,source_root,profile,job_id,phase,out,budget):
    if phase!='run' or profile!='azure-burst16-thread-wide07-v1':raise ValueError('fixed wide short run only')
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
