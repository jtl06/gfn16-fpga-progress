"""Separate P16/corr2 replica fault cohort; P8 captures remain immutable.

The frozen actual-field fault oracle is parameterized at its existing config
seam. Diagnostic injections are still real missing-FIRST and replica-setter
suppression; independent expected calendars/counters come from the P16 donor.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from . import stream27_fault_fanout_p16_native as normal
from . import stream27_fault_fanout_p16_bind as binding
from . import stream27_fault_fanout_fault_native as frozen

ROOT=normal.ROOT
SELF='reference/stream27_fault_fanout_p16_fault_native.py'
CPP='rtl/tb/stream27_fault_fanout_p16_faults.cpp'
HEADER='rtl/tb/s4_fault_fanout_config.h'
ID='s4-p16-fault-fanout-aw8-f1-c2-faults-q1-v1'
NORMAL_ID='s4-p16-fault-fanout-aw8-f1-c2-normal-q1-v1'
need,sha,dump=normal.need,normal.sha,normal.dump


def role():
    b=binding.bind(normal.donor.prepare(256,16,1,mode='warm_signed',corr_serial_bfs=2))
    g=b['geometry'];old=b['top'];top,text=frozen.diagnostic_root(b['files'][old+'.sv'],old)
    files={'rtl/'+name:value.encode() for name,value in b['files'].items() if name!=old+'.sv'}
    files['rtl/'+top+'.sv']=text.encode()
    cpp=(ROOT/frozen.CPP).read_text().replace('S4_FAULT_FANOUT','S4_P16_FAULT_FANOUT')
    need(cpp.count('aw=8 p=8 field=2')==1,'S4_P16_FAULT_FIXED_CPP_CONFIG')
    cpp=cpp.replace('aw=8 p=8 field=2','aw=8 p=16 field=1 corr_serial_bfs=2',1)
    files[CPP]=cpp.encode();files[HEADER]=(f'#include "V{top}.h"\nusing DUT=V{top};\n'
        f'constexpr unsigned P=16,T={g["rows"]},WORDS=(P*27+31)/32,POINTWISE={g["pointwise_accept"]},FIRST={g["physical_first"]},SINK={g["sink_accept"]};\n').encode()
    for name in b['source_dependencies']+[SELF,normal.SELF,frozen.SELF,frozen.CPP]:files['lineage/'+name]=(ROOT/name).read_bytes()
    footer=(f'S4_P16_FAULT_FANOUT_FAULT_PASS aw=8 p=16 field=1 corr_serial_bfs=2 cases=9 normal_frames=4 normal_rows={4*g["rows"]}'
            f' missing_first={g["pointwise_accept"]} fault_origins=2 legal_origin_commits=1 reset_aborts=2 reset_ages=10,{g["physical_first"]+2}'
            f' quiet_tail=16 canceled_rows={g["rows"]} recovery_frames=3\n')
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='/unbound/p16-fault-probe/fpga',output_parent='/unbound/p16-fault-probe/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=top,sv_sources=[name for name in files if name.startswith('rtl/') and name.endswith('.sv')],cpp_source=CPP,
            parameters={key:value for key,value in b['parameters'].items() if key!='FIELD'},cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='p16-corr2-replica-genuine-fault-reset-tail',argv=['{exe}'],expected_returncode=0,expected_stdout=footer,expected_stderr=''),
               dict(name='p16-corr2-replica-origin-typed-negative',argv=['{exe}','--negative-replica-origin'],expected_returncode=41,
                    expected_stdout=footer,expected_stderr='S4_P16_FAULT_FANOUT_TYPED_REPLICA_ORIGIN expected=3 actual=0\n')],
        test_role='deliberate_fault',fault_fanout=dict(binding=b['fault_fanout'],geometry=g,
            scope='Actual bounded P16/corr2 field missing-FIRST, legal origin commit, async reset recovery and canceled raw tails; no whole/physical qualification.'),
        lint_baseline_policy='Fresh class-gated lint; no defect/unknown warning waiver.')
    return m,files


def prepare(output,budget):
    from fpga.tools import native_class_package_v2 as package
    output=Path(output).resolve()
    need(not output.exists() and not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),'S4_P16_FAULT_PROBE_FRESH_PAUSE')
    m,files=role();source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m)
    profile='gcp-c4d-static01-v1';worker=ID+'-01';packet=output/'packet-01'
    r=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
    variant=dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],
        manifest_sha256=sha((packet/'manifest.json').read_bytes()),native_root=r['native_root'],runner='tools/native_class_package_v2.py',
        runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),stager=str(ROOT/'tools/native_package_v3.py'),
        stager_sha256=sha((ROOT/'tools/native_package_v3.py').read_bytes()),stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256=sha((ROOT/'tools/native_package_v2.py').read_bytes()))],max_seconds=3700)
    ticket=dict(schema='gfn16-global-ticket-v1',id=ID,owner='fault-fanout-p16',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=4,minimum_ram_rationale='Existing4GiB bounded P16 field exploration envelope; no peak claim.',est_minutes=10,
        promotion_bound=False,test_role='deliberate_fault',packages=[variant],after=[NORMAL_ID],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket)
    return dict(status='fault_source_prepared_not_submitted',id=ID,ticket=str(output/'global-ticket-v1.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--budget',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.budget),indent=2))
