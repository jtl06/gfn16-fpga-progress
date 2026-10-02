"""Exact r53 P16-c one-field sizing packet, no pre-fit diagnostic gate."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile

FPGA=Path(__file__).resolve().parents[1]
DEST=FPGA/'artifacts/plain-p16c-f16-v1'
NAME='stream27-p16c-aw16-p16-f0-plain-v1'
TOOLS='fit-plain-p16c-tools-v1'
UNIT='gfn16-plain-p16c-aw16-v1.service'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def main():
 assert not DEST.exists();DEST.mkdir()
 fit=load('plain',FPGA/'cloud/plain_fit_v1.py');meter=load('meter',FPGA/'cloud/host_hours_azure_v3.py')
 source=FPGA/'artifacts/stream27-p16c-aw16-p16-f0-prepared-v2/project'
 assert sha(source/'manifest.json')=='9c8b31cb54f95bd797ec7f53ba95bf3a845bbbe054d157dc861524fd7e32d825'
 project=DEST/NAME;shutil.copytree(source,project)
 (project/'run.tcl').write_text(fit.FULL_TCL)
 m=json.loads((project/'manifest.json').read_text());m['control_sha256']={k:sha(project/k) for k in ('probe.qsf','probe.qpf','probe.sdc','run.tcl')}
 m.update(status='r53_component_sizing_plain_prepared_not_executed',promotion_allowed=False,usable_clock_mhz=None)
 (project/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
 tools=DEST/TOOLS;tools.mkdir()
 for name in ('plain_fit_v1.py','aws_fit_v6.py','plain-fit-context.sh'):shutil.copy2(FPGA/'cloud'/name,tools/name)
 shutil.copy2(FPGA/'artifacts/plain-f16-launch-v1/fit-plain-tools-v1/topology.json',tools/'topology.json')
 context=fit.runner(fit.HOSTS['gfn16-azure-f16'],'gfn16-azure-f16',False).verify_project(project)
 provider=meter.provider_inputs();save(DEST/'provider-inputs.json',provider)
 quote=str((DEST/'provider-inputs.json').relative_to(FPGA))
 transition='results/throughput-20260929/azure-sim-resize-r49-v1/rate-transition-v1.json'
 budget=meter.make_budget('gfn16-azure-f16',21780,quote,sha(FPGA/quote),context['manifest_sha256'],transition_path=transition,transition_sha256=sha(FPGA/transition))
 admitted=meter.validate_budget(budget,'gfn16-azure-f16',21780,source_sha256=context['manifest_sha256'])
 for path,pin in meter.evidence_pins(budget).items():
  assert sha(FPGA/path)==pin;dest=tools/'fpga'/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(FPGA/path,dest)
 request=dict(schema='plain-fit-request-v1',host='gfn16-azure-f16',project_name=NAME,unit=UNIT,slot='d',mode='full',project=context,
   host_hours_budget=budget,topology_sha256=sha(tools/'topology.json'),exemption='component_sizing_probe',promotion_allowed=False)
 save(tools/'request.json',request);save(DEST/'host-hours.json',admitted)
 with tarfile.open(DEST/'package.tar.gz','w:gz') as t:
  for name in (NAME,TOOLS):t.add(DEST/name,arcname=name)
 result=dict(unit=UNIT,project_name=NAME,tools=TOOLS,request_sha256=sha(tools/'request.json'),manifest_sha256=context['manifest_sha256'],
   archive_sha256=sha(DEST/'package.tar.gz'),provider_observed=provider['observed_at_utc'],source_preparer_sha256=sha(__file__))
 save(DEST/'prepared.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
