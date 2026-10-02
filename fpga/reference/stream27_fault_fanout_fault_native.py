"""Separate actual P8 field fault/reset/quarantine packet after normal gate.

Production binding/leaf are captured unchanged. Only a named diagnostic top
adds forward-drop and missing-replica-setter injection plus actual monitors.
No host/cache/whole-core fault sign-off or physical benefit is inferred.
"""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import json
from . import stream27_fault_fanout_native as normal
from . import stream27_fault_fanout_bind as binding

ROOT=normal.ROOT
SELF='reference/stream27_fault_fanout_fault_native.py'
CPP='rtl/tb/stream27_fault_fanout_faults.cpp'
HEADER='rtl/tb/s4_fault_fanout_config.h'
NORMAL_ID='s4-p8-fault-fanout-aw8-f2-b0-normal-q1-v1'
ID='s4-p8-fault-fanout-aw8-f2-b0-faults-q1-v1'
need,sha,dump=normal.need,normal.sha,normal.dump


def diagnostic_root(text,old):
    top=old+'_fault_probe_v1'
    need(text.count('module '+old+' #')==1,'S4_FAULT_FANOUT_DIAGNOSTIC_TOP')
    text=text.replace('module '+old+' #','module '+top+' #',1)
    ports='input logic clk,rst_n,in_slot_valid,frame_start,context_enabled,'
    need(text.count(ports)==1,'S4_FAULT_FANOUT_DIAGNOSTIC_PORTS')
    text=text.replace(ports,ports+'debug_drop_forward,debug_mask_replica_set,',1)
    ports='output logic [31:0] cycle_count,frame_count);'
    need(text.count(ports)==1,'S4_FAULT_FANOUT_DIAGNOSTIC_MONITORS')
    text=text.replace(ports,'''output logic [31:0] cycle_count,frame_count,
 output logic [1:0] monitor_quarantine,
 output logic monitor_original_fault,monitor_protocol_commit);''',1)
    marker=' wire stop=controller_error;\n'
    need(text.count(marker)==1,'S4_FAULT_FANOUT_DIAGNOSTIC_MONITOR_DRIVER')
    text=text.replace(marker,marker+''' assign monitor_quarantine=transform_quarantine;
 assign monitor_original_fault=controller_error;
 assign monitor_protocol_commit=protocol_commit;
''',1)
    marker='.fault_set('+binding.SETTER+')'
    need(text.count(marker)==1,'S4_FAULT_FANOUT_DIAGNOSTIC_REAL_SETTER')
    text=text.replace(marker,'.fault_set(('+binding.SETTER+') && !debug_mask_replica_set)',1)
    start=text.index(' forward_transform (');end=text.index(');',start)+2
    call=text[start:end]
    tag='launch_tag' if 'wire [ROW_W+8:0] launch_tag;' in text else 'digit_tag[0]'
    marker='.in_slot_valid(digit_slot),.frame_start(digit_slot && '+tag+'[ROW_W])'
    need(call.count(marker)==1,'S4_FAULT_FANOUT_DIAGNOSTIC_FORWARD_DROP')
    call=call.replace(marker,'.in_slot_valid(digit_slot && !debug_drop_forward),.frame_start(digit_slot && !debug_drop_forward && '+tag+'[ROW_W])',1)
    return top,text[:start]+call+text[end:]


def role():
    b=normal.field_bundle(8,2);g=b['geometry'];old=b['top'];top,text=diagnostic_root(b['files'][old+'.sv'],old)
    files={'rtl/'+name:value.encode() for name,value in b['files'].items() if name!=old+'.sv'}
    files['rtl/'+top+'.sv']=text.encode();files[CPP]=(ROOT/CPP).read_bytes()
    files[HEADER]=(f'#include "V{top}.h"\nusing DUT=V{top};\n'
                   f'constexpr unsigned P=8,T={g["rows"]},WORDS=(P*27+31)/32,POINTWISE={g["pointwise_accept"]},'
                   f'FIRST={g["physical_first"]},SINK={g["sink_accept"]};\n').encode()
    for name in b['source_dependencies']+[SELF,CPP,normal.SELF]:files['lineage/'+name]=(ROOT/name).read_bytes()
    footer=(f'S4_FAULT_FANOUT_FAULT_PASS aw=8 p=8 field=2 cases=9 normal_frames=4 normal_rows={4*g["rows"]}'
            f' missing_first={g["pointwise_accept"]} fault_origins=2 legal_origin_commits=1 reset_aborts=2 reset_ages=10,{g["physical_first"]+2}'
            f' quiet_tail=16 canceled_rows={g["rows"]} recovery_frames=3\n')
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/unbound/fault-fanout-fault/fpga',output_parent='/unbound/fault-fanout-fault/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=top,sv_sources=[name for name in files if name.endswith('.sv') and name.startswith('rtl/')],
            cpp_source=CPP,parameters={key:value for key,value in b['parameters'].items() if key!='FIELD'},
            cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='s4-p8-field-replica-genuine-fault-reset-tail',argv=['{exe}'],expected_returncode=0,
                    expected_stdout=footer,expected_stderr=''),
               dict(name='s4-p8-field-replica-origin-typed-negative',argv=['{exe}','--negative-replica-origin'],
                    expected_returncode=41,expected_stdout=footer,
                    expected_stderr='S4_FAULT_FANOUT_TYPED_REPLICA_ORIGIN expected=3 actual=0\n')],
        test_role='deliberate_fault',fault_fanout=dict(binding=b['fault_fanout'],geometry=g,
            diagnostic_changes=['Named top adds two injections and actual monitors; all leaves unchanged.',
                'Forward slot/start are dropped together to test actual fixed FIRST lease.',
                'Negative masks only new replica setter at genuine fault origin, after complete baseline.'],
            scope='Actual bounded one-field registered fault, legal origin commit tail, one-edge reset and live-context canceled physical tails; no whole/cross-field/host-cache proof.'),
        lint_baseline_policy='Fresh class-gated lint; no defect/unknown warning waiver.')
    return manifest,files


def prepare(output,budget):
    from fpga.tools import native_class_package_v2 as package
    output=Path(output).resolve()
    need(not output.exists() and not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),
         'S4_FAULT_FANOUT_FAULT_FRESH_PAUSE')
    m,files=role();source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m)
    profile='gcp-c4d-static01-v1';worker=ID+'-01';packet=output/'packet-01'
    r=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
    variant=dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],
        ticket_sha256=r['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),native_root=r['native_root'],
        runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
        stager=str(ROOT/'tools/native_package_v3.py'),stager_sha256=sha((ROOT/'tools/native_package_v3.py').read_bytes()),
        stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256=sha((ROOT/'tools/native_package_v2.py').read_bytes()))],
        max_seconds=3700)
    ticket=dict(schema='gfn16-global-ticket-v1',id=ID,owner='fault-fanout',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=4,minimum_ram_rationale='Bounded AW8 one-field exploration; existing4GiB envelope, no measured peak claim.',
        est_minutes=10,promotion_bound=False,test_role='deliberate_fault',packages=[variant],
        after=[NORMAL_ID],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket)
    return dict(status='fault_source_prepared_not_submitted',id=ID,ticket=str(output/'global-ticket-v1.json'),
                manifest_sha256=sha(manifest.read_bytes()),top=m['build']['top'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--budget',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.budget),indent=2))
