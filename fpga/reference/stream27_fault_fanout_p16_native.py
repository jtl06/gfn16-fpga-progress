"""Separate P16 replica normal-first source cohort, actual CORR_SERIAL2.

Frozen P8 packages/binder are untouched. The independent nine-case field NTT
oracle and actual warm calendar are inherited; existing native packaging and
queues provide execution. Full-N numerical work never runs on the Mac.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from . import stream27_shared_field_flags as donor
from . import stream27_fault_fanout_p16_bind as binding
from . import stream27_term_select_native as shared

ROOT=donor.ROOT
SELF='reference/stream27_fault_fanout_p16_native.py'
CPP='rtl/tb/stream27_fault_fanout_p16_normal.cpp'
need,sha,dump=shared.need,shared.sha,shared.dump
RTL_READY='2026-10-01T23:04:07Z'


def role(aw=8,field=1):
    need(aw in (8,16) and field in (0,1,2),'S4_P16_FAULT_NORMAL_GEOMETRY')
    b=binding.bind(donor.prepare(1<<aw,16,field,mode='warm_signed',corr_serial_bfs=2,allow_full_constants=aw==16))
    g=b['geometry'];rows=g['rows'];cpp,header=shared.compile_bench(b,field)
    label=f'S4_P16_FAULT_FANOUT_NORMAL aw={aw} p=16 field={field} corr_serial_bfs=2'
    need(cpp.count('S4_SHARED_AW16_PASS')==1,'S4_P16_FAULT_NORMAL_LABEL');cpp=cpp.replace('S4_SHARED_AW16_PASS',label,1)
    ledgers=[shared.lease_ledger(starts,g['sink_accept'],rows) for starts in ([0],[0,g['warm_interval']],[0,g['warm_interval']+16])]
    need(all(not x['rejected'] for x in ledgers),'S4_P16_FAULT_NORMAL_CALENDAR')
    counts=dict(cases=9,frames=9,physical_rows=9*rows,physical_words=9*(1<<aw),eligible_rows=7*rows,commits=7*rows,peak_owners=max(x['peak'] for x in ledgers))
    footer=label+' '+' '.join(f'{key}={value}' for key,value in counts.items())+'\n'
    files={'rtl/'+name:text.encode() for name,text in b['files'].items()}
    files.update({CPP:cpp.encode(),shared.HEADER:header.encode(),shared.REFERENCE:(ROOT/shared.REFERENCE).read_bytes()})
    for name in b['source_dependencies']+[SELF,shared.SELF,'reference/stream27_shared_warm_full_native_v1.py',
                                           'reference/stream27_p8_warm_native_v2.py',shared.BENCH]:
        files['lineage/'+name]=(ROOT/name).read_bytes()
    snapshot={'rtl/'+name:pin for name,pin in b['generated_sha256'].items()}
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='/unbound/p16-fault/fpga',output_parent='/unbound/p16-fault/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=CPP,
                   parameters={key:value for key,value in b['parameters'].items() if key!='FIELD'},cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='p16-corr2-replica-normal',argv=['{exe}'],expected_returncode=0,expected_stdout=footer,expected_stderr='')],
        test_role='normal',fault_fanout=dict(binding=b['fault_fanout'],geometry=g,counts=counts,scope='One actual P16 C1 field/corr2 NTT/calendar/reset/origin tail; no physical/whole qualification.'))
    return m,files,snapshot


def prepare(output,aw,field,budget):
    from fpga.tools import native_class_package_v2 as package
    output=Path(output).resolve()
    need(not output.exists() and not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),'S4_P16_FAULT_FRESH_PAUSE')
    m,files,snapshot=role(aw,field);source=output/'input/source/fpga';source.mkdir(parents=True)
    m['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=f's4-p16-fault-fanout-aw{aw}-f{field}-c2-v1',
        candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=RTL_READY,source_snapshot=snapshot)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m)
    qid=f's4-p16-fault-fanout-aw{aw}-f{field}-c2-normal-q1-v1';profile='gcp-c4d-static01-v1';worker=qid+'-01';packet=output/'packet-01'
    r=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
    variant=dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
        manifest_sha256=sha((packet/'manifest.json').read_bytes()),native_root=r['native_root'],runner='tools/native_class_package_v2.py',
        runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),stager=str(ROOT/'tools/native_package_v3.py'),
        stager_sha256=sha((ROOT/'tools/native_package_v3.py').read_bytes()),
        stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256=sha((ROOT/'tools/native_package_v2.py').read_bytes()))],max_seconds=3700)
    ticket=dict(schema='gfn16-global-ticket-v1',id=qid,owner='fault-fanout-p16',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=8 if aw==16 else 4,minimum_ram_rationale='Existing4GiB bounded-field envelope/fullN8GiB; no peak claim.',
        est_minutes=10,promotion_bound=False,test_role='normal',packages=[variant],rtl_readiness=m['rtl_readiness'])
    if aw==16:ticket.update(after=[f's4-p16-fault-fanout-aw8-f{field}-c2-normal-q1-v1'],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket)
    return dict(status='normal_source_prepared_not_submitted',id=qid,ticket=str(output/'global-ticket-v1.json'),counts=m['fault_fanout']['counts'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--budget',type=Path,required=True)
    p.add_argument('--aw',type=int,choices=(8,16),default=8);p.add_argument('--field',type=int,choices=(0,1,2),default=1)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.aw,a.field,a.budget),indent=2))
