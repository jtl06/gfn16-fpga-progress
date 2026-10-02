"""S4-b N32/P16 shared-field precursor; immutable native inputs, no Mac HDL."""
import hashlib
import json
from pathlib import Path
import shutil

from .stream27_shared_field_v2 import ROOT,prepare as compile_field
from .stream27_shared_warm_full_native_v1 import BENCH,BENCH_PIN,replace
from .stream_ntt_model import FIELDS


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compile_bench(b,field):
    if sha(ROOT/BENCH)!=BENCH_PIN:raise ValueError('S4_SMALL_FROZEN_BENCH')
    s=(ROOT/BENCH).read_text();g=b['geometry'];prime,_=FIELDS[field]
    s=replace(s,'#include "Vgenefer_stream27_shared_warm_aw8_p16_f0_v1.h"','#include "s4_small_config_v1.h"')
    s=replace(s,'using DUT=Vgenefer_stream27_shared_warm_aw8_p16_f0_v1;','')
    s=replace(s,'constexpr unsigned N=256,P=16,T=N/P,PRIME=104857601;','')
    s=replace(s,'constexpr unsigned FIRST=143,SINK=144,INTERVAL=187,CORRECTION=205;','')
    s=replace(s,'j==255 || j==3','j==N-1 || j==3')
    s=replace(s,'f.c1[k]=(k&1)?896:-896;','f.c1[k]=(k&1)?int32_t(BOUND):-int32_t(BOUND);')
    s=replace(s,'"S4_DATA tick="+std::to_string(tick)+" lane="+std::to_string(lane)',
        '"S4_DATA case="+std::to_string(counts.cases)+" tick="+std::to_string(tick)+" lane="+std::to_string(lane)+" expected="+std::to_string(physical->expected[reverse4(lane)*T+row])+" actual="+std::to_string(unpack(d.data_out,lane))')
    s=s.replace('S4_SHARED_AW8_PASS','S4_SHARED_AW5_F'+str(field)+'_PASS')
    header=f'''#include "V{b['top']}.h"
using DUT=V{b['top']};
constexpr unsigned N=32,P=16,T=N/P,PRIME={prime},BOUND={2*32+24*16};
constexpr unsigned FIRST={g['physical_first']},SINK={g['sink_accept']},INTERVAL={g['warm_interval']},CORRECTION={g['next_correction_accept']};
'''
    return s,header


def prepare(destination,*,field=0):
    destination=Path(destination).resolve()
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_SMALL_FRESH_PAUSE')
    b=compile_field(32,16,field);source=destination/'inputs/fpga';source.mkdir(parents=True)
    for name,text in b['files'].items():
        path=source/'rtl'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    cpp,header=compile_bench(b,field);bench='rtl/tb/stream27_shared_warm_small_v1.cpp'
    (source/'rtl/tb').mkdir(parents=True,exist_ok=True);(source/bench).write_text(cpp)
    (source/'rtl/tb/s4_small_config_v1.h').write_text(header)
    deps=list(dict.fromkeys(b['source_dependencies']+['reference/stream27_shared_warm_small_native_v1.py',
        'reference/stream27_shared_warm_full_native_v1.py',BENCH]))
    for name in deps:
        path=source/'lineage'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
    sources={str(path.relative_to(source)):sha(path) for path in sorted(source.rglob('*')) if path.is_file()}
    footer=f'S4_SHARED_AW5_F{field}_PASS cases=9 frames=9 physical_rows=18 physical_words=288 eligible_rows=14 commits=14 peak_owners=2\n'
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='UNBOUND_NO_DISPATCH',
        source_root=str(source),output_parent=str(destination/'UNBOUND_OUTPUT'),sources=sources,
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=bench,
            parameters=dict(AW=5,P=16,CONTEXTS=1),cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name=f's4-aw5-real-warm-field-f{field}',argv=['{exe}'],expected_returncode=0,
            expected_stdout=footer,expected_stderr='')],lint_baseline_policy='Fresh r38 class-gated lint; no defect/unknown-warning waiver.')
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result=dict(status='prepared_not_executed',manifest_sha256=sha(destination/'manifest.json'),source_count=len(sources),
        top=b['top'],geometry=b['geometry'],source_sha256=b['source_sha256'],generated_sha256=b['generated_sha256'],
        native_reference='independent signed negacyclic schoolbook at N32',full_N_numeric_NTT_performed_on_Mac=False,
        native_run_performed=False,threads=1,field=field,gate_scope='Small shared-field precursor only; no three-field CRT/carry/canonical readback/whole clock claim')
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    import sys
    if len(sys.argv)!=3:raise ValueError('S4_SMALL_USAGE destination field')
    r=prepare(sys.argv[1],field=int(sys.argv[2]));print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','geometry')},indent=2))
