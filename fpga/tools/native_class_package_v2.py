"""Fail-closed host-budget binding successor; Azure accounting not yet admitted."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='61ae733fbd269a040aa73f02cf1d86810216fba24b57dc9ab4d8aade896a4932'


def binding(value,profile):
    if profile['host']=='aethia':
        if value!=dict(provider='local',host='aethia',cloud_cost_usd=0) or type(value['cloud_cost_usd']) is not int:
            raise ValueError('exact local aethia budget')
    elif profile['host']=='gfn16-pilot-c4d':
        if value.get('provider')!='gcp':raise ValueError('exact GCP host budget')
    else:raise ValueError('host budget not admitted; no cross-provider accounting')


def worker():
    raw=(HERE/'native_class_package_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen class package parent')
    text=raw.decode().replace('native_class_package_v1.py','native_class_package_v2.py')
    module=types.ModuleType('_class_package_budget_parent');module.__file__=str(Path(__file__).resolve())
    exec(compile(text,str(HERE/'native_class_package_v1.py')+'[host-budget]','exec'),module.__dict__)
    result=module.worker()
    result.PINS['native_class_package_v1.py']=PARENT_SHA
    result.budget_binding=binding
    return result


def prepare(manifest,source_root,profile,job_id,phase,out,budget):
    return worker().prepare(manifest,source_root,profile,job_id,phase,out,budget)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    prep=commands.add_parser('prepare')
    for name in ('manifest','source-root','output','budget'):prep.add_argument('--'+name,type=Path,required=True)
    prep.add_argument('--profile',required=True);prep.add_argument('--id',required=True);prep.add_argument('--phase',choices=('lint','run'),required=True)
    run=commands.add_parser('run');run.add_argument('--ticket',type=Path,required=True);run.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.manifest.resolve(),args.source_root.resolve(),args.profile,args.id,args.phase,args.output.resolve(),args.budget.resolve())
    else:result=worker().run(args.ticket,args.ticket_sha256)
    print(json.dumps(result,indent=2))
