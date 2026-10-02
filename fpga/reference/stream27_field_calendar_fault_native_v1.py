"""Bounded actual epoch-calendar negative on the repaired shared field.

Diagnostic top alone has one explicit forward-frame drop injection input.
CT inputs are both suppressed so CT stays idle; the real accepted lease must
detect its missing FIRST pointwise output at the unchanged due calendar.
Production field/transform/protocol files remain frozen and source-bound.
"""
import hashlib
import json
from pathlib import Path
import shutil
from . import stream27_shared_field_v4 as field

ROOT=field.ROOT
BENCH='rtl/tb/stream27_field_calendar_fault_v1.cpp'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination,*,p=8):
    destination=Path(destination).resolve()
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_CALENDAR_FRESH_PAUSE')
    if p not in (8,16):raise ValueError('S4_CALENDAR_REAL_P8_P16')
    b=field.prepare(32,p,0,mode='warm_signed');g=b['geometry'];old=b['top'];top=old+'_calendar_fault_v1'
    text=b['files'].pop(old+'.sv').replace('module '+old+' #','module '+top+' #',1)
    anchor='input logic clk,rst_n,in_slot_valid,frame_start,context_enabled,'
    if text.count(anchor)!=1:raise ValueError('S4_CALENDAR_DEBUG_PORT_ANCHOR')
    text=text.replace(anchor,anchor+'debug_drop_forward,')
    tag='launch_tag' if 'wire [ROW_W+8:0] launch_tag;' in text else 'digit_tag[0]'
    oldcall='.in_slot_valid(digit_slot),.frame_start(digit_slot && '+tag+'[ROW_W])'
    newcall='.in_slot_valid(digit_slot && !debug_drop_forward),.frame_start(digit_slot && !debug_drop_forward && '+tag+'[ROW_W])'
    if text.count(oldcall)!=1:raise ValueError('S4_CALENDAR_DEBUG_FORWARD_ANCHOR')
    text=text.replace(oldcall,newcall);b['files'][top+'.sv']=text
    source=destination/'inputs/fpga';source.mkdir(parents=True)
    for name,text in b['files'].items():
        path=source/'rtl'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    (source/'rtl/tb').mkdir(parents=True);shutil.copyfile(ROOT/BENCH,source/BENCH)
    label=f'S4_CALENDAR_FIRST_P{p}_AW5_PASS'
    header=f'''#include "V{top}.h"
using DUT=V{top};
constexpr unsigned P={p},T={32//p},POINTWISE={g['pointwise_accept']},PHYSICAL={g['physical_first']},SINK={g['sink_accept']};
constexpr const char* PASS_LABEL="{label}";
'''
    (source/'rtl/tb/s4_calendar_fault_config_v1.h').write_text(header)
    deps=list(dict.fromkeys(b['source_dependencies']+[BENCH,'reference/stream27_field_calendar_fault_native_v1.py']))
    for name in deps:
        path=source/'lineage'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='UNBOUND_NO_DISPATCH',source_root=str(source),output_parent=str(destination/'UNBOUND_OUTPUT'),
        sources={str(path.relative_to(source)):sha(path) for path in sorted(source.rglob('*')) if path.is_file()},
        build=dict(top=top,sv_sources=['rtl/'+name for name in b['files'] if name.endswith('.sv')],cpp_source=BENCH,parameters=dict(AW=5,P=p,CONTEXTS=1),cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='s4-calendar-missing-first',argv=['{exe}'],expected_returncode=0,expected_stdout=f'{label} cases=4 normal_rows={2*(32//p)} missing_first_tick={g["pointwise_accept"]} external_faults=1 reloads=1\n',expected_stderr=''),
               dict(name='s4-calendar-typed-negative',argv=['{exe}','--negative'],expected_returncode=1,expected_stdout='',expected_stderr=f'S4_CALENDAR_TYPED expected={g["pointwise_accept"]+1} actual={g["pointwise_accept"]}\n')],
        lint_baseline_policy='Fresh class-gated lint, no defect or unknown waiver.')
    path=destination/'manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
    r=dict(status='source_prepared_not_executed',manifest_sha256=sha(path),source_count=len(manifest['sources']),p=p,geometry=g,top=top,
        diagnostic_delta='Only new top/debug_drop_forward port gates forward input slot and start together; all underlying transform/protocol/arithmetic bytes and real expected lease calendar unchanged.',
        scope='Actual source-pinned fault-injection epoch FIRST-row negative and normal/reset-reload/external-admission control; not an arithmetic/long/fullN/physical/promotion gate',promotion_allowed=False)
    (destination/'preparation.json').write_text(json.dumps(r,indent=2)+'\n');return r


if __name__=='__main__':
    import sys
    print(json.dumps(prepare(sys.argv[1],p=int(sys.argv[2])),indent=2))
