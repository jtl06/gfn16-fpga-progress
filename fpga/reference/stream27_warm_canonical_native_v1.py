"""Hardware final-image + actual frozen T5b native comparison, stream ABI.

The canonical conversion in the test is an expected-value/setup oracle only;
DUT results are read from actual materialized RAM and compared word-for-word
with an independently instantiated production RTL core. No scalar host/image
adapter, long-PRP coverage or equal pulse latency is claimed by this gate.
"""
import json
from pathlib import Path
import shutil
from .stream27_warm_canonical_v1 import ROOT,prepare as compile_core
from .stream27_warm_recurrence_native_v1 import compile_bench as parent_bench
from .stream27_threefield_carry_native_v1 import sha,BENCH
from .stream27_shared_warm_full_native_v1 import replace


def compile_bench():
    s=parent_bench()
    s=replace(s,'#include "s4_internal_config_v1.h"','#include "s4_canonical_config_v1.h"')
    s=replace(s,'d.begin_setup=0;d.in_slot_valid=0;',
        'd.read_req=0;d.read_address=0;d.t5b_load_we=0;d.t5b_read_en=0;d.t5b_start=0;d.t5b_double_bit=0;d.t5b_host_addr=0;d.t5b_write_data=0;d.begin_setup=0;d.in_slot_valid=0;')
    s=replace(s,'feedback=0;};','feedback=0,canonical_reads=0,t5b_reads=0;};')
    s=replace(s,'unsigned last=frames.back().start+DONE+2;',
        'const auto final_expected=canonical(frames.back().coefficients,BASE);unsigned finalization=(final_expected[0]==-1?7u:6u)*N;unsigned canonical_done_tick=frames.back().start+DONE+2+finalization;unsigned last=canonical_done_tick+1;')
    s=replace(s,'need(bool(d.warm_done)==(tick==frames.back().start+DONE+1),"S4_WARM_DONE_CYCLE");',
        'need(bool(d.warm_done)==(tick==frames.back().start+DONE+1),"S4_WARM_DONE_CYCLE");need(bool(d.done)==(tick==canonical_done_tick),"S4_CANONICAL_DONE_CYCLE tick="+std::to_string(tick));')
    old='    }need(!d.active&&d.warm_done&&!d.warm_cancelled&&d.completed_frames==count,"S4_FINITE_DRAIN");++counts.cases;'
    new='''    }need(!d.active&&d.done&&!d.busy&&!d.warm_cancelled&&!d.cancelled&&d.canonical_ready&&d.completed_frames==count,"S4_CANONICAL_PUBLICATION");
    need(d.canonical_cycles==finalization,"S4_CANONICAL_PHASE_COST");
    std::array<I,N> materialized{};
    // Source-visible E0 request -> E1 response adapter; unlike T5b E0 read,
    // it never assumes that a dirty/unfinished image is immediately readable.
    for(unsigned j=0;j<=N;++j){d.clk=0;clear(d);d.read_req=j<N;d.read_address=j<N?j:0;d.eval();d.clk=1;d.eval();
        need(!d.out_error&&!d.busy&&!d.done,"S4_READ_IDLE");need(bool(d.read_valid)==(j!=0),"S4_READ_LATENCY");
        if(j){need(d.read_address_out==j-1,"S4_READ_ADDRESS");I got=signed96(d.read_data,0);need(got==I(final_expected[j-1]),"S4_MATERIALIZED_READ_VALUE");materialized[j-1]=got;++counts.canonical_reads;}}
    // Compare ACTUAL production RTL, not an oracle standing in for hardware.
    // Redundant seed corrections are canonicalized for production test INPUT
    // only. Candidate output conversion remains entirely its real RTL RAM.
    const auto production_input=canonical(effective(frames.front().input),BASE);
    auto edge=[&](){d.clk=0;d.eval();d.clk=1;d.eval();need(!d.out_error,"S4_IDLE_DRIFT");};
    for(unsigned j=0;j<N;++j){clear(d);d.t5b_load_we=1;d.t5b_host_addr=j;d.t5b_write_data=uint32_t(production_input[j]);edge();}
    clear(d);edge();
    for(unsigned i=0;i<count;++i){clear(d);d.t5b_start=1;d.t5b_double_bit=frames[i].twice;edge();need(d.t5b_busy&&!d.t5b_done&&!d.t5b_error,"S4_T5B_START");d.t5b_start=0;
        unsigned elapsed=0;while(!d.t5b_done&&elapsed<100000){edge();++elapsed;}need(d.t5b_done&&!d.t5b_busy&&!d.t5b_error,"S4_T5B_COMPLETION");}
    for(unsigned j=0;j<N;++j){clear(d);d.t5b_read_en=1;d.t5b_host_addr=j;edge();need(d.t5b_read_valid&&!d.t5b_error,"S4_T5B_READ_PULSE");I got=signed96(d.t5b_read_data,0);need(got==materialized[j],"S4_T5B_BIT_IDENTITY case="+std::to_string(kind)+" address="+std::to_string(j)+" expected="+decimal(materialized[j])+" actual="+decimal(got));++counts.t5b_reads;}
    clear(d);edge();need(!d.t5b_read_valid&&!d.read_valid,"S4_READ_PULSE_CLEAR");++counts.cases;'''
    s=replace(s,old,new)
    s=replace(s,'<<counts.feedback<<"\\n";',
        '<<counts.feedback<<" canonical_reads="<<counts.canonical_reads<<" t5b_reads="<<counts.t5b_reads<<"\\n";')
    return s


