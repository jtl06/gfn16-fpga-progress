"""Safe data-only staging for one exact eight-physical short-pilot placement."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PARENT_SHA='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
PACKAGE_SHA='9632fc4f55038052add52cc8bdce1cdc2398093baf5d9561677637cdad9b2d56'
EXECUTOR_SHA='75bd5bae7ffa549db530c02a46c527d5d996391980385e2a28c3d5c39adac9a1'
OVERLAY='cloud/azure-burst16-thread-wide-profiles-v1.json'
OVERLAY_SHA='6991626ec38018943ff4ff5c88eb7808301ef195d7e48686cbbbd4e4cc135808'
HARDWARE='cloud/azure-burst16-static-profiles-v1.json'
HARDWARE_SHA='eef2a816c7fc6ae5e53919b24b2bb135a16808d7ef7ccb7341395b0c030b596d'


def need(ok,why):
    if not ok:raise ValueError(why)


def profile_from_payload(payload,ticket,sources):
    for name,pin in {'tools/native_threaded_wide_package_v1.py':PACKAGE_SHA,'tools/native_threaded_wide_v1.py':EXECUTOR_SHA,OVERLAY:OVERLAY_SHA,HARDWARE:HARDWARE_SHA}.items():
        need(sources.get(name)==pin,'exact fixed-wide source closure')
    need(ticket['profile']=='azure-burst16-thread-wide07-v1','one measured fixed wide placement')
    data=json.loads(payload['capture/source/fpga/'+HARDWARE]);profiles=data.pop('profiles')
    overlay=json.loads(payload['capture/source/fpga/'+OVERLAY]);selected=overlay['profiles'][ticket['profile']]
    need(overlay['hardware_profile_source']==HARDWARE and overlay['hardware_profile_sha256']==HARDWARE_SHA,'same hardware separate from overlay')
    if isinstance(profiles[overlay['base_profile']],dict):data.update(profiles[overlay['base_profile']])
    else:data['cpus']=profiles[overlay['base_profile']]
    data.update(selected)
    observation_name=overlay['topology_observation']
    need(sources.get(observation_name)==overlay['topology_observation_sha256'],'exact wide topology observation')
    observation=json.loads(payload['capture/source/fpga/'+observation_name])
    placement=dict(id='burst16-wide07-v1',lane_ids=selected['constituent_profiles'],cpus=list(range(8)))
    allocation=dict(cpus=list(range(8)),physical_cores=[[observation['cpus'][str(cpu)][key] for key in ('physical_package_id','core_id')] for cpu in range(8)],cpu_quota_percent=800,compile_workers=2,memory_bytes=8<<30)
    contract=dict(schema='fixed-wide-execution-contract-v1',profile_id=ticket['profile'],profile_source=OVERLAY,profile_sha256=OVERLAY_SHA,
      hardware_profile_source=HARDWARE,hardware_profile_sha256=HARDWARE_SHA,topology_observation=overlay['topology_observation'],
      topology_observation_sha256=overlay['topology_observation_sha256'],observed_l3=selected['observed_l3'],runtime_allocation=allocation,placement=placement)
    manifest=json.loads(payload['manifest.json'])
    need(ticket.get('placement')==placement and ticket.get('fixed_execution')==contract and manifest.get('fixed_execution')==contract,'immutable source-bound wide allocation/cache contract')
    need(manifest.get('wide_thread_pilot',{}).get('placement')==placement and manifest['build'].get('runtime_threads') in (2,4,8),'fixed short-pilot role only')
    need(data['cpus']==list(range(8)) and data['memory_bytes']==8<<30 and data['cpu_quota_percent']==800,'fixed wide caps')
    return data


def worker():
    path=HERE/'native_package_v3.py'
    need(hashlib.sha256(path.read_bytes()).hexdigest()==PARENT_SHA,'frozen safe data stage')
    spec=importlib.util.spec_from_file_location('_wide_safe_stage_parent',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.profile_from_payload=profile_from_payload
    return module.worker()


def stage(archive,archive_sha,ticket_sha):return worker().stage(archive,archive_sha,ticket_sha)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    command=sub.add_parser('stage');command.add_argument('--archive',type=Path,required=True)
    command.add_argument('--archive-sha256',required=True);command.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args();print(json.dumps(stage(args.archive,args.archive_sha256,args.ticket_sha256),indent=2))
