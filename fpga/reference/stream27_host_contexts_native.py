"""Real two-context waiting-final/canonical/ordered host-readback native gate.

Only source/event and genuine small whole-integer reference vectors run
locally. Every chain, raw capture, copy/publication and RAM read is native RTL.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from fpga.reference import stream27_host_contexts as core
from fpga.reference import stream27_two_context_native as base
from fpga.reference import stream27_two_context_whole_programs as whole
from fpga.tools import native_class_package_v2 as package
ROOT=core.ROOT
SELF='reference/stream27_host_contexts_native.py'
CPP='rtl/tb/stream27_host_contexts.cpp'
HEADER='rtl/tb/s4_host_contexts_config_v1.h'
def role(kind='dense',p=8,diet=False,n=32,counts=(3,5)):
    base.need(kind in ('dense','sentinel') and p in (8,16),'HOST_CONTEXT_SMALL_KIND_P')
    base.need(type(diet) is bool and (not diet or p==16),'HOST_CONTEXT_DIET_P16')
    base.need((n==32 and counts==(3,5)) or (n==256 and p==16 and diet and kind=='dense' and counts==(3,14)),'HOST_CONTEXT_BOUNDED_COHORT')
    flags=dict(corr_serial_bfs=2,mont_factored=1,cold_launch_fence=1) if diet else {}
    bundle=core.prepare(n,p,contexts=2,ram_closure=1,**flags);g=bundle['geometry'];program=whole.programs(n=n,p=p,kind=kind,counts=counts);ctx=program['contexts']
    capture_copy=kind=='dense' and (not diet or n==256)
    schedule=None
    if diet:
        schedule=core.diet_calendar.schedule(n,p,counts=counts)
        base.need(schedule['geometry']['warm_interval']==g['warm_interval'],'HOST_CONTEXT_DIET_NATIVE_CALENDAR')
        # This tiny C2 geometry has no final B capture during A copy. A conservative
        # source-edge bound (including32 spare control edges) finishes A first.
        a_warm=204+(counts[0]-1)*g['warm_interval']+g['carry_done']+1
        b_first_capture=204+schedule['context_offset']+(counts[1]-1)*g['warm_interval']+g['first_digit']+1
        if n==32:
            a_publication_bound=a_warm+2*g['rows']+(10 if kind=='sentinel' else 9)*n+n+32
            base.need(a_publication_bound<b_first_capture,'HOST_CONTEXT_DIET_NO_FORCED_COPY_OVERLAP')
        else:
            # The actual source RAM/load/begin/canonical/read pipeline places
            # B capture well inside A's scalar copy, with8-edge control margin.
            copy_first=a_warm+g['rows']+6+9*n
            base.need(copy_first+8<b_first_capture and b_first_capture+g['rows']<copy_first+n-8,'HOST_CONTEXT_DIET_COPY_OVERLAP_WITNESS')
    base.need('read_owner' in bundle['files'][bundle['top']+'.sv'],'HOST_CONTEXT_FINAL_READ_OWNER_ABI')
    if kind=='dense':base.need(ctx[0]['dependent_steps'][-1]['canonical_signed32']!=ctx[1]['dependent_steps'][-1]['canonical_signed32'],'HOST_CONTEXT_CROSS_TALK_WITNESS')
    header=f'''#include <algorithm>
#include <cstdint>
#include "V{bundle['top']}.h"
using DUT=V{bundle['top']};
constexpr unsigned AW={n.bit_length()-1},N={n},P={p},T=N/P,INTERVAL={g['warm_interval']},FIRST_DIGIT={g['first_digit']},CARRY_DONE={g['carry_done']},CANON_PASSES={10 if kind=='sentinel' else 9};
constexpr const char* KIND="{kind}";
constexpr bool EXPECT_CAPTURE_COPY={str(capture_copy).lower()};
constexpr unsigned BASES[2]={{1009,2017}},COUNTS[2]={{{counts[0]},{counts[1]}}},EPOCHS[2]={{65534,42}},FIRST[2]={{204,{204+g['warm_interval']//2}}};
'''
    for name,key,width in [('INITIAL','initial_digits',n),('C0','initial_c0',p),('C1','initial_c1',p),('EXPECTED',None,n)]:
        arrays=[c[key] if key else c['dependent_steps'][-1]['canonical_signed32'] for c in ctx]
        header+=f'constexpr int32_t {name}[2][{width}]={{'+','.join('{'+','.join(map(str,array))+'}' for array in arrays)+'};\n'
    files={'rtl/'+name:text.encode() for name,text in bundle['files'].items()}
    files.update({CPP:(ROOT/CPP).read_bytes(),HEADER:header.encode(),'rtl/tb/native_runtime_context_v1.h':(ROOT/'rtl/tb/native_runtime_context_v1.h').read_bytes(),
                  'assets/two-context-whole-program.json':json.dumps(program,sort_keys=True,indent=2).encode()+b'\n'})
    for path in bundle['source_dependencies']:
        raw=(ROOT/path).read_bytes();base.need(base.sha(raw)==bundle['source_sha256'][path],'HOST_CONTEXT_DEPENDENCY_DRIFT:'+path);files['lineage/'+path]=raw
    for path in (SELF,'reference/stream27_two_context_whole_programs.py','reference/s4_waiting_final_contract.py','tests/test_s4_waiting_final_contract.py'):
        files['lineage/'+path]=(ROOT/path).read_bytes()
    stdout=f'S4_HOST_CONTEXTS_PASS kind={kind} aw={n.bit_length()-1} p={p} counts={counts[0]}/{counts[1]} chains=2 squares={sum(counts)} reads={4*n} peer_live_reads={n} waiting_b=1 capture_during_copy={int(capture_copy)} canonical_peer_arithmetic=1 owner_bits=56 signed96=1 canonical_host=1\n'
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',sources={name:base.sha(raw) for name,raw in files.items()},
        build=dict(top=bundle['top'],sv_sources=['rtl/'+name for name in bundle['rtl_sources']],cpp_source=CPP,parameters=dict(bundle['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),
            cflags=['-std=c++17','-O2','-Werror=return-type'],runtime_threads=1),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='host-contexts-normal',argv=['{exe}'],expected_returncode=0,expected_stdout=stdout,expected_stderr='')],
        host_contexts=dict(kind=kind,geometry=g,program=program,source_sha256=bundle['source_sha256'],generated_sha256=bundle['generated_sha256'],host_contract=bundle['host_contract'],
            diet_flags=flags,two_context_schedule=schedule,expected_capture_during_copy=capture_copy,
            diet_source_freeze_event_utc='2026-10-01T23:39:34Z' if diet else None,
            abi_freeze_event_utc='2026-10-01T22:26:35Z',ram_closure_freeze_event_utc='2026-10-01T22:45:44Z',reference='Genuine small Python whole-integer expansion and repeated modular squaring mod base^N+1; final signed32 digits consumed by native full signed96 actual RAM checks',
            expected_generations=[1,1],oracle_vectors_generation_fields_are_not_controller_assumptions=True,
            full_N_numeric_locally_performed=False,scope=f'Real AW{n.bit_length()-1}/P{p} two-context chains, waiting shadow reuse, shared canonical finalization, acknowledged copy/publication and ordered signed96 host reads; independent normal gate/no inherited geometry/physical/throughput claim'),promotion_allowed=False)
    return manifest,files
def prepare(out,budget,kind='dense',revision=1,p=8,diet=False,n=32,counts=(3,5),after=None):
    base.need(not out.exists() and not (ROOT/'docs/briefs/PAUSE').exists() and not (ROOT/'queue/PAUSE').exists(),'HOST_CONTEXT_FRESH_PAUSE')
    m,files=role(kind,p,diet,n,counts);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    m.update(source_root=str(source),output_parent=str(out/'UNBOUND_OUTPUT'));base.dump(out/'manifest.json',m)
    ready=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');stem=f's4-host-contexts-aw{n.bit_length()-1}-p{p}'+('-diet-c2-m1-fence' if diet else '')+f'-{kind}';snapshot={k:v for k,v in m['sources'].items() if k.endswith('.sv')}
    readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=stem+f'-v{revision}',source_snapshot=snapshot,candidate_source_sha256=base.sha(base.canonical(snapshot)),rtl_ready_at_utc=ready)
    if diet:readiness['rtl_ready_at_utc']=m['host_contexts']['diet_source_freeze_event_utc']
    base.dump(out/'source-readiness.json',readiness);packet=out/'packet-01';prepared=package.prepare(out/'manifest.json',source,'gcp-c4d-static01-v1',stem+f'-normal-01-v{revision}','run',packet,budget)
    nt=json.loads((packet/'ticket.json').read_text());donor=ROOT/'results/throughput-20260929/trackS-warm-contexts-v1/aw5-p8-normal-v1/global-ticket.json';ticket=json.loads(donor.read_text())
    ticket.update(id=stem+f'-normal-q1-v{revision}',candidate_id=readiness['candidate_id'],created=ready,test_role='normal',rtl_readiness=readiness,source_gate=dict(scope=m['host_contexts']['scope'],promotion_allowed=False))
    ticket['packages'][0].update(archive=str(packet/'package.tar.gz'),sha256=prepared['archive_sha256'],ticket_sha256=prepared['ticket_sha256'],manifest_sha256=nt['manifest_sha256'],worker_id=nt['id'],native_root=nt['native_root'])
    if after:ticket['after']=[after]
    base.dump(out/'global-ticket.json',ticket);print(out/'global-ticket.json')
if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--output',type=Path,required=True);q.add_argument('--budget',type=Path,required=True);q.add_argument('--kind',choices=('dense','sentinel'),default='dense');q.add_argument('--revision',type=int,default=1);q.add_argument('--p',type=int,choices=(8,16),default=8)
    q.add_argument('--diet',action='store_true')
    q.add_argument('--n',type=int,choices=(32,256),default=32);q.add_argument('--counts',type=int,nargs=2,default=(3,5));q.add_argument('--after')
    a=q.parse_args();prepare(a.output.resolve(),a.budget.resolve(),a.kind,a.revision,a.p,a.diet,a.n,tuple(a.counts),a.after)
