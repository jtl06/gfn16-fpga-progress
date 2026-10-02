"""Finite source-bound native arithmetic sequence; no local HDL execution."""
import hashlib
import json
from pathlib import Path
import shutil
from .stream27_threefield_carry_v1 import ROOT,prepare as compile_core

BENCH='rtl/tb/stream27_threefield_carry_v1.cpp'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination,*,n=32):
    destination=Path(destination).resolve()
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_THREEFIELD_FRESH_PAUSE')
    if n not in (32,256):raise ValueError('S4_THREEFIELD_NATIVE_SMALL_GATE_ONLY')
    b=compile_core(n);g=b['geometry'];aw=n.bit_length()-1;source=destination/'inputs/fpga';source.mkdir(parents=True)
    for name,text in b['files'].items():
        path=source/'rtl'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    (source/'rtl/tb').mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/BENCH,source/BENCH)
    label=f'S4_THREEFIELD_CARRY_AW{aw}_PASS'
    header=f'''#include "V{b['top']}.h"
using DUT=V{b['top']};
constexpr unsigned N={n},P=16,T=N/P,BASE=1000000000,BOUND={2*n+24*16};
constexpr unsigned COEFFICIENT={g['double_register']},DIGIT={g['first_digit']},BOUNDARY={g['boundary_output']},DONE={g['carry_done']},INTERVAL={g['warm_interval']},CORRECTION={g['next_correction_accept']};
constexpr const char* PASS_LABEL="{label}";
'''
    (source/'rtl/tb/s4_threefield_config_v1.h').write_text(header)
    deps=list(dict.fromkeys(b['source_dependencies']+['reference/stream27_threefield_carry_native_v1.py',BENCH]))
    for name in deps:
        path=source/'lineage'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
    sources={str(path.relative_to(source)):sha(path) for path in sorted(source.rglob('*')) if path.is_file()}
    footer=f'{label} cases=5 frames=13 coefficient_words={13*n} digit_words={13*n} boundary_pairs=208 warm_feedback_starts=8\n'
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='UNBOUND_NO_DISPATCH',
        source_root=str(source),output_parent=str(destination/'UNBOUND_OUTPUT'),sources=sources,
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=BENCH,
            parameters=dict(AW=aw,P=16,CONTEXTS=1),cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name=f's4-aw{aw}-threefield-carry',argv=['{exe}'],expected_returncode=0,expected_stdout=footer,expected_stderr='')],
        lint_baseline_policy='Fresh r38 class-gated lint; no defect or unknown waiver.')
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result=dict(status='prepared_not_executed',manifest_sha256=sha(destination/'manifest.json'),source_count=len(sources),
        top=b['top'],geometry=g,source_sha256=b['source_sha256'],generated_sha256=b['generated_sha256'],
        full_N_numeric_NTT_performed_on_Mac=False,native_run_performed=False,threads=1,
        independent_reference='Signed128 direct schoolbook coefficients; ordinary Euclidean block split/carry; serial modular canonical math check only.',
        feedback='Next rows/corrections are driven from ACTUAL captured RTL carry outputs, not reference output; fixed counted feedback delay.',
        gate_scope='S4-b intermediate arithmetic/calendar gate; external simulator feedback driver is not production finite recurrence controller or hardware canonical readback',
        promotion_allowed=False)
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    import sys
    if len(sys.argv)!=3:raise ValueError('S4_THREEFIELD_NATIVE_USAGE destination n')
    r=prepare(sys.argv[1],n=int(sys.argv[2]));print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','geometry')},indent=2))