def prepare(destination,*,n=32):
    destination=Path(destination).resolve()
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_CANONICAL_PAIRED_FRESH_PAUSE')
    if n not in (32,256):raise ValueError('S4_CANONICAL_PAIRED_SMALL_NATIVE_ONLY')
    b=compile_core(n,paired=True);g=b['geometry'];aw=n.bit_length()-1;source=destination/'inputs/fpga';source.mkdir(parents=True)
    for name,text in b['files'].items():
        path=source/'rtl'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    bench='rtl/tb/stream27_warm_canonical_v1.cpp';(source/'rtl/tb').mkdir(parents=True,exist_ok=True);(source/bench).write_text(compile_bench())
    label=f'S4_HARDWARE_CANONICAL_T5B_AW{aw}_PASS'
    header=f'''#include "V{b['top']}.h"
using DUT=V{b['top']};
constexpr unsigned N={n},P=16,T=N/P,BASE=1000000000,BOUND={2*n+24*16};
constexpr unsigned COEFFICIENT={g['double_register']},DIGIT={g['first_digit']},BOUNDARY={g['boundary_output']},DONE={g['carry_done']},INTERVAL={g['warm_interval']},CORRECTION={g['next_correction_accept']};
constexpr const char* PASS_LABEL="{label}";
'''
    (source/'rtl/tb/s4_canonical_config_v1.h').write_text(header)
    deps=list(dict.fromkeys(b['source_dependencies']+['reference/stream27_warm_canonical_native_v1.py',
        'reference/stream27_warm_recurrence_native_v1.py','reference/stream27_threefield_carry_native_v2.py',
        'reference/stream27_threefield_carry_native_v1.py','reference/stream27_shared_warm_full_native_v1.py',BENCH]))
    for name in deps:
        path=source/'lineage'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
    sources={str(path.relative_to(source)):sha(path) for path in sorted(source.rglob('*')) if path.is_file()}
    footer=f'{label} cases=5 frames=13 coefficient_words={13*n} digit_words={13*n} boundary_pairs=208 warm_feedback_starts=8 canonical_reads={5*n} t5b_reads={5*n}\n'
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='UNBOUND_NO_DISPATCH',source_root=str(source),
        output_parent=str(destination/'UNBOUND_OUTPUT'),sources=sources,
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=bench,
            parameters=dict(AW=aw,P=16,CONTEXTS=1),cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name=f's4-aw{aw}-hardware-canonical-t5b',argv=['{exe}'],expected_returncode=0,expected_stdout=footer,expected_stderr='')],
        lint_baseline_policy='Fresh r38 class-gated lint; no defect/unknown waiver.')
    (destination/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    r=dict(status='prepared_not_executed',manifest_sha256=sha(destination/'manifest.json'),source_count=len(sources),top=b['top'],
        geometry=g,canonical_cost=b['canonical_cost'],source_sha256=b['source_sha256'],generated_sha256=b['generated_sha256'],
        paired_production=b['paired_production'],full_N_numeric_NTT_performed_on_Mac=False,native_run_performed=False,threads=1,
        output_contract='Hardware materialized final RAM after once-chain6N/7N; source-visible E0/E1 read adapter; actual T5b RTL canonical96-word equality.',
        input_assistance='Only production comparator INPUT receives oracle-canonicalized redundant seed; DUT output is never oracle-converted.',
        remaining=['scalar host cold/image mutation adapter','same host priorities/errors and base mutation seams','counts beyond32/long PRP','fullN native/whole physical fit'],
        promotion_allowed=False)
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    if len(sys.argv)!=3:raise ValueError('S4_CANONICAL_PAIRED_USAGE destination n')
    r=prepare(sys.argv[1],n=int(sys.argv[2]));print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top')},indent=2))
