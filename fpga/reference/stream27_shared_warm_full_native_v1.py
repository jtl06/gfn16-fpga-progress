"""AW16 real one-field native preparation; source/ROM emission only locally.

The native C++ independent reference uses a different iterative NTT and first
checks that reference against direct signed schoolbook at N256. No Python
function here executes a numeric full-N transform.
"""
import hashlib
import json
from pathlib import Path
import shutil

from .stream27_shared_field_v1 import ROOT,prepare as compile_field
from .stream_ntt_model import FIELDS

BENCH='rtl/tb/stream27_shared_warm_aw8_v1.cpp'
BENCH_PIN='722fef508f9e99d03b282e59c4f47d4c8b8d468dd23a672930929f199cecbb2c'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replace(s,old,new):
    if s.count(old)!=1:raise ValueError('S4_FULL_BENCH_ANCHOR:'+old[:50])
    return s.replace(old,new)


def compile_bench(b,field):
    if sha(ROOT/BENCH)!=BENCH_PIN:raise ValueError('S4_FULL_FROZEN_BENCH')
    s=(ROOT/BENCH).read_text();n=b['geometry']['n'];p=b['parameters']['P'];prime,g=FIELDS[field]
    s=replace(s,'#include "Vgenefer_stream27_shared_warm_aw8_p16_f0_v1.h"','#include "s4_full_config_v1.h"')
    s=replace(s,'using DUT=Vgenefer_stream27_shared_warm_aw8_p16_f0_v1;','')
    s=replace(s,'constexpr unsigned N=256,P=16,T=N/P,PRIME=104857601;','')
    s=replace(s,'constexpr unsigned FIRST=143,SINK=144,INTERVAL=187,CORRECTION=205;','')
    s=replace(s,'k<4;++k','k<LANE_BITS;++k')
    s=replace(s,'j==255 || j==3','j==N-1 || j==3')
    s=replace(s,'f.c1[k]=(k&1)?896:-896;','f.c1[k]=(k&1)?int32_t(BOUND):-int32_t(BOUND);')
    s=replace(s,'static Frame frame(unsigned kind',
        '#include "stream27_shared_reference_ntt_v1.h"\nstatic Frame frame(unsigned kind')
    begin=s.index('    // Independent signed negacyclic schoolbook;')
    end=s.index('    return f;',begin)
    s=s[:begin]+'''    std::vector<int64_t> expanded(N);
    for(unsigned j=0;j<N;++j)expanded[j]=f.digits[j];
    for(unsigned k=0;k<P;++k){expanded[k*T]+=f.c0[k];expanded[k*T+1]+=f.c1[k];}
    const auto expected=ref_negacyclic_square(expanded);
    std::copy(expected.begin(),expected.end(),f.expected.begin());
'''+s[end:]
    s=replace(s,'run(d,{frame(2),frame(3,24,24,1)},counts);',
        'run(d,{frame(2),frame(3,INTERVAL+16,CORRECTION+16,1)},counts);')
    s=replace(s,'need(argc==1,"S4_ARGUMENTS");Counts counts;',
        'need(argc==1,"S4_ARGUMENTS");ref_self_check();Counts counts;')
    s=replace(s,'"S4_DATA tick="+std::to_string(tick)+" lane="+std::to_string(lane)',
        '"S4_DATA case="+std::to_string(counts.cases)+" tick="+std::to_string(tick)+" lane="+std::to_string(lane)+" expected="+std::to_string(physical->expected[reverse4(lane)*T+row])+" actual="+std::to_string(unpack(d.data_out,lane))')
    s=s.replace('S4_SHARED_AW8_PASS','S4_SHARED_AW16_PASS')
    g0=b['geometry']
    header=f'''#include "V{b['top']}.h"
using DUT=V{b['top']};
constexpr unsigned N={n},P={p},T=N/P,LANE_BITS={p.bit_length()-1},PRIME={prime},GENERATOR={g},BOUND={2*n+24*p};
constexpr unsigned FIRST={g0['physical_first']},SINK={g0['sink_accept']},INTERVAL={g0['warm_interval']},CORRECTION={g0['next_correction_accept']};
'''
    return s,header


def prepare(destination,*,field=0):
    destination=Path(destination).resolve()
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_FULL_FRESH_PAUSE')
    b=compile_field(65536,16,field,allow_full_constants=True);source=destination/'inputs/fpga';source.mkdir(parents=True)
    for name,text in b['files'].items():
        path=source/'rtl'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    cpp,header=compile_bench(b,field);bench='rtl/tb/stream27_shared_warm_full_v1.cpp'
    (source/'rtl/tb').mkdir(parents=True,exist_ok=True);(source/bench).write_text(cpp)
    (source/'rtl/tb/s4_full_config_v1.h').write_text(header)
    ref='rtl/tb/stream27_shared_reference_ntt_v1.h';shutil.copyfile(ROOT/ref,source/ref)
    deps=b['source_dependencies']+['reference/stream27_shared_warm_full_native_v1.py',BENCH,
        'reference/merged_negacyclic27_model.py','reference/lazy28_butterfly_v1.py']
    for name in deps:
        path=source/'lineage'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
    sources={str(path.relative_to(source)):sha(path) for path in sorted(source.rglob('*')) if path.is_file()}
    footer='S4_SHARED_AW16_PASS cases=9 frames=9 physical_rows=36864 physical_words=589824 eligible_rows=28672 commits=28672 peak_owners=2\n'
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='UNBOUND_NO_DISPATCH',
        source_root=str(source),output_parent=str(destination/'UNBOUND_OUTPUT'),sources=sources,
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=bench,
            parameters=dict(AW=16,P=16,CONTEXTS=1),cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='s4-aw16-real-warm-field',argv=['{exe}'],expected_returncode=0,expected_stdout=footer,expected_stderr='')],
        lint_baseline_policy='Fresh r38 class-gated lint; no defect or unknown-warning waiver.')
    (destination/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    result=dict(status='prepared_not_executed',manifest_sha256=sha(destination/'manifest.json'),source_count=len(sources),
        top=b['top'],geometry=b['geometry'],source_sha256=b['source_sha256'],generated_sha256=b['generated_sha256'],
        native_reference='independent iterative twist/cyclic-square/untwist, self-checked atN256 against signed schoolbook',
        full_N_numeric_NTT_performed_on_Mac=False,native_run_performed=False,threads=1,
        gate_scope='S4-a one field only; neither three-field CRT/carry nor E2E/fit/timing sign-off')
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    import sys
    if len(sys.argv)!=2:raise ValueError('S4_FULL_USAGE')
    r=prepare(sys.argv[1]);print(json.dumps({k:r[k] for k in ('status','manifest_sha256','source_count','top','geometry')},indent=2))
