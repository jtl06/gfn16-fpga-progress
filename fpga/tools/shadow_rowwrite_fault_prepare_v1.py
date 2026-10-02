"""Prepare separate stale-owner/global-quarantine/reset fault role on frozen RTL."""
import argparse,hashlib,importlib.util,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NORMAL=ROOT/'results/throughput-20260929/trackS-shadow-rowwrite-v1/normal-role-v1'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
def prepare(out):
    assert not out.exists() and not (ROOT/'docs/briefs/PAUSE').exists() and not (ROOT/'queue/PAUSE').exists()
    out.mkdir(parents=True);source=out/'source/fpga';source.mkdir(parents=True)
    manifest=json.loads((NORMAL/'manifest.json').read_text())
    for name,pin in manifest['sources'].items():
        original=NORMAL/'source/fpga'/name;assert sha(original)==pin
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(original.read_bytes())
    for name,path in [('rtl/tb/shadow_rowwrite_fault_v1.cpp',ROOT/'rtl/tb/shadow_rowwrite_fault_v1.cpp'),
                      ('lineage/shadow_rowwrite_fault_prepare_v1.py',Path(__file__).resolve())]:
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(path.read_bytes())
        manifest['sources'][name]=sha(target)
    manifest.update(source_root=str(source),output_parent=str(out/'UNBOUND_OUTPUT'))
    manifest['build']['cpp_source']='rtl/tb/shadow_rowwrite_fault_v1.cpp'
    manifest['steps']=[dict(name='shadow-row-fault',argv=['{exe}'],expected_returncode=0,
        expected_stdout='SHADOW_ROW_FAULT_PASS aliases=6 quarantine=global reset_retains_payload=1\n',expected_stderr=''),
        dict(name='shadow-row-negative-oracle',argv=['{exe}','--negative-oracle'],expected_returncode=1,expected_stdout='',
        expected_stderr='SHADOW_ROW_NEGATIVE_ORACLE_REJECT\n')]
    manifest['scope']='Frozen normal RTL, deliberate full-owner ordinal/epoch/gen/context aliases and disabled-owner denial; unrelated-context progress before wrapper global quarantine; same-context commit/capture rejection; global quarantine/reset eligibility invalidation and payload retention; independent oracle mutant. No local shared-fault recovery claim.'
    dump(out/'manifest.json',manifest)
    spec=importlib.util.spec_from_file_location('_shadow_fault_native',ROOT/'tools/native_class_package_v2.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    budget=ROOT/'results/throughput-20260929/trackS-p16-diet-analysis-v1/fifo-ram-v1/normal-role-v1/budget.json'
    packet=out/'packet-01';worker.prepare(out/'manifest.json',source,'gcp-c4d-static01-v1','s4-shadow-row-fault-01-v1','run',packet,budget)
    native=json.loads((packet/'ticket.json').read_text());ticket=json.loads((NORMAL/'global-ticket.json').read_text())
    ticket.update(id='s4-shadow-row-fault-q1-v1',created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),test_role='deliberate_fault',
                  source_gate=dict(scope=manifest['scope'],promotion_allowed=False));ticket.pop('rtl_readiness',None)
    ticket['packages'][0].update(archive=str(packet/'package.tar.gz'),sha256=sha(packet/'package.tar.gz'),ticket_sha256=sha(packet/'ticket.json'),
        manifest_sha256=native['manifest_sha256'],worker_id=native['id'],native_root=native['native_root'])
    dump(out/'global-ticket.json',ticket);print(out/'global-ticket.json')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);prepare(parser.parse_args().output.resolve())
