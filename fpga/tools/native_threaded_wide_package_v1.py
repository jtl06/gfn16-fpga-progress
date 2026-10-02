"""One immutable eight-physical allocation for short T5b model2/4/8 pilots."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='a8c42095d5d174b6bc622eb10774a0a581e6060b8366d981afabc39084ddcfdd'
EXECUTOR_SHA='75bd5bae7ffa549db530c02a46c527d5d996391980385e2a28c3d5c39adac9a1'


def runtime():
    path=HERE/'native_threaded_wide_v1.py'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=EXECUTOR_SHA:raise ValueError('exact fixed-wide runtime')
    spec=importlib.util.spec_from_file_location('_package_fixed_wide',path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def execution_contract(profile):
    return dict(schema='fixed-wide-execution-contract-v1',profile_id=profile['profile_id'],
      profile_source=profile['profile_source'],profile_sha256=profile['profile_sha256'],
      hardware_profile_source=profile['hardware_profile_source'],hardware_profile_sha256=profile['hardware_profile_sha256'],
      topology_observation=profile['topology_observation'],topology_observation_sha256=profile['topology_observation_sha256'],
      observed_l3=profile['observed_l3'],runtime_allocation=profile['runtime_allocation'],placement=profile['fixed_placement'])


def wide_binding(manifest,profile,final=False):
    count=runtime().validate_threaded(manifest);role=manifest.get('wide_thread_pilot',{})
    if profile['profile_id']!='azure-burst16-thread-wide07-v1' or role.get('schema')!='gfn16-fixed-wide-thread-pilot-role-v1' \
       or type(role.get('thread_count')) is not int or role['thread_count']!=count \
       or role.get('fixed_profile')!=profile['profile_id'] or role.get('placement')!=profile['fixed_placement']:
        raise ValueError('exact wide role count/profile/constituent placement')
    if final and manifest.get('fixed_execution')!=execution_contract(profile):raise ValueError('immutable wide execution contract')


def wide_source(text):
    changes=[("original=json.loads(manifest_path.read_text());snapshot.closed_inputs(source_root,original['sources'])",
      "original=json.loads(manifest_path.read_text());snapshot.closed_inputs(source_root,original['sources']);wide_binding(original,shared.profile(profile_id))"),
      ('m=json.loads(json.dumps(original));',"m=json.loads(json.dumps(original));m['fixed_execution']=execution_contract(profile);"),
      ('max_seconds=3700,','max_seconds=3700,placement=profile[\'fixed_placement\'],fixed_execution=execution_contract(profile),'),
      ("queue.identifier(ticket['id']);need(root==", "wide_binding(m,profile,True);need(ticket.get('placement')==profile['fixed_placement'] and ticket.get('fixed_execution')==execution_contract(profile),'ticket fixed wide allocation');queue.identifier(ticket['id']);need(root==")]
    for old,new in changes:
        if text.count(old)!=1:raise ValueError('unique fixed-wide package anchor: '+old)
        text=text.replace(old,new,1)
    return text


def module():
    raw=(HERE/'native_class_package_v3.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen source-bound package')
    text=raw.decode()
    changes=[('native_class_package_v3.py','native_threaded_wide_package_v1.py'),
      ('native_class_v2.py','native_threaded_wide_v1.py'),
      ('5a3ab8b8306e74de9d6dd9fcbe26ee185a25dff95ac6a5e1b51503ce00e543c3',EXECUTOR_SHA),
      ('host_hours_azure_v2.py','host_hours_azure_v3.py'),
      ('b0875ec8fb12780c637548e9664d25d47a2b77bb8ef7d3ff997bbdfc640a8c9e','d133b301ff0dc193774090f991ffa8bc6ee51f06fd318d21ff89673b1632a20c'),
      ("profile_sha256=profile['profile_sha256']","profile_sha256=profile['hardware_profile_sha256']"),
      ('    changes=[',"    adapted=adapted.replace(\"load('build_identity_v1.py')\",\"load('build_identity_v2.py')\")\n    changes=["),
      ('    namespace=dict(', '    adapted=WIDE_SOURCE(adapted)\n    namespace=dict('),
      ('budget_binding=binding)','budget_binding=binding,wide_binding=WIDE_BINDING,execution_contract=EXECUTION_CONTRACT)')]
    for old,new in changes:
        if old not in text:raise ValueError('wide package source anchor')
        text=text.replace(old,new)
    result=types.ModuleType('_fixed_wide_package');result.__file__=str(Path(__file__).resolve())
    result.__dict__.update(WIDE_SOURCE=wide_source,WIDE_BINDING=wide_binding,EXECUTION_CONTRACT=execution_contract)
    exec(compile(text,'[fixed wide short package]','exec'),result.__dict__)
    return result


base=module()
meter=base.meter
source_identity=base.source_identity


def worker(budget):
    if budget.get('provider')!='azure' or budget.get('host')!='gfn16-azure-sim-f32':raise ValueError('exact wide Azure host budget')
    result=base.worker(budget);result.PINS['native_class_package_v3.py']=PARENT_SHA;return result


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
