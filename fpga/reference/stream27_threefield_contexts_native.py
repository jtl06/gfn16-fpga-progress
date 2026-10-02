"""Normal-first native gate for the real threefield contexts arithmetic core.

Local work is source/event/width only. Independent signed-schoolbook and
Euclidean carry run in the native CPP. Actual outputs drive external feedback;
this is not the production recurrence/controller or canonical host gate.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from fpga.reference import stream27_threefield_contexts as core
from fpga.reference import stream27_two_context_native as base
from fpga.reference.s4_two_context_model_v1 import disjoint,feedback_queues
from fpga.reference.stream27_blockcarry_param_model_v1 import bounds
from fpga.tools import native_class_package_v2 as package
ROOT=core.ROOT
SELF='reference/stream27_threefield_contexts_native.py'
CPP='rtl/tb/stream27_threefield_contexts.cpp'
HEADER='rtl/tb/s4_threefield_contexts_config_v1.h'

def role(aw=5,p=8):
    base.need(aw in (5,8) and p in (8,16),'THREE_CTX_SMALL_GEOMETRY')
    bundle=core.prepare(1<<aw,p,contexts=2,mode='warm_signed');g=bundle['geometry'];plan=base.calendar(g)
    for ctx,radix in enumerate((1009,2017)):bounds(1<<aw,p,radix)
    frames=plan['frames']
    disjoint([(f['start']+g['sink_accept'],f['start']+g['carry_done'],(f['context'],f['epoch'])) for f in frames],'THREE_CTX_CARRY_ACTIVE')
    # Actual digits become usable on the next edge, boundary on next correction.
    previous={}
    for f in frames:
        old=previous.get(f['context'])
        if old:
            base.need(f['start']>=old['start']+g['first_digit']+1,'THREE_CTX_ACTUAL_ROW_AVAILABILITY')
            base.need(f['correction']>=old['start']+g['boundary_output']+1,'THREE_CTX_ACTUAL_BOUNDARY_AVAILABILITY')
        previous[f['context']]=f
    plan.update(scope='Real three-field/CRT/carry with external actual per-context feedback; no production recurrence/host/publication/canonical qualification',
        setup_profiles=[dict(context=ctx,base=radix,generation=11+12*ctx,bits=213) for ctx,radix in enumerate((1009,2017))],
        setup_latency=bundle['setup_latency'],carry_active_nonoverlap=True,actual_external_feedback_starts=6)
    header=f'''#include "V{bundle['top']}.h"
using DUT=V{bundle['top']};
constexpr unsigned AW={aw},N={1<<aw},P={p},T=N/P,LANE_BITS={p.bit_length()-1},BOUND=2*N+24*P,FRAME_COUNT=8;
constexpr unsigned SETUP={bundle['setup_latency']},COEFFICIENT={g['double_register']},DIGIT={g['first_digit']},BOUNDARY={g['boundary_output']},DONE={g['carry_done']};
constexpr uint32_t BASES[2]={{1009,2017}};
'''
    # uint32_t appears in the generated header before standard CPP includes.
    header='#include <cstdint>\n'+header
    for name,key in [('FRAME_CONTEXT','context'),('FRAME_EPOCH','epoch'),('FRAME_ORDINAL','ordinal'),('FRAME_START','start'),('FRAME_CORRECTION','correction')]:
        header+='constexpr unsigned '+name+'[FRAME_COUNT]={'+','.join(str(f[key]) for f in frames)+'};\n'
    files={'rtl/'+name:text.encode() for name,text in bundle['files'].items()}
    files.update({CPP:(ROOT/CPP).read_bytes(),HEADER:header.encode(),'rtl/tb/native_runtime_context_v1.h':(ROOT/'rtl/tb/native_runtime_context_v1.h').read_bytes()})
    for path in bundle['source_dependencies']:
        raw=(ROOT/path).read_bytes();base.need(base.sha(raw)==bundle['source_sha256'][path],'THREE_CTX_DEPENDENCY_DRIFT:'+path);files['lineage/'+path]=raw
    for path in (SELF,base.SELF,'reference/s4_two_context_model_v1.py','reference/stream27_blockcarry_param_model_v1.py'):
        files['lineage/'+path]=(ROOT/path).read_bytes()
    stdout=f'S4_THREE_CONTEXTS_PASS aw={aw} p={p} frames=8 counts=3/5 setup_profiles=2 coefficients={8*(1<<aw)} digits={8*(1<<aw)} boundary_pairs={8*p} actual_feedback_starts=6 intermediate_external_driver=1\n'
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',
        sources={name:base.sha(raw) for name,raw in files.items()},build=dict(top=bundle['top'],sv_sources=['rtl/'+name for name in bundle['rtl_sources']],
            cpp_source=CPP,parameters=bundle['parameters'],cflags=['-std=c++17','-O2','-Werror=return-type'],runtime_threads=1),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='threefield-contexts-normal',argv=['{exe}'],expected_returncode=0,expected_stdout=stdout,expected_stderr='')],
        threefield_contexts=dict(geometry=g,calendar=plan,source_sha256=bundle['source_sha256'],generated_sha256=bundle['generated_sha256'],
            reference='Independent native signed schoolbook + serial Euclidean residue and blockcarry; actual native rows/boundaries feed each next per-context frame',
            full_N_numeric_locally_performed=False,scope=plan['scope']),promotion_allowed=False)
    return manifest,files

def prepare(out,aw,p,budget,revision=1):
    base.need(not out.exists() and not (ROOT/'docs/briefs/PAUSE').exists() and not (ROOT/'queue/PAUSE').exists(),'THREE_CTX_FRESH_PAUSE')
    base.need(type(revision) is int and revision>=1,'THREE_CTX_REVISION');m,files=role(aw,p);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    m.update(source_root=str(source),output_parent=str(out/'UNBOUND_OUTPUT'));base.dump(out/'manifest.json',m)
    ready=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');stem=f's4-three-contexts-aw{aw}-p{p}'
    snapshot={k:v for k,v in m['sources'].items() if k.endswith('.sv')}
    readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=stem+f'-v{revision}',source_snapshot=snapshot,candidate_source_sha256=base.sha(base.canonical(snapshot)),rtl_ready_at_utc=ready)
    base.dump(out/'source-readiness.json',readiness);packet=out/'packet-01'
    prepared=package.prepare(out/'manifest.json',source,'gcp-c4d-static01-v1',stem+f'-normal-01-v{revision}','run',packet,budget)
    native=json.loads((packet/'ticket.json').read_text())
    donor=ROOT/'results/throughput-20260929/trackS-two-context-field-v1/aw5-p8-f0-normal-v3/global-ticket.json';ticket=json.loads(donor.read_text())
    ticket.update(id=stem+f'-normal-q1-v{revision}',candidate_id=readiness['candidate_id'],owner='two-context-native',created=ready,test_role='normal',
        rtl_readiness=readiness,source_gate=dict(scope=m['threefield_contexts']['scope'],promotion_allowed=False))
    ticket['packages'][0].update(archive=str(packet/'package.tar.gz'),sha256=prepared['archive_sha256'],ticket_sha256=prepared['ticket_sha256'],
        manifest_sha256=native['manifest_sha256'],worker_id=native['id'],native_root=native['native_root'])
    base.dump(out/'global-ticket.json',ticket);base.dump(out/'preparation.json',dict(status='source_ready_not_dispatched',id=ticket['id'],counts=[3,5],geometry=m['threefield_contexts']['geometry']))
    print(out/'global-ticket.json')
if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--aw',type=int,choices=(5,8),default=5);q.add_argument('--p',type=int,choices=(8,16),default=8)
    q.add_argument('--output',type=Path,required=True);q.add_argument('--budget',type=Path,required=True);q.add_argument('--revision',type=int,default=1)
    a=q.parse_args();prepare(a.output.resolve(),a.aw,a.p,a.budget.resolve(),a.revision)
