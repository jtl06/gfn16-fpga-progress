"""Immutable r54 ready fits plus exact current/historical-live adoptions."""
import hashlib
import importlib.util
import json
from pathlib import Path
FPGA=Path(__file__).resolve().parents[1]
OUTPUT=FPGA/'queue/fit-r54-v1.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def load(p):return json.loads(Path(p).read_text())
def main():
 assert not OUTPUT.exists()
 path=FPGA/'tools/plain_fit_queue_v1.py'
 assert sha(path)=='d17344287b45c41dcd9e581503cbf942af4d5f8f3418fcc7881679cfd5f31f80'
 s=importlib.util.spec_from_file_location('queue',path);q=importlib.util.module_from_spec(s);s.loader.exec_module(q)
 aws='gfn16-aws-m8i';azure='gfn16-azure-f16'
 adopted=[
 ('c1-current',azure,'a','gfn16-plain-c1-8ns-v1.service','e2798d8d8fe8462e8b99b374a2df922d','artifacts/plain-f16-launch-v1/fit-plain-tools-v1/c1-request.json','fit-plain-tools-v1/c1-request.json','whole_core'),
 ('seed2-current',azure,'b','gfn16-plain-t5b-seed2-95ns-v1.service','62d5294e07cb490bb1cd65315e869abf','artifacts/plain-f16-launch-v1/fit-plain-tools-v1/t5b-seed2-request.json','fit-plain-tools-v1/t5b-seed2-request.json','whole_core'),
 ('seed3-current',azure,'c','gfn16-plain-t5b-seed3-95ns-v1.service','61944a7820f144848e5b89d4b1368154','artifacts/plain-f16-launch-v1/fit-plain-tools-v1/t5b-seed3-request.json','fit-plain-tools-v1/t5b-seed3-request.json','whole_core'),
 ('anext-current',azure,'d','gfn16-plain-anext-9668ps-v1.service','20978c00c5d04f6c9d557c3013a0a8dd','artifacts/plain-anext-f16-launch-v1/fit-plain-anext-tools-v1/request.json','fit-plain-anext-tools-v1/request.json','whole_core'),
 ('a4b-current',aws,'a','gfn16-plain-a4b-10ns-v1.service','df5aa1daeda74226b77361955a818def','artifacts/plain-aws-pair-v1/fit-plain-aws-tools-v1/a4b-request.json','fit-plain-aws-tools-v1/a4b-request.json','whole_core'),
 ('a10-current',aws,'b','gfn16-plain-a10-aw16-v1.service','6f5ef9bb7e9140ea880961b42628c88f','artifacts/plain-a10-aws-launch-v1/fit-plain-aws-tools-v1/a10-request.json','fit-plain-aws-tools-v1/a10-request.json','component_probe')]
 adopt=[]
 for key,host,slot,unit,inv,local,remote,scope in adopted:
  request=load(FPGA/local)
  adopt.append(dict(id=key,host=host,slot=slot,unit=unit,invocation_id=inv,project_name=request['project_name'],request=ref(FPGA/local),remote_request=str(Path(q.HOSTS[host]['root'])/remote),scope=scope))
 def gate(path):
  value=load(FPGA/path);assert value['status'].startswith('PASS')
  return dict(**ref(FPGA/path),fields=dict(status=value['status']))
 prerequisites=[gate('results/throughput-20260929/f2-aw16-native-independent-v1.json'),gate('results/throughput-20260929/f2-registered-native-independent-v1.json')]
 def job(key,priority,name,unit,scope,host,variant,after,requires):
  return dict(id=key,priority=priority,project_name=name,unit=unit,scope=scope,variants={host:variant},allowed_slots={host:['b' if host==aws else 'd']},after=after,requires=requires)
 jobs=[
 job('f2-parent',20,'f2-parent-aw16-f0-aws-fitq-v1','gfn16-fitq-f2-parent-v1.service','component_probe',aws,
  q.variant_descriptor(FPGA/'artifacts/f2-registered-aw16-f0-plain-workers6-v1/parent',aws,exemption='component_sizing_probe'),[],prerequisites),
 job('f2-candidate',21,'f2-candidate-aw16-f0-aws-fitq-v1','gfn16-fitq-f2-candidate-v1.service','component_probe',aws,
  q.variant_descriptor(FPGA/'artifacts/f2-registered-aw16-f0-plain-workers6-v1/candidate',aws,exemption='component_sizing_probe'),[dict(job='f2-parent',outcome='native_fit_success')],prerequisites),
 job('s4-warm-sizing',30,'s4-warm-aw16-p16-f0-f16-fitq-v1','gfn16-fitq-s4-warm-sizing-v1.service','component_probe',azure,
  q.variant_descriptor(FPGA/'artifacts/stream27-s4-aw16-p16-warm-sizing-v3/project',azure,exemption='component_sizing_probe'),[dict(job='f2-candidate',outcome='native_fit_success')],[]),
 job('anext-8ns',40,'anext-aw16-8ns-f16-fitq-v1','gfn16-fitq-anext-8ns-v1.service','whole_core',azure,
  q.variant_descriptor(FPGA/'artifacts/anext-8ns-f16-plain-v1/project',azure,structural_spec=ref(FPGA/'artifacts/anext-8ns-f16-plain-v1/inventory.json')),
  [dict(job='anext-current',outcome='native_fit_success')],[gate('results/throughput-20260929/anext-v1-representative-aw16-native-independent-v1.json')])]
 value=dict(schema='plain-fit-queue-v1',until_utc='2026-10-02T04:00:00Z',jobs=jobs,adopt=adopt)
 q.validate_queue(value);OUTPUT.parent.mkdir(parents=True,exist_ok=True)
 with OUTPUT.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
 print(json.dumps(dict(queue=str(OUTPUT),sha256=sha(OUTPUT),jobs=len(jobs),adoptions=len(adopt)),indent=2))
if __name__=='__main__':main()
