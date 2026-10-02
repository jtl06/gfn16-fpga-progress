"""Cold-only native two-context actual on-chip dependent arithmetic gate."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from fpga.reference import stream27_warm_contexts as core
from fpga.reference import stream27_threefield_contexts_native as arithmetic
from fpga.reference import stream27_two_context_native as base
from fpga.tools import native_class_package_v2 as package
ROOT=core.ROOT
SELF='reference/stream27_warm_contexts_native.py'
CPP='rtl/tb/stream27_warm_contexts.cpp'
HEADER='rtl/tb/s4_warm_contexts_config_v1.h'
FROZEN=ROOT/'results/throughput-20260929/trackS-threefield-contexts-v1/aw5-p8-normal-v2'
def role(aw=5,p=8):
    base.need(aw==5 and p==8,'WARM_FIRST_RESOLVED_GEOMETRY')
    m,files=arithmetic.role(aw,p);bundle=core.prepare(1<<aw,p,contexts=2);g=bundle['geometry']
    files={k:v for k,v in files.items() if not (k.startswith('rtl/') and k.endswith('.sv'))}
    files.update({'rtl/'+name:text.encode() for name,text in bundle['files'].items()})
    old_header=files.pop(arithmetic.HEADER).decode();oldtop=m['build']['top'];files[HEADER]=old_header.replace('V'+oldtop,'V'+bundle['top']).encode()
    frozen_manifest=json.loads((FROZEN/'manifest.json').read_text());raw=(FROZEN/'source/fpga'/arithmetic.CPP).read_bytes()
    base.need(base.sha(raw)==frozen_manifest['sources'][arithmetic.CPP],'WARM_FROZEN_ARITHMETIC_BENCH')
    files['lineage/'+arithmetic.CPP]=raw
    files[arithmetic.CPP]=raw.replace(b'#include "s4_threefield_contexts_config_v1.h"',b'#include "s4_warm_contexts_config_v1.h"',1)
    files[CPP]=(ROOT/CPP).read_bytes()
    for path in bundle['source_dependencies']:
        raw=(ROOT/path).read_bytes();base.need(base.sha(raw)==bundle['source_sha256'][path],'WARM_DEPENDENCY_DRIFT:'+path);files['lineage/'+path]=raw
    files['lineage/'+SELF]=(ROOT/SELF).read_bytes()
    stdout=f'S4_WARM_CONTEXTS_PASS aw={aw} p={p} counts=3/5 cold_frames=2 cold_corrections=2 internal_frames=6 internal_corrections=6 coefficients={8*(1<<aw)} digits={8*(1<<aw)} boundary_pairs={8*p} final_rows={2*g["rows"]} final_boundaries=2 final_owner_bits=56 a_done_b_active=1 onchip_feedback=1 canonical_host=0\n'
    m['build'].update(top=bundle['top'],cpp_source=CPP,sv_sources=['rtl/'+name for name in bundle['rtl_sources']],parameters=bundle['parameters'])
    m['steps']=[dict(name='warm-contexts-normal',argv=['{exe}'],expected_returncode=0,expected_stdout=stdout,expected_stderr='')]
    m['sources']={name:base.sha(raw) for name,raw in files.items()}
    details=m.pop('threefield_contexts');details.update(source_sha256=bundle['source_sha256'],generated_sha256=bundle['generated_sha256'],
        scope='Actual on-chip dependent arithmetic after two cold frames/corrections only; per-context counts3/5/full32 sequence/final56owner; no canonical host publication/readback or physical qualification',
        bench_reuse='Frozen arithmetic CPP with include filename only changed to unique warm config; exact original preserved in lineage',control_contract=bundle['control_contract'])
    m['warm_contexts']=details
    return m,files
def prepare(out,budget,revision=1):
    base.need(not out.exists() and not (ROOT/'docs/briefs/PAUSE').exists() and not (ROOT/'queue/PAUSE').exists(),'WARM_FRESH_PAUSE')
    m,files=role();source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    m.update(source_root=str(source),output_parent=str(out/'UNBOUND_OUTPUT'));base.dump(out/'manifest.json',m)
    ready=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');stem='s4-warm-contexts-aw5-p8';snapshot={k:v for k,v in m['sources'].items() if k.endswith('.sv')}
    readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=stem+f'-v{revision}',source_snapshot=snapshot,candidate_source_sha256=base.sha(base.canonical(snapshot)),rtl_ready_at_utc=ready)
    base.dump(out/'source-readiness.json',readiness);packet=out/'packet-01'
    prepared=package.prepare(out/'manifest.json',source,'gcp-c4d-static01-v1',stem+f'-normal-01-v{revision}','run',packet,budget)
    nt=json.loads((packet/'ticket.json').read_text());ticket=json.loads((FROZEN/'global-ticket.json').read_text())
    ticket.update(id=stem+f'-normal-q1-v{revision}',candidate_id=readiness['candidate_id'],created=ready,test_role='normal',rtl_readiness=readiness,source_gate=dict(scope=m['warm_contexts']['scope'],promotion_allowed=False))
    ticket['packages'][0].update(archive=str(packet/'package.tar.gz'),sha256=prepared['archive_sha256'],ticket_sha256=prepared['ticket_sha256'],manifest_sha256=nt['manifest_sha256'],worker_id=nt['id'],native_root=nt['native_root'])
    base.dump(out/'global-ticket.json',ticket);print(out/'global-ticket.json')
if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--output',type=Path,required=True);q.add_argument('--budget',type=Path,required=True);q.add_argument('--revision',type=int,default=1)
    a=q.parse_args();prepare(a.output.resolve(),a.budget.resolve(),a.revision)
