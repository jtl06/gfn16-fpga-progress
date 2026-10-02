"""Exact reviewed A-next direct prototype plain fit on released F16 slotD."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
FPGA=Path(__file__).resolve().parents[1]
DEST=FPGA/'artifacts/plain-anext-f16-launch-v1'
NAME='anext-aw16-9668ps-f16-plain-v1'
TOOLS='fit-plain-anext-tools-v1'
UNIT='gfn16-plain-anext-9668ps-v1.service'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def main():
 assert not DEST.exists();DEST.mkdir()
 source=FPGA/'artifacts/anext-9668ps-f16-plain-v2'
 assert sha(source/'project/manifest.json')=='41b2fe9d4eb5648f4728ff89cd2ce5a0c43242d6ef6bc0b6b8818f38b9c37742'
 assert sha(source/'inventory.json')=='07b158b5ce8cbe8d108f7008be4887bf68b58d1618e46f0a5a56bc259bb28f3d'
 project=DEST/NAME;shutil.copytree(source/'project',project)
 fit=load('plain',FPGA/'cloud/plain_fit_v2.py');meter=load('meter',FPGA/'cloud/host_hours_azure_v3.py')
 context=fit.runner(fit.HOSTS['gfn16-azure-f16'],'gfn16-azure-f16',False).verify_project(project)
 inventory=json.loads((source/'inventory.json').read_text());structural=load('structural',FPGA/'tools/prefit_structural_guard_v1.py')
 assert not structural.source_inventory(project,inventory)['findings']
 tools=DEST/TOOLS;tools.mkdir()
 for name in ('plain_fit_v2.py','aws_fit_v6.py','plain-fit-context.sh'):shutil.copy2(FPGA/'cloud'/name,tools/name)
 shutil.copy2(FPGA/'tools/prefit_structural_guard_v1.py',tools/'prefit_structural_guard_v1.py')
 shutil.copy2(FPGA/'artifacts/plain-f16-launch-v1/fit-plain-tools-v1/topology.json',tools/'topology.json')
 quote='results/throughput-20260929/azure-restart-recovery-1004-v1/provider-inputs.json'
 transition='results/throughput-20260929/azure-sim-resize-r49-v1/rate-transition-v1.json'
 budget=meter.make_budget('gfn16-azure-f16',21780,quote,sha(FPGA/quote),context['manifest_sha256'],transition_path=transition,transition_sha256=sha(FPGA/transition))
 admitted=meter.validate_budget(budget,'gfn16-azure-f16',21780,source_sha256=context['manifest_sha256'])
 for path,pin in meter.evidence_pins(budget).items():
  assert sha(FPGA/path)==pin;dest=tools/'fpga'/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(FPGA/path,dest)
 request=dict(schema='plain-fit-request-v1',host='gfn16-azure-f16',project_name=NAME,unit=UNIT,slot='d',mode='full',project=context,
  host_hours_budget=budget,topology_sha256=sha(tools/'topology.json'),structural_spec=inventory,promotion_allowed=False)
 save(tools/'request.json',request);save(DEST/'host-hours.json',admitted)
 with tarfile.open(DEST/'package.tar.gz','w:gz') as t:
  for name in (NAME,TOOLS):t.add(DEST/name,arcname=name)
 result=dict(unit=UNIT,project_name=NAME,request_sha256=sha(tools/'request.json'),manifest_sha256=context['manifest_sha256'],archive_sha256=sha(DEST/'package.tar.gz'),
  source_preparer_sha256=sha(__file__),native_prerequisite_sha256=sha(FPGA/'results/throughput-20260929/anext-v1-representative-aw16-native-independent-v1.json'))
 save(DEST/'prepared.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
