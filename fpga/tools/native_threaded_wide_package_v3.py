"""Fixed-wide package selecting the callable and live-guard repairs."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='9632fc4f55038052add52cc8bdce1cdc2398093baf5d9561677637cdad9b2d56'
EXECUTOR_SHA='71924875229a549fbcfb8cd52252406a8610d40946597e1d8b2470ae843466d7'


def module():
    raw=(HERE/'native_threaded_wide_package_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen fixed-wide package')
    text=raw.decode().replace('native_threaded_wide_package_v1.py','native_threaded_wide_package_v3.py')
    text=text.replace('native_threaded_wide_v1.py','native_threaded_wide_v3.py').replace('75bd5bae7ffa549db530c02a46c527d5d996391980385e2a28c3d5c39adac9a1',EXECUTOR_SHA)
    text=text.replace("('host_hours_azure_v2.py','host_hours_azure_v3.py')",
        "('host_hours_azure_v2.py','host_hours_azure_signed_v1.py')")
    text=text.replace('d133b301ff0dc193774090f991ffa8bc6ee51f06fd318d21ff89673b1632a20c',
        '9c3d902e3da0969145c4148f06a51ec9ca22a322513068074f7b338cb8ddf137')
    value=types.ModuleType('_callable_wide_package');value.__file__=str(Path(__file__).resolve())
    exec(compile(text,'[wide callable selector repair]','exec'),value.__dict__)
    return value


base=module()
runtime=base.runtime
execution_contract=base.execution_contract
source_identity=base.source_identity
accounting_meter=base.meter

def meter():
    value=accounting_meter()
    def bound(budget,host,max_seconds=3715,now=None,source_sha256=None,profile_sha256=None):
        if (budget.get('schema')!='azure-host-hours-budget-v5' or budget.get('kind')!='azure-host-hours-v5'
            or budget.get('provider')!='azure' or budget.get('host')!=host or host!='gfn16-azure-sim-f32'
            or type(budget.get('max_seconds')) is not int or budget['max_seconds']!=max_seconds or max_seconds!=3715
            or budget.get('checker_sha256')!='9c3d902e3da0969145c4148f06a51ec9ca22a322513068074f7b338cb8ddf137'):
            raise ValueError('exact source-bound hourly wide packet descriptor')
        if source_sha256 is not None and budget['source_sha256']!=source_sha256:raise ValueError('source identity drift')
        if profile_sha256 is not None and budget['profile']['sha256']!=profile_sha256:raise ValueError('hardware identity drift')
    value.validate_budget=bound
    return value

def wide_binding(manifest,profile,final=False):
    count=runtime().validate_threaded(manifest);role=manifest.get('wide_thread_pilot',{})
    if (profile['profile_id'] not in runtime().SELECTIONS
        or role.get('schema')!='gfn16-fixed-wide-thread-pilot-role-v1'
        or type(role.get('thread_count')) is not int or role['thread_count']!=count
        or role.get('fixed_profile')!=profile['profile_id'] or role.get('placement')!=profile['fixed_placement']):
        raise ValueError('exact source-bound wide thread/allocation role')
    if final and manifest.get('fixed_execution')!=execution_contract(profile):raise ValueError('immutable wide execution contract')

base.meter=meter
base.wide_binding=wide_binding
base.base.meter=meter
base.base.WIDE_BINDING=wide_binding


def worker(budget):
    value=base.worker(budget);value.PINS['native_threaded_wide_package_v1.py']=PARENT_SHA;return value


def prepare(manifest,source_root,profile,job_id,phase,out,budget):
    if phase!='run' or profile not in runtime().SELECTIONS:raise ValueError('fixed wide finite pilot only')
    return worker(json.loads(Path(budget).read_text())).prepare(manifest,source_root,profile,job_id,phase,out,budget)

def prepare_pilot(threads,profile_id,job_id,out):
    """Mechanical runtime-only P8 pilot from its immutable numeric contract."""
    selected=runtime().profile(profile_id);out=Path(out).resolve()
    if threads not in (1,4,8) or type(threads) is not int or out.exists():raise ValueError('fresh bounded declared pilot')
    original=runtime().pinned(runtime().P8_ROLE,runtime().P8_ROLE_SHA)
    m=json.loads(original.read_text());source=out/'role/source/fpga';source.mkdir(parents=True)
    donor=original.parent/'source/fpga'
    for name,pin in m['sources'].items():
        path=donor/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=pin:raise ValueError('unchanged donor source')
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    target=source/runtime().P8_ROLE;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
    m['sources'][runtime().P8_ROLE]=runtime().P8_ROLE_SHA
    config=runtime().base().load('native_thread_config_v1.py',runtime().base().RUNTIME_SHA)
    m['build']=config.configure_build(m['build'],threads)
    m['probe']['expected_json']=config.expected_probe(threads)
    contract={key:json.loads(original.read_text())[key] for key in ('build','probe','steps','sources')}
    m['wide_thread_pilot']=dict(schema='gfn16-fixed-wide-thread-pilot-role-v1',thread_count=threads,
        fixed_profile=profile_id,placement=selected['fixed_placement'],purpose='r75 matched P8 continuous100 source-identical runtime pilot',
        serial_contract=contract,serial_contract_sha256=hashlib.sha256(json.dumps(contract,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest())
    manifest=out/'role/manifest.json';manifest.write_text(json.dumps(m,indent=2)+'\n')
    import importlib.util
    spec=importlib.util.spec_from_file_location('_wide_local_queue_metadata',HERE/'global_queue_v1.py')
    queue=importlib.util.module_from_spec(spec);spec.loader.exec_module(queue)
    reference=queue.provider_capture_ref()
    descriptor=meter().make_budget(selected['host'],3715,str(Path(reference['path']).relative_to(HERE.parent)),
        reference['sha256'],source_identity(m),selected['hardware_profile_sha256'],
        transition_path='results/throughput-20260929/azure-sim-resize-r49-v1/rate-transition-v1.json',
        transition_sha256='c4923266e1fabaeeca7cbf6e5f2444455c299accf5ed89c122927c47ed56ac92')
    budget=out/'budget.json';budget.write_text(json.dumps(descriptor,indent=2)+'\n')
    return prepare(manifest,source,profile_id,job_id,'run',out/'packet',budget)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare')
    for name in ('manifest','source-root','output','budget'):prep.add_argument('--'+name,type=Path,required=True)
    prep.add_argument('--profile',required=True);prep.add_argument('--id',required=True);prep.add_argument('--phase',choices=['run'],required=True)
    run=sub.add_parser('run');run.add_argument('--ticket',type=Path,required=True);run.add_argument('--ticket-sha256',required=True)
    pilot=sub.add_parser('pilot');pilot.add_argument('--threads',type=int,choices=(1,4,8),required=True)
    pilot.add_argument('--profile',default='azure-burst16-thread-wide815-v1');pilot.add_argument('--id',required=True)
    pilot.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.manifest.resolve(),args.source_root.resolve(),args.profile,args.id,args.phase,args.output.resolve(),args.budget.resolve())
    elif args.command=='pilot':result=prepare_pilot(args.threads,args.profile,args.id,args.output)
    else:
        if hashlib.sha256(args.ticket.read_bytes()).hexdigest()!=args.ticket_sha256:raise ValueError('ticket before budget data')
        result=worker(json.loads(args.ticket.read_text())['budget']).run(args.ticket,args.ticket_sha256)
    print(json.dumps(result,indent=2))
