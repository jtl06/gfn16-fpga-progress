"""Minimal static-host binding of the frozen shared-v1 finite package worker.

Preserves the source snapshot, build identity, claims and failure-stop sequence.
Only host selection, closed helper/profile paths and local-budget exemption
change. Static executor retains serial compilation and one model thread.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
SELF='native_static_package_v1.py'
PARENT_SHA='1ae024a4efe23410758f6cd17507dc1941d809803c539ee84bb2565f069a0219'
STATIC_SHA='5b1b0f0dc584df8d6887235a9ddf1610f4956823aa84131438de7b8054f1e0ab'


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def helper_path(name):return HERE.parent/name if name.startswith('cloud/') else HERE/name


def source_name(name):return name if name.startswith('cloud/') else 'tools/'+name


def load_file(name,pin):
    path=helper_path(name);need(sha(path)==pin,'exact static package dependency')
    spec=importlib.util.spec_from_file_location('_static_package_'+path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def budget_binding(value,profile):
    if profile['host']=='aethia':
        need(value==dict(provider='local',host='aethia',cloud_cost_usd=0)
             and type(value['cloud_cost_usd']) is int,'exact no-cloud-cost aethia exemption')
    else:need(value['provider']=='gcp','host-bound cloud accounting')


def adapted_source(raw):
    need(hashlib.sha256(raw).hexdigest()==PARENT_SHA,'frozen package source')
    text=raw.decode()
    start=text.index('PINS={');end=text.index('\n\n\ndef need',start)
    text=text[:start]+'PINS=STATIC_PINS'+text[end:]
    replacements=[
      ('path=HERE/name','path=helper_path(name)'),
      ("load('native_shared_v1.py')","load('native_static_v1.py')"),
      ("need(profile_id in shared.PROFILES and phase in ('lint','run'),'known profile/phase')",
       "need(profile_id in shared.SELECTIONS and phase in ('lint','run'),'known static profile/phase')"),
      ("profile=shared.PROFILES[profile_id];native=Path(profile['base'])/'jobs'/job_id",
       "profile=shared.profile(profile_id);budget_binding(budget,profile);native=Path(profile['base'])/'jobs'/job_id"),
      ("helpers={name:(HERE/name).read_bytes() for name in [*PINS,'native_shared_v1.py','native_package_v1.py']}",
       "helpers={name:helper_path(name).read_bytes() for name in [*PINS,'native_shared_v1.py','native_package_v1.py','native_static_package_v1.py']}"),
      ("m['sources']['tools/'+name]","m['sources'][source_name(name)]"),
      ("target=source/'tools'/name;target.parent.mkdir(exist_ok=True)",
       "target=source/source_name(name);target.parent.mkdir(parents=True,exist_ok=True)"),
      ("source/'tools/native_package_v1.py'","source/'tools/native_static_package_v1.py'"),
      ("{*PINS,'native_shared_v1.py','native_package_v1.py'}","{*PINS,'native_shared_v1.py','native_package_v1.py','native_static_package_v1.py'}"),
      ("sha(HERE/name)","sha(helper_path(name))"),
      ("profile=shared.PROFILES[ticket['profile']]","profile=shared.profile(ticket['profile']);budget_binding(ticket['budget'],profile)"),
      ("shared.execution_limits(profile)","shared.execution_limits(profile)")]
    for old,new in replacements:
        count=text.count(old);need(count>=1,'static package source anchor: '+old)
        text=text.replace(old,new)
    return text


def worker():
    parent=load_file('native_package_v1.py',PARENT_SHA)
    static=load_file('native_static_v1.py',STATIC_SHA)
    pins=dict(parent.PINS)
    pins.update({name.removeprefix('tools/'):value for name,value in static.PINS.items()})
    pins.update({'native_package_v1.py':PARENT_SHA,'native_static_v1.py':STATIC_SHA})
    for name,value in pins.items():need(sha(helper_path(name))==value,'closed helper/profile pin')
    def budget(value,now=None):
        if value.get('provider')=='local':
            need(value==dict(provider='local',host='aethia',cloud_cost_usd=0),'local budget descriptor')
        else:parent.budget_check(value,now)
    module=types.ModuleType('_static_package_parent');module.__file__=str(Path(__file__).resolve())
    module.__dict__.update(STATIC_PINS=pins,helper_path=helper_path,source_name=source_name,budget_binding=budget_binding)
    exec(compile(adapted_source((HERE/'native_package_v1.py').read_bytes()),str(HERE/'native_package_v1.py')+'[static-host]','exec'),module.__dict__)
    module.budget_check=budget
    return module


def prepare(manifest,source_root,profile,job_id,phase,out,budget):
    return worker().prepare(manifest,source_root,profile,job_id,phase,out,budget)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare')
    for name in ('manifest','source-root','output','budget'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--profile',required=True);p.add_argument('--id',required=True);p.add_argument('--phase',choices=('lint','run'),required=True)
    p=sub.add_parser('run');p.add_argument('--ticket',type=Path,required=True);p.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.manifest.resolve(),args.source_root.resolve(),args.profile,args.id,args.phase,args.output.resolve(),args.budget.resolve())
    else:result=worker().run(args.ticket,args.ticket_sha256)
    print(json.dumps(result,indent=2))
