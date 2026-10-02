"""Separate fault role against frozen first real threefield normal RTL."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from fpga.reference import stream27_two_context_native as base
from fpga.tools import native_class_package_v2 as package
ROOT=base.ROOT
CPP='rtl/tb/stream27_threefield_contexts_fault.cpp'
def prepare(out,budget,revision=2):
    base.need(not out.exists() and not (ROOT/'docs/briefs/PAUSE').exists() and not (ROOT/'queue/PAUSE').exists(),'THREE_CTX_FAULT_FRESH_PAUSE')
    base.need(type(revision) is int and revision>=2,'THREE_CTX_FAULT_SUCCESSOR_ONLY')
    FROZEN=ROOT/f'results/throughput-20260929/trackS-threefield-contexts-v1/aw5-p8-normal-v{revision}'
    m=json.loads((FROZEN/'manifest.json').read_text());source=out/'source/fpga';source.mkdir(parents=True)
    for name,pin in m['sources'].items():
        raw=(FROZEN/'source/fpga'/name).read_bytes();base.need(base.sha(raw)==pin,'THREE_CTX_FAULT_FROZEN_DRIFT')
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
    for name,path in [(CPP,ROOT/CPP),('lineage/reference/stream27_threefield_contexts_fault.py',Path(__file__).resolve())]:
        raw=path.read_bytes();target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
        m['sources'][name]=base.sha(raw)
    m.update(source_root=str(source),output_parent=str(out/'UNBOUND_OUTPUT'));m['build']['cpp_source']=CPP
    m['steps']=[dict(name='threefield-contexts-fault',argv=['{exe}'],expected_returncode=0,
        expected_stdout='S4_THREE_CONTEXTS_FAULT_PASS base_denial=1 profile_generation_denial=1 held_second_edge=1 global_other_stop=3 cancellation_tails=2 cancellation_global_fault=0\n',expected_stderr='')]
    m['threefield_contexts']['scope']='Separate frozen profile-qualified core: malformed base/profile-generation/repeated-edge origin faults globally stop other context; disable/live-only cancellation tails drain raw values without eligible publication or global fault.'
    base.dump(out/'manifest.json',m);packet=out/'packet-01';stem='s4-three-contexts-aw5-p8-fault'
    prepared=package.prepare(out/'manifest.json',source,'gcp-c4d-static01-v1',stem+f'-01-v{revision}','run',packet,budget)
    nt=json.loads((packet/'ticket.json').read_text());ticket=json.loads((FROZEN/'global-ticket.json').read_text())
    ticket.update(id=stem+f'-q1-v{revision}',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),test_role='deliberate_fault',
        source_gate=dict(scope=m['threefield_contexts']['scope'],promotion_allowed=False));ticket.pop('rtl_readiness',None)
    ticket['packages'][0].update(archive=str(packet/'package.tar.gz'),sha256=prepared['archive_sha256'],ticket_sha256=prepared['ticket_sha256'],
        manifest_sha256=nt['manifest_sha256'],worker_id=nt['id'],native_root=nt['native_root'])
    base.dump(out/'global-ticket.json',ticket);print(out/'global-ticket.json')
if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--output',type=Path,required=True);q.add_argument('--budget',type=Path,required=True)
    q.add_argument('--revision',type=int,default=2)
    a=q.parse_args();prepare(a.output.resolve(),a.budget.resolve(),a.revision)
