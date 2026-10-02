"""Thin source-role emitter for the existing native and standing-fit queues.

Owners declare real contracts, not package/profile recipes. This tool never
executes HDL, invents missing ladder stages, or creates another scheduler.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
from fpga.tools import global_queue_v1 as queue

STAGES={'aw5','aw8','typed_mutant','aw16','e2e1','pilot100','continuous1000'}
FIT_STAGES={'field_fit','whole_fit'}
FLAGS={'CANONICAL_PIPE_STAGES':{1}}
PIPE='genefer_stream27_canonical_image_pipe_v1.sv'
LOCALBASE='genefer_stream27_canonical_image_localbase_v1.sv'


def need(ok,why):
    if not ok:raise ValueError('candidate ladder: '+why)


def read_reference(ref):
    need(type(ref) is dict and set(ref)=={'path','sha256'},'exact manifest reference')
    path=Path(ref['path'])
    need(path.is_absolute() and path.resolve()==path and path.is_relative_to(ROOT)
         and queue.sha(path)==ref['sha256'],'contained immutable manifest')
    return path,json.loads(path.read_text())


def plan(path,flags=None):
    path=Path(path).resolve();value=json.loads(path.read_text())
    need(value.get('schema')=='gfn16-candidate-ladder-v1','declared ladder schema')
    queue.need(queue.ID.fullmatch(value['candidate_id']) and queue.ID.fullmatch(value['owner']),'candidate/owner id')
    selected=value.get('flags',{})
    if flags is not None:need(flags==selected,'CLI flags equal the declared source contract')
    need(selected and all(name in FLAGS and type(setting) is int and setting in FLAGS[name]
                         for name,setting in selected.items()),'unsupported shared-shell flag/interface')
    need(value.get('track')=='S','initial real adapter is Track S canonical pipe only')
    if value.get('rtl_readiness'):
        need(value['rtl_readiness']['candidate_id']==value['candidate_id'],'one explicit design readiness identity')
    roles=value.get('roles',[])
    need(type(roles) is list and roles,'at least one real runnable role; missing faults do not hold normal')
    ids=set();prepared=[]
    for row in roles:
        need(queue.ID.fullmatch(row['id']) and row['id'] not in ids,'unique declared role id');ids.add(row['id'])
        need(row['stage'] in STAGES and row['test_role'] in ('normal','deliberate_fault'),'explicit stage/test role')
        manifest_path,manifest=read_reference(row['manifest'])
        source=Path(row['source_root'])
        need(source.is_absolute() and source.resolve()==source and source.is_relative_to(ROOT),'contained source snapshot')
        for name,pin in manifest['sources'].items():
            child=source/name
            need(not Path(name).is_absolute() and '..' not in Path(name).parts
                 and child.resolve()==child and queue.sha(child)==pin,'exact closed role source: '+name)
        build=manifest['build'];parameters=build.get('parameters',{})
        leaves={Path(name).name for name in build['sv_sources']}
        localbase=parameters.get('CANONICAL_LOCALBASE',0)
        need(type(localbase) is int and localbase in (0,1),'exact canonical-localbase selector')
        need((LOCALBASE in leaves and PIPE not in leaves and parameters.get('CANONICAL_PIPE_STAGES')==1)
             if localbase else (PIPE in leaves and LOCALBASE not in leaves),
             'real registered flag-bound canonical-pipe/localbase leaf')
        need(build['top']=='genefer_stream27_canonical_image_pipe_v1'
             or parameters.get('CANONICAL_PIPE_STAGES')==1,'real leaf or flag-bound shared-shell top')
        need(parameters.get('AW') in (5,8,16) and parameters.get('P') in (8,16),'declared native geometry')
        need(manifest['steps'] and all(step.get('expected_stdout') is not None or step.get('validator')
                                      for step in manifest['steps']),'explicit typed outcome contracts')
        if row['test_role']=='normal':
            need(all(step.get('expected_returncode',0)==0 for step in manifest['steps']),'normal runs separately from newly authored faults')
        if row['stage']=='typed_mutant':
            need(row['test_role']=='deliberate_fault' and any(step.get('expected_returncode',0)!=0
                 for step in manifest['steps']),'a declared typed-mutant rejection contract, not a relabelled normal PASS')
        allocation=row.get('resources',dict(cores=2,threads=1,ram_gib=8,scratch_gib=4))
        need(allocation in (dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
                            dict(cores=2,threads=1,ram_gib=24,scratch_gib=4)),'existing serial pair allocation only')
        minimum=row.get('minimum_ram_gib',allocation['ram_gib'])
        need(type(minimum) in (int,float) and minimum in (4,8,24) and minimum<=allocation['ram_gib'],'explicit compatible minimum RAM')
        if minimum<allocation['ram_gib']:need(bool(row.get('minimum_ram_rationale')),'owner rationale for smaller exploratory cap')
        if row['stage']=='continuous1000':need('runtime_duration' in manifest,'actual source-bound duration contract, not a placeholder')
        if value.get('rtl_readiness'):
            queue.validate_rtl_readiness(dict(rtl_readiness=value['rtl_readiness']),manifest)
        prepared.append((row,manifest_path,source,manifest,allocation))
    for row,*_ in prepared:
        need(type(row.get('after',[])) is list and all(type(item) is str and queue.ID.fullmatch(item)
             for item in row.get('after',[])),'explicit dependency IDs, no inferred mutant serialization')
    return value,prepared


def emit_fits(value):
    """Existing standing-fit intake, only after actual declared native data."""
    from fpga.tools import fit_submit
    submissions=[];deferred=[]
    for row in value.get('fits',[]):
        need(row.get('stage') in FIT_STAGES,'known field/whole fit stage')
        project=Path(row['project']).resolve()
        need(project.is_relative_to(ROOT) and project.is_dir(),'existing immutable fit project')
        files={p.name for p in (project/'rtl').glob('*.sv')}
        need(PIPE in files,'real registered flag leaf in fit project')
        requires=row.get('requires',[])
        need(requires,'explicit actual native prerequisite contracts for fits')
        if any(not Path(item['path']).exists() for item in requires):
            deferred.append(dict(id=row['id'],reason='actual native gate evidence is not collected yet'))
            continue
        result=fit_submit.submit(ROOT/'queue/standing-fits',row['id'],project,
            row.get('period_ns','10'),row.get('seed',1),row.get('slot_shapes',dict(azure4=['a','b','c','d'],aws6=['a','b'])),
            'whole_core' if row['stage']=='whole_fit' else 'component_probe',row['source_contract'],
            priority=row.get('priority',20),requires=requires,after=row.get('after',[]),track='S',
            purpose='whole' if row['stage']=='whole_fit' else 'sizing')
        submissions.append(dict(id=row['id'],ticket=result))
    return submissions,deferred


def budget_from_hourly():
    cached=queue.cached_provider_cost('gcp')
    admission=cached.get('admission',{})
    need(admission.get('host_id')=='gcp-c4d','authentic GCP packaging quote exists; execution is checked separately')
    path=ROOT/'queue/provider-cost-status/gcp.json'
    return dict(provider='gcp',observed_at=admission['observed_at_utc'],total_allowance_usd=100,
                planning_usd_per_hour=admission['hourly_rate_usd'],
                remaining_after_reserves_usd=admission['remaining_total_after_storage_usd'],
                actual_billing=False,source_receipt_sha256=queue.sha(path))


def emit(path,output,flags=None):
    value,roles=plan(path,flags)
    out=Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(),'fresh project output; old evidence is never overwritten')
    out.mkdir(parents=True)
    budget=out/'host-hours.json';queue.atomic(budget,budget_from_hourly())
    submissions=[]
    for row,manifest_path,source,manifest,allocation in roles:
        token=hashlib.sha256((row['id']+'|'+str(out)+'|'+queue.sha(manifest_path)).encode()).hexdigest()[:16]
        native_id='ladder-'+row['id'][:40]+'-'+token
        if row['stage']=='continuous1000':
            from fpga.tools import native_long_package_v3 as builder
            runner='tools/native_long_package_v3.py';stager='tools/native_long_stage_v3.py'
            dependencies=['tools/native_long_stage_v1.py','tools/native_package_v3.py','tools/native_package_v2.py'];seconds=10800
        elif allocation['ram_gib']==24:
            from fpga.tools import native_class_package_gcp24_v1 as builder
            runner='tools/native_class_package_gcp24_v1.py';stager='tools/native_stage_gcp24_v1.py'
            dependencies=['tools/native_package_v3.py','tools/native_package_v2.py'];seconds=3700
        else:
            from fpga.tools import native_class_package_v2 as builder
            runner='tools/native_class_package_v2.py';stager='tools/native_package_v4.py'
            dependencies=['tools/native_package_v3.py','tools/native_package_v2.py'];seconds=3700
        profile='gcp-c4d-static24g01-v1' if allocation['ram_gib']==24 else 'gcp-c4d-static01-v1'
        target=out/row['id'];packet=target/'packet'
        builder.prepare(manifest_path,source,profile,native_id,'run',packet,budget)
        ticket=json.loads((packet/'ticket.json').read_text());packed=json.loads((packet/'manifest.json').read_text())
        package=dict(archive=str(packet/'package.tar.gz'),sha256=queue.sha(packet/'package.tar.gz'),
            ticket_sha256=queue.sha(packet/'ticket.json'),manifest_sha256=queue.sha(packet/'manifest.json'),
            worker_id=native_id,profile=profile,native_root=ticket['native_root'],runner=runner,
            runner_sha256=packed['sources'][runner],stager=str(ROOT/stager),stager_sha256=queue.sha(ROOT/stager),
            stager_dependencies=[dict(path=str(ROOT/name),sha256=queue.sha(ROOT/name)) for name in dependencies],max_seconds=seconds)
        logical=dict(schema='gfn16-global-ticket-v1',id=row['id'],owner=value['owner'],created=queue.stamp(),
            priority=row.get('priority','P1'),kind='sim',needs='verilator',test_role=row['test_role'],
            tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=allocation,
            minimum_ram_gib=row.get('minimum_ram_gib',allocation['ram_gib']),est_minutes=row.get('est_minutes',10),
            promotion_bound=False,after=row.get('after',[]),packages=[package],
            candidate_id=value['candidate_id'],candidate_ladder=dict(candidate_id=value['candidate_id'],flags=value['flags'],stage=row['stage'],
                descriptor=dict(path=str(Path(path).resolve()),sha256=queue.sha(path))))
        for name in ('minimum_ram_rationale','allowed_hosts'):
            if name in row:logical[name]=row[name]
        if value.get('rtl_readiness'):logical['rtl_readiness']=value['rtl_readiness']
        queue.validate(logical)
        destination=target/'global-ticket.json';queue.atomic(destination,logical)
        # The existing public CLI owns submission locks, exact dependency
        # binding, uniqueness and all admitted-host package expansion.
        result=queue.command([sys.executable,'-B',str(ROOT/'tools/global_queue_v1.py'),'submit',str(destination)],
                             target,'public-submit',timeout=300)
        submissions.append(json.loads(queue.output(result)))
    fits,deferred=emit_fits(value)
    declared={row['stage'] for row,*_ in roles}|{row['stage'] for row in value.get('fits',[])}
    result=dict(status='declared_roles_submitted_not_native_pass',candidate_id=value['candidate_id'],
        submissions=submissions,fit_submissions=fits,deferred_fits=deferred,undeclared_stages=sorted((STAGES|FIT_STAGES)-declared),
        remaining_contracts='No synthetic test or promotion PASS is created for undeclared stages.')
    queue.atomic(out/'receipt.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--flag',action='append',default=[])
    parser.add_argument('--output',type=Path)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args();flags=None
    if args.flag:
        flags={}
        for item in args.flag:
            name,setting=item.split('=',1);need(name not in flags,'unique CLI flag');flags[name]=int(setting)
    if args.check:
        value,roles=plan(args.candidate,flags)
        print(json.dumps(dict(status='SOURCE_plan_only_not_native',candidate_id=value['candidate_id'],roles=[x[0]['id'] for x in roles])))
    else:
        need(args.output is not None,'fresh output required')
        print(json.dumps(emit(args.candidate,args.output,flags),indent=2))


if __name__=='__main__':main()
