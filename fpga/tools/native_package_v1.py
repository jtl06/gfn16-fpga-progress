"""Generic immutable one-job finite queue package. No SSH or provisioning.

One fresh ticket is a finite queue of one; owners sequence tickets after actual
terminal success. Reuses snapshot v2, build identity v1 and queue v1 claims and
evidence helpers. No implicit ELF reuse, candidate-specific runner or promotion.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import shutil
import sys
import tarfile

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
PINS={'native_source_gate_aethia_cpu02_v2.py':'452f9bfdebc535d39c1e493b61378de50720088788698435fd6d11974eb670b3',
 'snapshot_native_sources_v2.py':'db9786b52e0bb53545aa9a800f45dc00beec6663346cfa77f3ec2d0b1c6c5f83',
 'build_identity_v1.py':'b0e1ab77c0fc06a6b0cc958061394dad1f990aa52eb1e76d96922c25225788a2',
 'native_test_queue_v1.py':'f76fd5b98a7a390a8573fbab87e6721ba5d631cddcc7ef7fbd3967b03f8f4fab'}


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load(name):
    path=HERE/name
    if name in PINS:need(sha(path)==PINS[name],'frozen helper pin')
    spec=importlib.util.spec_from_file_location('_package_'+path.stem,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def dump(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def budget_check(value,now=None):
    now=now or datetime.now(timezone.utc)
    stamp=datetime.fromisoformat(value['observed_at'].replace('Z','+00:00'))
    need(stamp.tzinfo is not None and 0<=(now-stamp).total_seconds()<=21600,'fresh six-hour accounting evidence')
    need(value['provider']=='gcp' and value['total_allowance_usd']==100 and value['planning_usd_per_hour']>=1,'fixed existing GCP allowance/rate')
    elapsed=(now-stamp).total_seconds()/3600
    need(value['remaining_after_reserves_usd']>=value['planning_usd_per_hour']*(elapsed+3715/3600),'remaining allowance covers elapsed host burn plus max job and grace')
    need(value['actual_billing'] is False and type(value['source_receipt_sha256']) is str and len(value['source_receipt_sha256'])==64,'explicit conservative accounting receipt')


def prepare(manifest_path,source_root,profile_id,job_id,phase,out,budget_path):
    shared=load('native_shared_v1.py');snapshot=load('snapshot_native_sources_v2.py');identity=load('build_identity_v1.py');queue=load('native_test_queue_v1.py')
    need(not (HERE.parent/'docs/briefs/PAUSE').exists(),'brief PAUSE');queue.identifier(job_id)
    need(profile_id in shared.PROFILES and phase in ('lint','run'),'known profile/phase')
    need(out.is_absolute() and out.resolve()==out and not out.exists(),'fresh canonical package')
    original=json.loads(manifest_path.read_text());snapshot.closed_inputs(source_root,original['sources'])
    budget=json.loads(budget_path.read_text());budget_check(budget)
    profile=shared.PROFILES[profile_id];native=Path(profile['base'])/'jobs'/job_id
    m=json.loads(json.dumps(original));m.update(host=profile['host'],cpu_profile=profile_id,phase=phase,
        source_root=str(native/'capture/source/fpga'),output_parent=str(native/'output'),status='prepared_not_executed')
    helpers={name:(HERE/name).read_bytes() for name in [*PINS,'native_shared_v1.py','native_package_v1.py']}
    for name,raw in helpers.items():m['sources']['tools/'+name]=hashlib.sha256(raw).hexdigest()
    # Every step must have an exact contract or a closed typed validator.
    for step in m['steps']:
        need('validator' in step or ('expected_stdout' in step and 'expected_stderr' in step),'explicit role output contract')
    out.mkdir(parents=True)
    try:
        source=out/'inputs/fpga';source.mkdir(parents=True)
        for name,pin in original['sources'].items():
            target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source_root/name,target)
            need(sha(target)==pin,'input changed during packaging')
        for name,raw in helpers.items():
            target=source/'tools'/name;target.parent.mkdir(exist_ok=True)
            if target.exists():need(target.read_bytes()==raw,'refuse changed existing helper')
            else:target.write_bytes(raw)
        snapshot.closed_inputs(source,m['sources']);dump(out/'manifest.json',m)
        snapshot.capture(out/'manifest.json',source,out/'capture')
        snapshot.closed_inputs(source_root,original['sources'])
        need(json.loads(manifest_path.read_text())==original,'original manifest drift')
        build=identity.build_identity(m,profile)
        ticket=dict(schema='shared-native-ticket-v1',id=job_id,native_root=str(native),profile=profile_id,phase=phase,
            manifest_sha256=sha(out/'manifest.json'),build_key=build['build_key'],max_seconds=3700,
            promotion_allowed=False,failure_policy='stop',budget=budget,
            tools={name:hashlib.sha256(raw).hexdigest() for name,raw in helpers.items()})
        ticket['run_key']=hashlib.sha256(queue.canonical(dict(build_key=build['build_key'],steps=m['steps'],probe=m['probe'],phase=phase,id=job_id))).hexdigest()
        dump(out/'ticket.json',ticket)
        files=['manifest.json','ticket.json','capture/approved-manifest.json','capture/capture.json','capture/source.tar.gz']
        files += [str(x.relative_to(out)) for x in (out/'capture/source/fpga').rglob('*') if x.is_file()]
        with tarfile.open(out/'package.tar.gz','x:gz',format=tarfile.PAX_FORMAT) as archive:
            for name in sorted(files):
                raw=(out/name).read_bytes();entry=tarfile.TarInfo(name);entry.size=len(raw);entry.mode=0o644
                import io
                archive.addfile(entry,io.BytesIO(raw))
        result=dict(status='prepared_not_executed',ticket_sha256=sha(out/'ticket.json'),archive_sha256=sha(out/'package.tar.gz'),
            archive_bytes=(out/'package.tar.gz').stat().st_size,native_root=str(native),build_key=build['build_key'],files=len(files))
        dump(out/'preparation.json',result);return result
    except BaseException as error:
        dump(out/'failure.json',dict(status='failed_package_preserved',error=repr(error)));raise


def run(ticket_path,pin):
    need(sha(ticket_path)==pin,'ticket identity');ticket=json.loads(ticket_path.read_text())
    need(ticket['schema']=='shared-native-ticket-v1' and ticket['failure_policy']=='stop' and ticket['promotion_allowed'] is False and ticket['max_seconds']==3700,'finite nonpromotion ticket')
    root=Path(ticket['native_root']);need(root.resolve()==root and ticket_path==root/'ticket.json','native ticket placement')
    source=root/'capture/source/fpga';need(Path.cwd()==source and Path(__file__).resolve()==source/'tools/native_package_v1.py','native package placement/cwd')
    need(set(ticket['tools'])=={*PINS,'native_shared_v1.py','native_package_v1.py'},'closed shared helper list')
    for name,pin_value in ticket['tools'].items():need(sha(HERE/name)==pin_value,'shared tool drift before import')
    shared=load('native_shared_v1.py');queue=load('native_test_queue_v1.py');identity=load('build_identity_v1.py')
    manifest_path=root/'manifest.json';need(sha(manifest_path)==ticket['manifest_sha256'],'manifest binding')
    m=json.loads(manifest_path.read_text());profile=shared.PROFILES[ticket['profile']]
    queue.identifier(ticket['id']);need(root==Path(profile['base'])/'jobs'/ticket['id'],'fixed ticket namespace')
    need(m['cpu_profile']==ticket['profile'] and m['phase']==ticket['phase'] and Path(m['source_root'])==source,'manifest ticket profile')
    shared.parent(ticket['profile']).check_sources(source,m['sources'])
    need(identity.build_identity(m,profile)['build_key']==ticket['build_key'],'exact build identity')
    expected_key=hashlib.sha256(queue.canonical(dict(build_key=ticket['build_key'],steps=m['steps'],probe=m['probe'],phase=ticket['phase'],id=ticket['id']))).hexdigest()
    need(ticket['run_key']==expected_key,'exact duplicate-claim key')
    budget_check(ticket['budget']);shared.execution_limits(profile)
    need(not (Path(profile['base'])/'PAUSE').exists(),'host PAUSE')
    registry=Path(profile['base'])/'claims';need(registry.is_dir() and registry.resolve()==registry,'existing claim registry')
    need(not (root/'queue-report.json').exists() and not (root/'output/native').exists(),'fresh job outputs')
    queue.claim(registry,ticket['run_key'],dict(ticket_sha256=pin,id=ticket['id'],status='claimed_no_retry'))
    report=dict(status='running',ticket_sha256=pin,promotion_allowed=False,profile=ticket['profile'])
    try:
        result=shared.execute(manifest_path,ticket['manifest_sha256'],root/'output/native')
        for name,digest in result['artifacts'].items():need(sha(root/'output/native'/name)==digest,'terminal artifact hash')
        queue.archive_inventory(root/'output/native/sources.tar.gz',m['sources'])
        need(sha(manifest_path)==ticket['manifest_sha256'],'terminal manifest drift')
        shared.parent(ticket['profile']).check_sources(source,m['sources'])
        report.update(status='needs_independent_review',worker_status=result['status'],report_sha256=sha(root/'output/native/report.json'))
        return report
    except BaseException as error:report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:dump(root/'queue-report.json',report)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare')
    for name in ('manifest','source-root','output','budget'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--profile',required=True);p.add_argument('--id',required=True);p.add_argument('--phase',choices=('lint','run'),required=True)
    p=sub.add_parser('run');p.add_argument('--ticket',type=Path,required=True);p.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.manifest.resolve(),args.source_root.resolve(),args.profile,args.id,args.phase,args.output.resolve(),args.budget.resolve())
    else:result=run(args.ticket,args.ticket_sha256)
    print(json.dumps(result,indent=2))
