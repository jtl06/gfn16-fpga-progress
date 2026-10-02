"""Package a frozen P16 timing bundle, retaining the exact full9 reference."""
import argparse,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
from fpga.tools import native_class_package_v2 as package
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
DONOR=ROOT/'results/throughput-20260929/s4-p16-diet-whole-full9-normal-v1/input'
TEMPLATE=ROOT/'results/throughput-20260929/trackS-boundary-inputreg-v1/normal-role-v1/global-ticket.json'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def prepare(bundle,output,budget,identifier,freeze):
 b=json.loads(Path(bundle).read_text());out=Path(output).resolve()
 assert not out.exists() and not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE'))
 assert b['parameters']['P']==16 and b['parameters']['AW']==16
 assert {n:sha(s.encode()) for n,s in b['files'].items()}==b['generated_sha256']
 m=json.loads((DONOR/'manifest.json').read_text());files={}
 for name,pin in m['sources'].items():
  raw=(DONOR/'source/fpga'/name).read_bytes();assert sha(raw)==pin
  if not name.endswith('.sv'):files[name]=raw
 g=b['geometry'];assert (g['first_digit'],g['warm_interval'],g['carry_done'])==(8459,8460,12558)
 flags={k:v for k,v in b['parameters'].items() if k not in ('AW','P','CONTEXTS')}
 counts=dict(m['full_host']['counts']);counts.update(candidate_cycles=1395173,backpressure_edges=25376)
 assert counts['candidate_cycles']==(102+g['carry_done']+2+10*65536+4)+(3+7*g['warm_interval']+g['carry_done']+2+10*65536+4)
 header='rtl/tb/s4_host_chain_full_config_v1.h'
 files[header]=(f'#include <cstdint>\n#include "V{b["top"]}.h"\nusing DUT=V{b["top"]};\n'
  'constexpr unsigned AW=16,P=16,N=65536,BASE=604832956;\n'
  'constexpr uint64_t FIRST_DIGIT=8459,INTERVAL=8460,CARRY_DONE=12558,EXPECTED_CYCLES=1395173,T5B_WAIT_LIMIT=20*N+100000;\n').encode()
 cpp=m['build']['cpp_source'];assert files[cpp].count(b'S4_P16_DIET_HOST_PASS aw=16 p=16')==1
 files[cpp]=files[cpp].replace(b'S4_P16_DIET_HOST_PASS aw=16 p=16',b'S4_P16_TIMING_HOST_PASS aw=16 p=16')
 validator='reference/p16_timing_validator.py';files[validator]=(HERE/'validator.py').read_bytes()
 config=dict(aw=16,p=16,base=604832956,flags=flags,counts=counts)
 m['steps']=[dict(name='p16-timing-full9-normal',argv=['{exe}'],expected_returncode=0,
  validator=dict(source=validator,function='validate',config=config,assets={}))]
 m['build'].update(top=b['top'],parameters={**m['build']['parameters'],**b['parameters']},sv_sources=['rtl/'+n for n in b['rtl_sources']])
 m['full_host'].update(counts=counts,geometry=g,flags=flags,generated_sha256=b['generated_sha256'],source_sha256=b['source_sha256'],
  host_contract=b['host_contract'],cycle_contract=b['cycle_contract'],native_executed=False,promotion_allowed=False)
 hosts=[n for n in b['files'] if n.startswith('genefer_stream27_host_chain_aw16_p16_') and n.endswith('.sv')];assert len(hosts)==1
 m['full_host'].update(standalone_top=hosts[0][:-3],candidate_root_sha256=b['generated_sha256'][hosts[0]])
 m['full_host'].pop('standalone_generated_sha256',None)
 files.update({'rtl/'+n:s.encode() for n,s in b['files'].items()})
 for name in b['source_dependencies']:
  raw=(ROOT/name).read_bytes();assert sha(raw)==b['source_sha256'][name];files['lineage/'+name]=raw
 files['lineage/prepare_normal.py']=Path(__file__).read_bytes()
 source=out/'source/fpga';source.mkdir(parents=True)
 for name,raw in files.items():p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
 now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
 m.update(source_root=str(source),output_parent=str(out/'UNBOUND_OUTPUT'),sources={n:sha(s) for n,s in files.items()},promotion_allowed=False,
  readiness=dict(rtl_ready_at_utc=freeze,packaged_at_utc=now))
 dump(out/'manifest.json',m);dump(out/'bundle.json',b)
 packet=out/'packet-01';worker=identifier.replace('-q1-','-01-')
 package.prepare(out/'manifest.json',source,'gcp-c4d-static01-v1',worker,'run',packet,Path(budget).resolve())
 q=json.loads(TEMPLATE.read_text());native=json.loads((packet/'ticket.json').read_text())
 q.update(id=identifier,candidate_id=identifier.replace('-normal-q1',''),created=now,est_minutes=20,minimum_ram_gib=8)
 q['packages'][0].update(archive=str(packet/'package.tar.gz'),sha256=sha((packet/'package.tar.gz').read_bytes()),ticket_sha256=sha((packet/'ticket.json').read_bytes()),manifest_sha256=native['manifest_sha256'],worker_id=worker,native_root=native['native_root'])
 pins={k:v for k,v in m['sources'].items() if k.endswith('.sv')}
 q['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=q['candidate_id'],source_snapshot=pins,candidate_source_sha256=sha(json.dumps(pins,sort_keys=True,separators=(',',':')).encode()),rtl_ready_at_utc=freeze)
 q['source_gate']=dict(scope='Exact new P16 timing full9; no inherited qualification or clock',promotion_allowed=False)
 dump(out/'global-ticket.json',q);print(json.dumps(dict(id=identifier,rtl=len(b['rtl_sources']),freeze=freeze,packaged=now,manifest_sha256=sha((out/'manifest.json').read_bytes()))))
if __name__=='__main__':
 a=argparse.ArgumentParser();[a.add_argument('--'+n,required=True) for n in ('bundle','output','budget','id','freeze')];v=a.parse_args();prepare(v.bundle,v.output,v.budget,v.id,v.freeze)
