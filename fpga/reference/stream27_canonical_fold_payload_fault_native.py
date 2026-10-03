"""Separate reset/origin/comparator role, not a production payload mutation."""
from . import stream27_canonical_fold_payload_native as normal
import json
from pathlib import Path
from datetime import datetime,timezone

ROOT=normal.ROOT
SELF='reference/stream27_canonical_fold_payload_fault_native.py'
CPP='rtl/tb/stream27_canonical_fold_payload_fault.cpp'
ID='s4-p16-canonical-fold-payload-fault-q1-v1'


def role():
    m,files=normal.role('fault')
    files[CPP]=(ROOT/CPP).read_bytes();files[SELF]=(ROOT/SELF).read_bytes()
    m['build']['cpp_source']=CPP
    m['steps'][0]['expected_stdout']+='FOLD_PAYLOAD_PHASE_RESET_PASS events=5 first_READ_VALUE_PROCESS=3 final_VALUE_PROCESS=2 quiet_edges=40 recovery_signed96_reads=1280 paired_edges=1 payload_zero_assumed=0 os_threads_peak=1\n'
    m['steps'].append(dict(name='fold-payload-comparator-control',argv=['{exe}','--wrong-word'],
        expected_returncode=1,expected_stdout='',expected_stderr='FOLD_PAYLOAD_WRONG_WORD\n'))
    m['sources']={n:normal.sha(raw) for n,raw in files.items()}
    m['fold_payload']['fault_scope']='External framing/live c0/c1 origin checks, five actual phase resets and recovery, deliberate output comparator sensitivity only; no arbitrary payload-FF corruption immunity.'
    m['fold_payload'].update(phase_reset_events=5,phase_reset_recovery_reads=1280,PROCESS_priority_injection_claim=False)
    return m,files


def prepare(output):
    from fpga.tools import candidate_ladder,native_class_package_v2 as package
    out=Path(output).resolve();normal.need(out.is_relative_to(normal.BASE) and not out.exists(),'FRESH_FAULT')
    normal.need(not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')),'PAUSE')
    m,files=role();source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    m['source_root']=str(source);normal.dump(out/'manifest.json',m)
    normal.dump(out/'host-hours.json',candidate_ladder.budget_from_hourly());variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-canonical-fold-payload-fault-'+pair+'-v1';packet=out/('packet-'+pair)
        r=package.prepare(out/'manifest.json',source,profile,worker,'run',packet,out/'host-hours.json')
        ticket=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
          manifest_sha256=normal.sha((packet/'manifest.json').read_bytes()),worker_id=worker,profile=profile,native_root=ticket['native_root'],
          runner='tools/native_class_package_v2.py',runner_sha256=normal.sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
          stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=normal.sha((ROOT/'tools/native_package_v4.py').read_bytes()),
          stager_dependencies=[dict(path=str(ROOT/n),sha256=normal.sha((ROOT/n).read_bytes())) for n in ('tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    logical=dict(schema='gfn16-global-ticket-v1',id=ID,owner='p16-mlab',
       created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
       tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',allowed_hosts=['gfn16-pilot-c4d','aethia'],
       resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
       minimum_ram_rationale='Small N256 paired component reset/negative gate; bounded4GiB, no whole-model inference.',
       est_minutes=5,promotion_bound=False,test_role='deliberate_fault',rtl_readiness=m['rtl_readiness'],packages=variants,
       after=[normal.IDS['normal']],on='PASS_expected_contracts')
    normal.dump(out/'global-ticket.json',logical)
    return dict(id=ID,ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_NATIVE')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output),indent=2))
