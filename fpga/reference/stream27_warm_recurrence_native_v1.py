"""Native finite INTERNAL feedback source preparation, not host ABI closure."""
import json
from pathlib import Path
import shutil
from .stream27_warm_recurrence_v1 import ROOT,prepare as compile_core
from .stream27_threefield_carry_native_v2 import serial_bench,BENCH,BENCH_PIN
from .stream27_threefield_carry_native_v1 import sha
from .stream27_shared_warm_full_native_v1 import replace


def compile_bench():
    if sha(ROOT/BENCH)!=BENCH_PIN:raise ValueError('S4_INTERNAL_BENCH_PARENT_DRIFT')
    s=serial_bench((ROOT/BENCH).read_text())
    s=replace(s,'#include "s4_threefield_config_v1.h"','#include "s4_internal_config_v1.h"')
    s=replace(s,'d.double_in=0;d.context_enabled=1;','d.double_in=0;d.square_count=1;d.double_mask=0;d.context_enabled=1;')
    s=replace(s,'unsigned last=frames.back().start+DONE+2;',
        'unsigned last=frames.back().start+DONE+2;') if False else s
    s=replace(s,'d.clk=0;clear(d);unsigned starts=0,corrections=0;',
        'd.clk=0;clear(d);d.square_count=count;d.double_mask=kind==2?10u:0u;unsigned starts=0,corrections=0,internal_starts=0,internal_corrections=0;')
    s=replace(s,'const auto& f=frames[i];if(tick>=f.start&&tick<f.start+T)',
        'const auto& f=frames[i];internal_starts+=i!=0&&tick==f.start;internal_corrections+=i!=0&&tick==f.correction;if(i==0&&tick>=f.start&&tick<f.start+T)')
    s=replace(s,'if(tick==f.correction){d.correction_valid=1;',
        'if(i==0&&tick==f.correction){d.correction_valid=1;')
    s=replace(s,'d.eval();need(unsigned(d.frame_accept)==starts&&unsigned(d.correction_accept)==corrections,',
        'd.eval();need(unsigned(d.internal_frame_accept)==internal_starts&&unsigned(d.internal_correction_accept)==internal_corrections,"S4_INTERNAL_ADMISSION tick="+std::to_string(tick));counts.feedback+=d.internal_frame_accept;need(unsigned(d.frame_accept)==starts&&unsigned(d.correction_accept)==corrections,')
    s=replace(s,'need(!d.out_error,"S4_ERROR tick="+std::to_string(tick));',
        'need(!d.out_error,"S4_ERROR tick="+std::to_string(tick));need(bool(d.warm_done)==(tick==frames.back().start+DONE+1),"S4_WARM_DONE_CYCLE");')
    s=replace(s,'    }++counts.cases;',
        '    }need(!d.active&&d.warm_done&&!d.warm_cancelled&&d.completed_frames==count,"S4_FINITE_DRAIN");++counts.cases;')
    return s


def prepare(destination,*,n=32):
    destination=Path(destination).resolve()
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_INTERNAL_FRESH_PAUSE')
    if n not in (32,256):raise ValueError('S4_INTERNAL_SMALL_NATIVE_GATE_ONLY')
    b=compile_core(n);g=b['geometry'];aw=n.bit_length()-1;source=destination/'inputs/fpga';source.mkdir(parents=True)
    for name,text in b['files'].items():
        path=source/'rtl'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    bench='rtl/tb/stream27_warm_recurrence_v1.cpp';(source/'rtl/tb').mkdir(parents=True,exist_ok=True)
    (source/bench).write_text(compile_bench());label=f'S4_WARM_RECURRENCE_AW{aw}_PASS'
    header=f'''#include "V{b['top']}.h"
using DUT=V{b['top']};
constexpr unsigned N={n},P=16,T=N/P,BASE=1000000000,BOUND={2*n+24*16};
constexpr unsigned COEFFICIENT={g['double_register']},DIGIT={g['first_digit']},BOUNDARY={g['boundary_output']},DONE={g['carry_done']},INTERVAL={g['warm_interval']},CORRECTION={g['next_correction_accept']};
constexpr const char* PASS_LABEL="{label}";
'''
    (source/'rtl/tb/s4_internal_config_v1.h').write_text(header)
    deps=list(dict.fromkeys(b['source_dependencies']+['reference/stream27_warm_recurrence_native_v1.py',
        'reference/stream27_threefield_carry_native_v2.py','reference/stream27_threefield_carry_native_v1.py',
        'reference/stream27_shared_warm_full_native_v1.py',BENCH]))
    for name in deps:
        path=source/'lineage'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
    sources={str(path.relative_to(source)):sha(path) for path in sorted(source.rglob('*')) if path.is_file()}
    footer=f'{label} cases=5 frames=13 coefficient_words={13*n} digit_words={13*n} boundary_pairs=208 warm_feedback_starts=8\n'
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='UNBOUND_NO_DISPATCH',
        source_root=str(source),output_parent=str(destination/'UNBOUND_OUTPUT'),sources=sources,
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=bench,
            parameters=dict(AW=aw,P=16,CONTEXTS=1),cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name=f's4-aw{aw}-finite-internal-feedback',argv=['{exe}'],expected_returncode=0,expected_stdout=footer,expected_stderr='')],
        lint_baseline_policy='Fresh r38 class-gated lint; no defect/unknown waiver.')
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result=dict(status='prepared_not_executed',manifest_sha256=sha(destination/'manifest.json'),source_count=len(sources),
        top=b['top'],geometry=g,source_sha256=b['source_sha256'],generated_sha256=b['generated_sha256'],
        feedback='RTL only after cold frame; simulator drives NO later rows/corrections. Finite count1/2/4, per-frame double mask; physical cancellation drain hook.',
        native_reference='Independent signed128 schoolbook + serial large Euclidean carry; math canonical check remains intermediate.',
        full_N_numeric_NTT_performed_on_Mac=False,native_run_performed=False,threads=1,
        gate_scope='Internal finite warm recurrence only; warm_done not canonical host done; hardware canonical/readback/image adapter still pending',
        promotion_allowed=False)
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    import sys
    if len(sys.argv)!=3:raise ValueError('S4_INTERNAL_USAGE destination n')
    r=prepare(sys.argv[1],n=int(sys.argv[2]));print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top')},indent=2))
