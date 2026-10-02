"""Exact A4b whole-core/P8-b sizing pair on existing AWS two six-core slots."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
import types
FPGA=Path(__file__).resolve().parents[1]
DEST=FPGA/'artifacts/plain-aws-pair-v1'
TOOLS='fit-plain-aws-tools-v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def main():
 assert not DEST.exists();DEST.mkdir()
 fit=load('plain',FPGA/'cloud/plain_fit_v2.py');meter=load('meter',FPGA/'cloud/host_hours_admit_v1.py')
 admitted=meter.admit('aws-m8azn',21780);save(DEST/'host-hours.json',admitted)
 tools=DEST/TOOLS;tools.mkdir()
 for name in ('plain_fit_v2.py','aws_fit_v6.py','plain-fit-context.sh'):shutil.copy2(FPGA/'cloud'/name,tools/name)
 shutil.copy2(FPGA/'tools/prefit_structural_guard_v1.py',tools/'prefit_structural_guard_v1.py')
 shutil.copy2(FPGA/'cloud/aws-topology-plain-0944-v1.json',tools/'topology.json')
 for p,pin in admitted['source_evidence_sha256'].items():
  p=Path(p);assert sha(p)==pin;dest=tools/'fpga'/p.relative_to(FPGA);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
 raw=(FPGA/'cloud/aws_fit_v6.py').read_text().replace("manifest['compile_processors']==4","manifest['compile_processors']==6").replace("assignment('NUM_PARALLEL_PROCESSORS')==['4']","assignment('NUM_PARALLEL_PROCESSORS')==['6']")
 verify=types.ModuleType('plain_local_source_verifier');exec(compile(raw,'frozen_v6[local_source_checks]','exec'),verify.__dict__)
 jobs=[('a4b','a','track-a4b-aw16-10ns-aws-plain-v1','gfn16-plain-a4b-10ns-v1.service','artifacts/a4b-10ns-aws-plain-v1/project'),
       ('p8b','b','stream27-p8b-aw16-p8-f0-aws-plain-v1','gfn16-plain-p8b-aw16-v1.service','artifacts/stream27-p8b-aw16-p8-f0-prepared-v1/project')]
 reports=[]
 for role,slot,name,unit,path in jobs:
  source=FPGA/path;project=DEST/name;shutil.copytree(source,project)
  if role=='p8b':
   qsf=(project/'probe.qsf').read_text();assert qsf.count('NUM_PARALLEL_PROCESSORS 4')==1
   (project/'probe.qsf').write_text(qsf.replace('NUM_PARALLEL_PROCESSORS 4','NUM_PARALLEL_PROCESSORS 6'))
   (project/'run.tcl').write_text(fit.FULL_TCL)
   m=json.loads((project/'manifest.json').read_text());m['compile_processors']=6;m['control_sha256']={k:sha(project/k) for k in ('probe.qsf','probe.qpf','probe.sdc','run.tcl')}
   m.update(status='r53_plain_aws_component_sizing_not_executed',promotion_allowed=False,usable_clock_mhz=None)
   (project/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
  context=verify.verify_project(project)
  request=dict(schema='plain-fit-request-v1',host='gfn16-aws-m8i',project_name=name,unit=unit,slot=slot,mode='full',project=context,
   topology_sha256=sha(tools/'topology.json'),promotion_allowed=False)
  if role=='a4b':
   inventory=json.loads((FPGA/'artifacts/a4b-10ns-aws-plain-v1/inventory.json').read_text());request['structural_spec']=inventory
   structure=load('structural',FPGA/'tools/prefit_structural_guard_v1.py');assert not structure.source_inventory(project,inventory)['findings']
  else:request['exemption']='component_sizing_probe'
  save(tools/(role+'-request.json'),request)
  reports.append(dict(role=role,unit=unit,slot=slot,project_name=name,request_file=role+'-request.json',request_sha256=sha(tools/(role+'-request.json')),manifest_sha256=context['manifest_sha256']))
 with tarfile.open(DEST/'package.tar.gz','w:gz') as t:
  for name in [j['project_name'] for j in reports]+[TOOLS]:t.add(DEST/name,arcname=name)
 result=dict(jobs=reports,tools=TOOLS,archive_sha256=sha(DEST/'package.tar.gz'),source_preparer_sha256=sha(__file__),runner_sha256=sha(FPGA/'cloud/plain_fit_v2.py'))
 save(DEST/'prepared.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
