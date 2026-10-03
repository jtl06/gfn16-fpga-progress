"""ONE immutable-role quota retry; public intake needs exact infra proof."""
import json
from pathlib import Path
from . import stream27_r15_canonical_foldstage_native as n

ORIGINAL=n.identifier(16,'fault')
SUCCESSOR='s4-p16-r15-canonical-foldstage-aw16-fault-q1-v2'

def prepare():
    original_dir=n.BASE/'full-fault';out=n.BASE/'full-fault-infra-v2'
    n.b.need(not out.exists(),'FRESH_INFRA_SUCCESSOR')
    raw=(original_dir/'manifest.json').read_bytes();m=json.loads(raw)
    evidence=n.ROOT/'queue/evidence'/ORIGINAL/'attempt-0/collected'
    report=json.loads((evidence/'queue-report.json').read_bytes())
    n.b.need(report['error']=="QuotaError('global blocks below outstanding reservations plus floor')" and
      not (evidence/'output').exists() and (evidence/'runner.stdout').read_bytes()==b'','ACTUAL_INITIAL_QUOTA_NO_NATIVE')
    source=out/'source/fpga';source.mkdir(parents=True)
    for name,pin in m['sources'].items():
        data=(Path(m['source_root'])/name).read_bytes();n.b.need(n.sha(data)==pin,'PRESERVED_CAPTURE:'+name)
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(data)
    m['source_root']=str(source);n.dump(out/'manifest.json',m)
    before={k:json.loads(raw)[k] for k in ('sources','build','probe','steps','rtl_readiness')}
    n.b.need(before=={k:m[k] for k in before},'BYTE_ROLE_CONFIG_AND_READINESS_UNCHANGED')
    return resume()

def resume():
    out=n.BASE/'full-fault-infra-v2';old=json.loads((n.BASE/'full-fault/manifest.json').read_bytes())
    m=json.loads((out/'manifest.json').read_bytes())
    n.b.need(all(m[k]==old[k] for k in ('sources','build','probe','steps','rtl_readiness')),'EXACT_FROZEN_INFRA_ROLE')
    for name,pin in m['sources'].items():n.b.need(n.sha((Path(m['source_root'])/name).read_bytes())==pin,'EXACT_INFRA_SOURCE:'+name)
    n.b.need(not (out/'global-ticket.json').exists(),'NO_DUPLICATE_INFRA_PACKAGING')
    result=n.package(out,16,'fault',logical_id=SUCCESSOR)
    # Append recovery association to this never-submitted fresh logical input,
    # not the original DONE or any existing immutable worker packet.
    ticket=out/'global-ticket.json';t=json.loads(ticket.read_bytes());t['infra_retry_of']=ORIGINAL
    # Recovery field is metadata outside source/worker archive. Caller emits
    # it as an additive input file; existing global-ticket is retained too.
    n.dump(out/'infra-global-ticket.json',t)
    from fpga.tools import global_queue_v1 as q
    original=q.registry()[ORIGINAL]
    n.b.need(q.expected_identity(original)==q.expected_identity(t),'EXACT_FUNCTIONAL_IDENTITY')
    result.update(ticket=str(out/'infra-global-ticket.json'),infra_retry_of=ORIGINAL,
      exact_role_identity=q.expected_identity(t),status='PREPARED_HOLD_FOR_INFRA_PROOF_READY')
    n.dump(out/'owner-preparation.json',result)
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');a=p.parse_args()
    print(json.dumps(resume() if a.resume else prepare(),indent=2))
