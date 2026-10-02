"""Normal-first actual field role for the isolated zero-cycle term selector.

Source preparation only locally. The existing admitted native class packager
and public queue own native compilation/execution; no new infrastructure.
Independent signed NTT oracle self-checks against schoolbook at N256.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from . import stream27_shared_field_flags as donor
from . import stream27_term_select_bind as binding
from .stream27_shared_warm_full_native_v1 import compile_bench,BENCH
from .stream27_p8_warm_native_v2 import lease_ledger

ROOT=donor.ROOT
SELF='reference/stream27_term_select_native.py'
CPP='rtl/tb/stream27_term_select_normal.cpp'
HEADER='rtl/tb/s4_full_config_v1.h'
REFERENCE='rtl/tb/stream27_shared_reference_ntt_v1.h'
RTL_READY='2026-10-01T22:52:59Z'
RTL_READY_CORR2='2026-10-01T22:54:35Z'


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def dump(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def field_bundle(aw=8,p=8,field=1,*,corr_serial_bfs=0):
    need(type(aw) is int and aw in (8,16) and type(p) is int and p in (8,16)
         and type(field) is int and field in (0,1,2),'TERM_SELECT_NORMAL_GEOMETRY')
    need(type(corr_serial_bfs) is int and corr_serial_bfs in (0,2),'TERM_SELECT_CORRECTION_FLAG')
    return binding.bind(donor.prepare(1<<aw,p,field,mode='warm_signed',contexts=1,
                                     allow_full_constants=aw==16,corr_serial_bfs=corr_serial_bfs))


def role(aw=8,p=8,field=1,*,corr_serial_bfs=0):
    b=field_bundle(aw,p,field,corr_serial_bfs=corr_serial_bfs);g=b['geometry'];rows=g['rows']
    ledgers=[lease_ledger(starts,g['sink_accept'],rows)
             for starts in ([0],[0,g['warm_interval']],[0,g['warm_interval']+16])]
    need(all(not item['rejected'] for item in ledgers),'TERM_SELECT_REAL_LEASE_CALENDAR')
    cpp,header=compile_bench(b,field)
    label=f'S4_TERM_SELECT_NORMAL aw={aw} p={p} field={field}'
    if corr_serial_bfs:label+=f' corr_serial_bfs={corr_serial_bfs}'
    need(cpp.count('S4_SHARED_AW16_PASS')==1,'TERM_SELECT_NORMAL_LABEL')
    cpp=cpp.replace('S4_SHARED_AW16_PASS',label,1)
    counts=dict(cases=9,frames=9,physical_rows=9*rows,physical_words=9*(1<<aw),
                eligible_rows=7*rows,commits=7*rows,peak_owners=max(x['peak'] for x in ledgers))
    footer=label+' '+' '.join(f'{key}={value}' for key,value in counts.items())+'\n'
    files={'rtl/'+name:value.encode() for name,value in b['files'].items()}
    files.update({CPP:cpp.encode(),HEADER:header.encode(),REFERENCE:(ROOT/REFERENCE).read_bytes()})
    for name in b['source_dependencies']+[SELF,'reference/stream27_shared_warm_full_native_v1.py',
                                           'reference/stream27_p8_warm_native_v2.py',BENCH]:
        files['lineage/'+name]=(ROOT/name).read_bytes()
    snapshot={'rtl/'+name:pin for name,pin in b['generated_sha256'].items()}
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/unbound/term-select/fpga',output_parent='/unbound/term-select/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=CPP,
                   parameters={key:value for key,value in b['parameters'].items() if key!='FIELD'},
                   cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='s4-term-selector-normal',argv=['{exe}'],expected_returncode=0,
                    expected_stdout=footer,expected_stderr='')],test_role='normal',
        term_select=dict(binding=b['term_select'],geometry=g,counts=counts,
                         source_sha256=b['source_sha256'],generated_sha256=b['generated_sha256'],
                         scope='One actual P8/P16 field nine arithmetic/calendar/reset/origin-tail cases; no whole or physical qualification.'))
    return manifest,files,snapshot


def prepare(output,aw,p,field,budget,*,corr_serial_bfs=0):
    from fpga.tools import native_class_package_v2 as package
    output=Path(output).resolve()
    need(not output.exists() and not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),
         'TERM_SELECT_FRESH_PAUSE')
    m,files,snapshot=role(aw,p,field,corr_serial_bfs=corr_serial_bfs)
    now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    m['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',
        candidate_id=f's4-p{p}-term-select-aw{aw}-f{field}-c{corr_serial_bfs}-v1',
        candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
        rtl_ready_at_utc=RTL_READY_CORR2 if corr_serial_bfs else RTL_READY,source_snapshot=snapshot)
    source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m)
    qid=f's4-p{p}-term-select-aw{aw}-f{field}-normal-q1-v1'
    if corr_serial_bfs:qid=f's4-p{p}-term-select-aw{aw}-f{field}-c{corr_serial_bfs}-normal-q1-v1'
    profile='gcp-c4d-static01-v1';worker=qid+'-01';packet=output/'packet-01'
    result=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
    variant=dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),
        sha256=result['archive_sha256'],ticket_sha256=result['ticket_sha256'],
        manifest_sha256=sha((packet/'manifest.json').read_bytes()),native_root=result['native_root'],
        runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
        stager=str(ROOT/'tools/native_package_v3.py'),stager_sha256=sha((ROOT/'tools/native_package_v3.py').read_bytes()),
        stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256=sha((ROOT/'tools/native_package_v2.py').read_bytes()))],
        max_seconds=3700)
    ticket=dict(schema='gfn16-global-ticket-v1',id=qid,owner='term-select',created=now,
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8 if aw==16 else 4,
        minimum_ram_rationale='Bounded field keeps existing4GiB exploration envelope; fullN8GiB. No peak claim.',
        est_minutes=10,promotion_bound=False,test_role='normal',packages=[variant],rtl_readiness=m['rtl_readiness'])
    if aw==16:
        predecessor=f's4-p{p}-term-select-aw8-f{field}-normal-q1-v1'
        if corr_serial_bfs:predecessor=f's4-p{p}-term-select-aw8-f{field}-c{corr_serial_bfs}-normal-q1-v1'
        ticket.update(after=[predecessor],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket)
    return dict(status='normal_source_prepared_not_submitted',id=qid,ticket=str(output/'global-ticket-v1.json'),
                manifest_sha256=sha(manifest.read_bytes()),top=m['build']['top'],counts=m['term_select']['counts'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--budget',type=Path,required=True);parser.add_argument('--aw',type=int,choices=(8,16),default=8)
    parser.add_argument('--p',type=int,choices=(8,16),default=8);parser.add_argument('--field',type=int,choices=(0,1,2),default=1)
    parser.add_argument('--corr-serial-bfs',type=int,choices=(0,2),default=0)
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.aw,args.p,args.field,args.budget,
                                                    corr_serial_bfs=args.corr_serial_bfs),indent=2))
