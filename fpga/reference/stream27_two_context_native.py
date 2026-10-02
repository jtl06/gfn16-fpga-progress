"""Normal-first real two-context shared-field source/event/native preparation.

Only RTL/ROM source generation and bounded integer calendars run locally.
Independent NTT and signed schoolbook execute solely inside the native CPP.
This gate injects independent frames; shared CRT/carry feedback is not implied.
"""
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from fpga.reference import stream27_shared_field_contexts as core
from fpga.reference.s4_two_context_model_v1 import Frame,correction_calendar,disjoint
from fpga.reference.stream_ntt_model import FIELDS
from fpga.tools import native_class_package_v2 as package
ROOT=core.ROOT
SELF='reference/stream27_two_context_native.py'
CPP='rtl/tb/stream27_two_context_field.cpp'
HEADER='rtl/tb/s4_two_context_field_config_v1.h'
REFERENCE='rtl/tb/stream27_shared_reference_ntt_v1.h'
REFERENCE_PIN='c7837ba92829293131efda704dfdde347708641bf9aff46dccbcb87b825ba390'

def need(ok,label):
    if not ok:raise ValueError(label)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def dump(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
def calendar(g):
    interval=g['warm_interval'];offset=interval//2
    frames=sorted([Frame(ctx,11 if ctx==0 else 23,((65534 if ctx==0 else 42)+ordinal)&65535,
        ordinal,ordinal*interval+ctx*offset,1009 if ctx==0 else 2017)
        for ctx,count in ((0,3),(1,5)) for ordinal in range(count)],key=lambda f:f.start)
    disjoint([(f.start,f.start+g['rows']-1,f.tag) for f in frames],'TWO_NATIVE_INPUT')
    disjoint([(f.start+g['physical_first'],f.start+g['physical_first']+g['rows']-1,f.tag) for f in frames],'TWO_NATIVE_OUTPUT')
    corrections=correction_calendar(frames,g)
    leases=[None]*4;rows=[];banks={};peak=0;mask=0
    last=frames[-1].start+g['last_sink']+1
    for edge in range(last):
        incoming=next((f for f in frames if f.start==edge),None)
        pre=tuple(leases);selected=None
        if incoming:
            selected=next((i for i,f in enumerate(pre) if f is None),None)
            need(selected is not None,'TWO_NATIVE_LEASE_CAPACITY');banks[incoming.tag]=selected;mask|=1<<selected
        leases=[None if f and f.start+g['last_sink']==edge else f for f in pre]
        if incoming:leases[selected]=incoming
        owners=sum(f is not None for f in leases);peak=max(peak,owners)
        rows.append(dict(edge=edge,pre_owners=sum(f is not None for f in pre),post_owners=owners,
                         admitted_bank=selected,retired_banks=[i for i,f in enumerate(pre) if f and f.start+g['last_sink']==edge]))
    need(not any(leases),'TWO_NATIVE_DRAIN')
    return dict(frames=[dict(context=f.context,generation=f.generation,epoch=f.epoch,ordinal=f.ordinal,start=f.start,base=f.base,
        correction=corrections[i]['accept'],bank=banks[f.tag]) for i,f in enumerate(frames)],
        corrections=corrections,peak=peak,used_bank_mask=mask,lease_edges=rows,
        allocation='Pre-edge lowest-free among4 leases; retirement cannot free an occupied bank for same-edge admission',
        context_frame_counts=[3,5],scope='Independent injected one-field frames; no CRT/carry feedback/host/finalization qualification')
def role(aw=5,p=8,field=0):
    need(aw in (5,8) and p in (8,16) and field in (0,1,2),'TWO_NATIVE_SMALL_GEOMETRY')
    need(sha((ROOT/REFERENCE).read_bytes())==REFERENCE_PIN,'TWO_NATIVE_FROZEN_REFERENCE')
    b=core.prepare(1<<aw,p,field,contexts=2,corr_serial_bfs=0,mont_factored=0);g=b['geometry'];plan=calendar(g);prime,generator=FIELDS[field]
    header=f'''#include "V{b['top']}.h"
using DUT=V{b['top']};
constexpr unsigned AW={aw},N={1<<aw},P={p},T=N/P,FIELD={field},LANE_BITS={p.bit_length()-1},PRIME={prime},GENERATOR={generator};
constexpr unsigned FIRST={g['physical_first']},SINK={g['sink_accept']},PW={g['pointwise_accept']},FRAME_COUNT=8;
constexpr unsigned EXPECTED_PEAK={plan['peak']},EXPECTED_BANK_MASK={plan['used_bank_mask']};
'''
    for name,key in [('FRAME_CONTEXT','context'),('FRAME_EPOCH','epoch'),('FRAME_ORDINAL','ordinal'),('FRAME_START','start'),('FRAME_CORRECTION','correction'),('FRAME_BANK','bank')]:
        header+='constexpr unsigned '+name+'[FRAME_COUNT]={'+','.join(str(f[key]) for f in plan['frames'])+'};\n'
    files={'rtl/'+name:text.encode() for name,text in b['files'].items()}
    files.update({CPP:(ROOT/CPP).read_bytes(),HEADER:header.encode(),REFERENCE:(ROOT/REFERENCE).read_bytes(),
                  'rtl/tb/native_runtime_context_v1.h':(ROOT/'rtl/tb/native_runtime_context_v1.h').read_bytes()})
    for path in b['source_dependencies']:
        raw=(ROOT/path).read_bytes();need(sha(raw)==b['source_sha256'][path],'TWO_NATIVE_DEPENDENCY_DRIFT:'+path);files['lineage/'+path]=raw
    for path in (SELF,'reference/s4_two_context_model_v1.py','reference/stream_ntt_model.py'):
        files['lineage/'+path]=(ROOT/path).read_bytes()
    stdout=f'S4_TWO_CONTEXT_FIELD_PASS aw={aw} p={p} field={field} frames=8 counts=3/5 physical_rows={8*g["rows"]} words={8*(1<<aw)} commits={8*g["rows"]} peak={plan["peak"]} bank_mask={plan["used_bank_mask"]} injected_field_only=1\n'
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',
        sources={name:sha(raw) for name,raw in files.items()},build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],
            cpp_source=CPP,parameters={k:v for k,v in b['parameters'].items() if k!='FIELD'},cflags=['-std=c++17','-O2','-Werror=return-type'],runtime_threads=1),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='two-context-field-normal',argv=['{exe}'],expected_returncode=0,expected_stdout=stdout,expected_stderr='')],
        two_context=dict(geometry=g,calendar=plan,source_sha256=b['source_sha256'],generated_sha256=b['generated_sha256'],
            reference='Independent native iterative negacyclic NTT with N256 signed schoolbook selfcheck; natural expanded digits+c0/c1',
            full_N_numeric_locally_performed=False,scope=plan['scope']),promotion_allowed=False)
    return manifest,files
