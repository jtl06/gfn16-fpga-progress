"""Frozen v2 RTL start-edge diagnostic; never changes numeric expectations."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from fpga.reference import stream27_two_context_native as native
from fpga.tools import native_class_package_v2 as package
ROOT=native.ROOT
FROZEN=ROOT/'results/throughput-20260929/trackS-two-context-field-v1/aw5-p8-f0-normal-v2'
CPP='rtl/tb/stream27_two_context_start_diag.cpp'
def prepare(out,budget,duplicate=False):
    native.need(not out.exists() and not (ROOT/'docs/briefs/PAUSE').exists() and not (ROOT/'queue/PAUSE').exists(),'TWO_DIAG_FRESH_PAUSE')
    m=json.loads((FROZEN/'manifest.json').read_text());source=out/'source/fpga';source.mkdir(parents=True)
    for name,pin in m['sources'].items():
        raw=(FROZEN/'source/fpga'/name).read_bytes();native.need(native.sha(raw)==pin,'TWO_DIAG_FROZEN_SOURCE')
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
    for name,path in [(CPP,ROOT/CPP),('lineage/reference/stream27_two_context_start_diag.py',Path(__file__).resolve())]:
        raw=path.read_bytes();target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
        m['sources'][name]=native.sha(raw)
    m.update(source_root=str(source),output_parent=str(out/'UNBOUND_OUTPUT'));m['build']['cpp_source']=CPP
    stem='s4-two-duplicate' if duplicate else 's4-two-start-diag'
    stdout=('S4_TWO_DUPLICATE_PASS held_second_edge=1 registered_fault=1 unrelated_context_stopped=1 clock_edges=3\n' if duplicate else
        'S4_TWO_START_DIAG registered=0 pending_held=1 pending_after_drop=0 owners=1 clock_edges=1\n')
    m['steps']=[dict(name=stem,argv=['{exe}','--duplicate'] if duplicate else ['{exe}'],expected_returncode=0,expected_stdout=stdout,expected_stderr='')]
    m['two_context']['scope']=('Unchanged v2 RTL deliberate repeated FIRST/correction held through second rising edge: registered global fault must also stop unrelated context; no context-local recovery.' if duplicate else
        'Unchanged v2 RTL start-edge diagnostic: differentiate settled pre-edge transaction checks from prospective duplicate requests held afterNBA; no numeric qualification or fault waiver.')
    native.dump(out/'manifest.json',m);packet=out/'packet-01'
    prepared=package.prepare(out/'manifest.json',source,'gcp-c4d-static01-v1',stem+'-01-v1','run',packet,budget)
    nt=json.loads((packet/'ticket.json').read_text());q=json.loads((FROZEN/'global-ticket.json').read_text())
    q.update(id=stem+'-q1-v1',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),test_role='deliberate_fault',
        source_gate=dict(scope=m['two_context']['scope'],promotion_allowed=False));q.pop('rtl_readiness',None)
    q['packages'][0].update(archive=str(packet/'package.tar.gz'),sha256=prepared['archive_sha256'],ticket_sha256=prepared['ticket_sha256'],
        manifest_sha256=nt['manifest_sha256'],worker_id=nt['id'],native_root=nt['native_root'])
    native.dump(out/'global-ticket.json',q);print(out/'global-ticket.json')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--budget',type=Path,required=True)
    p.add_argument('--duplicate',action='store_true')
    a=p.parse_args();prepare(a.output.resolve(),a.budget.resolve(),a.duplicate)
