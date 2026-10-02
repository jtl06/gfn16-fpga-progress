"""Data-only wide stage bound to the corrected callable/live-guard runtime/package."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='20581efa4daadb13ec986224ed5fc1c86df339e5508fd400a5f09340482a83f9'
PACKAGE_SHA='8d8585935a42241b85813a8db6204b02ce5aa2a23559e91a4911489a8de410e6'
EXECUTOR_SHA='71924875229a549fbcfb8cd52252406a8610d40946597e1d8b2470ae843466d7'


def module():
    raw=(HERE/'native_threaded_wide_stage_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen safe wide stage')
    text=raw.decode().replace('native_threaded_wide_package_v1.py','native_threaded_wide_package_v3.py').replace('9632fc4f55038052add52cc8bdce1cdc2398093baf5d9561677637cdad9b2d56',PACKAGE_SHA)
    text=text.replace('native_threaded_wide_v1.py','native_threaded_wide_v3.py').replace('75bd5bae7ffa549db530c02a46c527d5d996391980385e2a28c3d5c39adac9a1',EXECUTOR_SHA)
    value=types.ModuleType('_wide_callable_stage');value.__file__=str(Path(__file__).resolve())
    exec(compile(text,'[wide callable source stage]','exec'),value.__dict__)
    return value


base=module()
HARDWARE=base.HARDWARE
HARDWARE_SHA=base.HARDWARE_SHA
OVERLAY=base.OVERLAY
OVERLAY_SHA=base.OVERLAY_SHA
def profile_from_payload(payload,ticket,sources):
    need=base.need
    for name,pin in {'tools/native_threaded_wide_package_v3.py':PACKAGE_SHA,
        'tools/native_threaded_wide_v3.py':EXECUTOR_SHA,OVERLAY:OVERLAY_SHA,HARDWARE:HARDWARE_SHA}.items():
        need(sources.get(name)==pin,'exact wide source controls/caps')
    need(ticket['profile'] in ('azure-burst16-thread-wide07-v1','azure-burst16-thread-wide815-v1'),
         'two observed physical groups only')
    hardware=json.loads(payload['capture/source/fpga/'+HARDWARE]);pairs=hardware.pop('profiles')
    overlay=json.loads(payload['capture/source/fpga/'+OVERLAY]);template=overlay['profiles']['azure-burst16-thread-wide07-v1']
    name=overlay['topology_observation'];need(sources.get(name)==overlay['topology_observation_sha256'],'observed topology source')
    observed=json.loads(payload['capture/source/fpga/'+name])
    first=0 if ticket['profile'].endswith('wide07-v1') else 8;cpus=list(range(first,first+8))
    ids=['azure-burst16-static'+str(n)+str(n+1)+'-v1' for n in range(first,first+8,2)]
    need([cpu for key in ids for cpu in pairs[key]]==cpus,'all four real constituent pairs')
    physical=[[observed['cpus'][str(cpu)][key] for key in ('physical_package_id','core_id')] for cpu in cpus]
    need(len(set(map(tuple,physical)))==8 and all(observed['cpus'][str(cpu)]['thread_siblings_list']==str(cpu) for cpu in cpus),
         'eight physical cores, no SMT inflation')
    l3=observed['cpus'][str(first)]['l3'];need(len(l3)==1 and all(observed['cpus'][str(cpu)]['l3']==l3 for cpu in cpus),'one observed cache domain')
    placement=dict(id='burst16-wide'+('07' if first==0 else '815')+'-v1',lane_ids=ids,cpus=cpus)
    allocation=dict(cpus=cpus,physical_cores=physical,cpu_quota_percent=800,compile_workers=2,memory_bytes=8<<30)
    contract=dict(schema='fixed-wide-execution-contract-v1',profile_id=ticket['profile'],profile_source=OVERLAY,profile_sha256=OVERLAY_SHA,
        hardware_profile_source=HARDWARE,hardware_profile_sha256=HARDWARE_SHA,topology_observation=name,
        topology_observation_sha256=overlay['topology_observation_sha256'],observed_l3=l3[0],runtime_allocation=allocation,placement=placement)
    manifest=json.loads(payload['manifest.json'])
    need(ticket.get('placement')==placement and ticket.get('fixed_execution')==contract and manifest.get('fixed_execution')==contract,
         'source-bound allocation in ticket and manifest')
    need(manifest['wide_thread_pilot']['placement']==placement and manifest['build']['runtime_threads'] in (1,2,4,8),
         'finite explicit model thread count')
    need(template['memory_bytes']==8<<30 and template['cpu_quota_percent']==800 and template['compile_workers']==2,
         'unchanged resource caps template')
    hardware.update(template,cpus=cpus,observed_l3=l3[0])
    return hardware

base.profile_from_payload=profile_from_payload
worker=base.worker
stage=base.stage


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    command=sub.add_parser('stage');command.add_argument('--archive',type=Path,required=True)
    command.add_argument('--archive-sha256',required=True);command.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args();print(json.dumps(stage(args.archive,args.archive_sha256,args.ticket_sha256),indent=2))
