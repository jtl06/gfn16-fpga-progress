"""Private genuine DIGIT-before-INTERNAL origin plus bounded FF diagnostic."""
from . import stream27_canonical_fold_payload_fault_native as fault
from . import stream27_canonical_fold_payload_native as normal
from pathlib import Path
import json
from datetime import datetime,timezone

ROOT=normal.ROOT
SELF='reference/stream27_canonical_fold_payload_priority_native.py'
CPP='rtl/tb/stream27_canonical_fold_payload_priority.cpp'
ID='s4-p16-canonical-fold-payload-priority-q1-v1'
HEADER='V'+normal.TOP+'___024root.h'


def role():
    # Header names/widths were read from the ACTUAL prior normal build.
    import tarfile
    archive=ROOT/'queue/evidence'/normal.IDS['normal']/'attempt-0/collected/output/native/generated-sources.tar.gz'
    with tarfile.open(archive) as t:header=t.extractfile(HEADER).read().decode()
    for label in ('parent','local'):
        for member in ('correction0','state','stored_digit_bad','process_bad','process_code'):
            normal.need(normal.TOP+'__DOT__'+label+'_dut__DOT__'+member in header,'ACTUAL_GENERATED_FIELD')
    normal.need(normal.TOP+'__DOT__parent_dut__DOT__value' in header,'ACTUAL_PARENT_VALUE')
    for member in ('fold_q_payload','fold_remainder_payload'):
        normal.need(normal.TOP+'__DOT__local_dut__DOT__'+member in header,'ACTUAL_CANDIDATE_PAYLOAD')
    normal.need(normal.TOP+'__DOT__local_dut__DOT__fold_range_payload' in header,'ACTUAL_FOLD_PAYLOAD_FIELD')
    m,files=normal.role('fault');files[CPP]=(ROOT/CPP).read_bytes();files[SELF]=(ROOT/SELF).read_bytes()
    m['build']['cpp_source']=CPP
    m['steps']=[dict(name='fold-payload-priority',argv=['{exe}','--priority'],expected_returncode=0,
       expected_stdout='FOLD_PAYLOAD_PRIORITY_PASS protocol_digit_internal_cases=1 digit_code=6 correction_FF_internal_cases=4 internal_code=7 signed_extrema=1 exact_PROCESS_origin=1 recovery_signed96_reads=256 paired_edges=1 production_mutated=0 simulation_only=1 os_threads_peak=1\n',expected_stderr='')]
    m['sources']={n:normal.sha(raw) for n,raw in files.items()}
    m['fold_payload'].update(priority_scope='One genuine LOADbase5000→BEGINbase599 double fault gives DIGIT6; four identical correction0 FF mutations after legal BEGIN/before VALUE give INTERNAL7. No arbitrary memory/FF corruption immunity.',
        generated_header_sha256=normal.sha(header.encode()),production_SV_unchanged=True)
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
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-canonical-fold-payload-priority-'+pair+'-v1';packet=out/('packet-'+pair)
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
