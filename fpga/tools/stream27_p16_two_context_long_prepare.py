"""Thin R84 role/evidence binding to the EXISTING measured long package path.

No runner, scheduler, profile or duration-policy implementation lives here.
The public queue remains sole dispatch authority; this emits one P1 ticket.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))


def prepare(output):
    from fpga.reference import stream27_p16_two_context_continuous as role
    from fpga.tools import native_long_package_v3 as package
    from fpga.tools import global_queue_v1 as queue
    from fpga.cloud import host_hours_azure_signed_v1 as meter
    out=Path(output).resolve()
    role.need(out.is_relative_to(ROOT) and not out.exists(), 'FRESH_LONG_PACKET')
    role.need(not any((ROOT/n).exists() for n in ('docs/briefs/PAUSE','queue/PAUSE')), 'PAUSE')
    original=ROOT/'artifacts/s4-p16-c2-explicit-continuous1000-role-v1'
    m=json.loads((original/'manifest.json').read_text())
    role.need(m['sources'][role.SELF]==role.sha((ROOT/role.SELF).read_bytes()),'FROZEN_CONTINUOUS_HELPER')
    out.mkdir(parents=True)
    evidence=dict(forecast=original/'forecast.json',pilot_manifest=role.PILOT_MANIFEST,
                  pilot_report=role.PILOT_REPORT,pilot_gate=role.PILOT_GATE)
    bound=package.bind_role(original/'manifest.json',original/'source/fpga',evidence,out/'bound')
    bound_manifest=Path(bound['manifest']);bound_source=Path(bound['source_root'])
    profile_id='azure-burst16-thread-wide815-v1'
    selected=package.runtime.profile(profile_id)
    reference=queue.provider_capture_ref()
    budget=meter.make_budget(selected['host'],10815,str(Path(reference['path']).relative_to(ROOT)),reference['sha256'],
        package.source_identity(json.loads(bound_manifest.read_text())),selected['hardware_profile_sha256'],
        transition_path='results/throughput-20260929/azure-sim-resize-r49-v1/rate-transition-v1.json',
        transition_sha256='c4923266e1fabaeeca7cbf6e5f2444455c299accf5ed89c122927c47ed56ac92')
    role.dump(out/'budget.json',budget)
    packet=out/'packet-815';worker='s4-p16-c2-explicit-continuous1000-wide815-v1'
    package.prepare(bound_manifest,bound_source,profile_id,worker,'run',packet,out/'budget.json')
    native=json.loads((packet/'ticket.json').read_text());packed=json.loads((packet/'manifest.json').read_text())
    names=('tools/native_long_stage_v1.py','tools/native_package_v3.py','tools/native_package_v2.py',
           'tools/native_threaded_wide_stage_v3.py','tools/native_threaded_wide_stage_v1.py')
    variant=dict(archive=str(packet/'package.tar.gz'),sha256=queue.sha(packet/'package.tar.gz'),
        ticket_sha256=queue.sha(packet/'ticket.json'),manifest_sha256=queue.sha(packet/'manifest.json'),
        worker_id=worker,profile=profile_id,native_root=native['native_root'],
        runner='tools/native_long_package_v3.py',runner_sha256=packed['sources']['tools/native_long_package_v3.py'],
        stager=str(ROOT/'tools/native_long_stage_v3.py'),stager_sha256=queue.sha(ROOT/'tools/native_long_stage_v3.py'),
        stager_dependencies=[dict(path=str(ROOT/name),sha256=queue.sha(ROOT/name)) for name in names],
        max_seconds=10800,placement=selected['fixed_placement'])
    logical=dict(schema='gfn16-global-ticket-v1',id='s4-p16-c2-explicit-continuous1000-q3-v1',
        owner='merged-ntt-model',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='azure-burst16-verilator5032-gcc13-python312-v1',
        resources=dict(cores=8,threads=8,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,
        minimum_ram_rationale='Same own measured C2 eight-thread allocation; count/program header grows only. EightGiB cap unchanged, no OOM guarantee.',
        est_minutes=180,promotion_bound=False,test_role='normal',rtl_readiness=m['rtl_readiness'],
        after=['s4-p16-c2-explicit-own100-threadpilot-q2-v1'],on='PASS_expected_contracts',
        placement_from='s4-p16-c2-explicit-own100-threadpilot-q2-v1',packages=[variant])
    role.dump(out/'global-ticket.json',logical)
    role.dump(out/'preparation.json',dict(status='prepared_not_native',id=logical['id'],
        admission=bound['admission'],packet=str(packet),public_ticket=str(out/'global-ticket.json')))
    return dict(id=logical['id'],ticket=str(out/'global-ticket.json'),status='prepared_not_native')


def refresh_stager(ticket, output):
    """Unaccepted descriptor successor only; preserve worker package and ID."""
    from fpga.reference import stream27_p16_two_context_continuous as role
    from fpga.tools import global_queue_v1 as queue
    ticket,output=Path(ticket).resolve(),Path(output).resolve()
    role.need(ticket.is_relative_to(ROOT) and output.is_relative_to(ROOT) and not output.exists(),
              'FRESH_STAGER_METADATA_SUCCESSOR')
    value=json.loads(ticket.read_text())
    role.need(value['id']=='s4-p16-c2-explicit-continuous1000-q3-v1', 'EXACT_OWN_LOGICAL_ID')
    for name in ('pending','running','done'):
        role.need(not (ROOT/'queue'/name/(value['id']+'.json')).exists(), 'UNACCEPTED_ONLY')
    for item in value['packages']:
        role.need(queue.sha(Path(item['archive']))==item['sha256'], 'UNCHANGED_SOURCE_ARCHIVE')
        role.need(Path(item['stager']).resolve()==ROOT/'tools/native_long_stage_v3.py', 'EXISTING_STAGER_ONLY')
        role.need(all(queue.sha(Path(row['path']))==row['sha256'] for row in item['stager_dependencies']),
                  'UNCHANGED_EXTERNAL_DEPENDENCIES')
        item['stager_sha256']=queue.sha(Path(item['stager']))
        dependency=ROOT/'tools/native_threaded_wide_stage_v1.py'
        if not any(Path(row['path'])==dependency for row in item['stager_dependencies']):
            item['stager_dependencies'].append(dict(path=str(dependency),sha256=queue.sha(dependency)))
    value['placement_from']='s4-p16-c2-explicit-own100-threadpilot-q2-v1'
    role.dump(output,value)
    return dict(id=value['id'],ticket=str(output),status='metadata_only_unaccepted_successor')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--refresh-ticket',type=Path);args=parser.parse_args()
    result=refresh_stager(args.refresh_ticket,args.output) if args.refresh_ticket else prepare(args.output)
    print(json.dumps(result,indent=2))