def prepare(out,aw,p,field,budget,revision=1):
    need(not out.exists() and not (ROOT/'docs/briefs/PAUSE').exists() and not (ROOT/'queue/PAUSE').exists(),'TWO_NATIVE_FRESH_PAUSE')
    m,files=role(aw,p,field);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    m.update(source_root=str(source),output_parent=str(out/'UNBOUND_OUTPUT'));dump(out/'manifest.json',m)
    need(type(revision) is int and revision>=1,'TWO_NATIVE_REVISION')
    ready=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');qid=f's4-two-field-aw{aw}-p{p}-f{field}-normal-q1-v{revision}'
    candidate=f's4-two-field-aw{aw}-p{p}-f{field}-v{revision}';snapshot={k:v for k,v in m['sources'].items() if k.endswith('.sv')}
    readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=candidate,source_snapshot=snapshot,candidate_source_sha256=sha(canonical(snapshot)),rtl_ready_at_utc=ready)
    dump(out/'source-readiness.json',readiness)
    packet=out/'packet-01';worker=f's4-two-field-aw{aw}-p{p}-f{field}-normal-01-v{revision}'
    prepared=package.prepare(out/'manifest.json',source,'gcp-c4d-static01-v1',worker,'run',packet,budget)
    native=json.loads((packet/'ticket.json').read_text())
    donor=ROOT/'results/throughput-20260929/trackS-p16-diet-analysis-v1/fifo-ram-v1/normal-role-v1/global-ticket.json'
    ticket=json.loads(donor.read_text());ticket.update(id=qid,candidate_id=candidate,owner='two-context-native',created=ready,test_role='normal',
        rtl_readiness=readiness,source_gate=dict(scope=m['two_context']['scope'],promotion_allowed=False))
    ticket['packages'][0].update(archive=str(packet/'package.tar.gz'),sha256=prepared['archive_sha256'],ticket_sha256=prepared['ticket_sha256'],
        manifest_sha256=native['manifest_sha256'],worker_id=native['id'],native_root=native['native_root'])
    dump(out/'global-ticket.json',ticket);dump(out/'preparation.json',dict(status='source_ready_not_dispatched',id=qid,geometry=m['two_context']['geometry'],
        counts=[3,5],peak=m['two_context']['calendar']['peak'],bank_mask=m['two_context']['calendar']['used_bank_mask']))
    print(out/'global-ticket.json')
if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--aw',type=int,choices=(5,8),default=5);q.add_argument('--p',type=int,choices=(8,16),default=8)
    q.add_argument('--field',type=int,choices=(0,1,2),default=0);q.add_argument('--output',type=Path,required=True);q.add_argument('--budget',type=Path,required=True)
    q.add_argument('--revision',type=int,default=1)
    a=q.parse_args();prepare(a.output.resolve(),a.aw,a.p,a.field,a.budget.resolve(),a.revision)
