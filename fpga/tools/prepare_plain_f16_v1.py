"""Three source-bound plain r53 F16 jobs, no per-job budget hold."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
FPGA=Path(__file__).resolve().parents[1]
DEST=FPGA/'artifacts/plain-f16-launch-v1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n')

def main():
 assert not DEST.exists() and not(FPGA/'docs/briefs/PAUSE').exists();DEST.mkdir()
 fit=load('plain_fit_source',FPGA/'cloud/plain_fit_v1.py');meter=load('meter_plain',FPGA/'cloud/host_hours_azure_v3.py')
 provider=meter.provider_inputs();save(DEST/'provider-inputs.json',provider)
 quote=str((DEST/'provider-inputs.json').relative_to(FPGA));quote_sha=sha(FPGA/quote)
 tools=DEST/'fit-plain-tools-v1';tools.mkdir()
 for name in ('plain_fit_v1.py','aws_fit_v6.py','plain-fit-context.sh','azure_c1_fit_continue_v4.py'):
  shutil.copy2(FPGA/'cloud'/name,tools/name)
 oldobs=json.loads((FPGA/'artifacts/core27-crtmont-c1-8ns-azure-v3-prepared/native-admission-observation-v1.json').read_text())
 topology={k:oldobs[k] for k in ('hostname','observed_at','cpus','memory_total_bytes')};topology['slots']=fit.HOSTS['gfn16-azure-f16']['slots'];save(tools/'topology.json',topology)
 jobs=[('c1', 'a','core27-crtmont-c1-8ns-plain-v1','gfn16-plain-c1-8ns-v1.service','core27-crtmont-c1-8ns-azure-v4-prepared/project','saved_syn'),
       ('t5b-seed2','b','core27-t5b-seed2-95ns-plain-v1','gfn16-plain-t5b-seed2-95ns-v1.service','t5b-seed2-95ns-azure-v1/project','full'),
       ('t5b-seed3','c','core27-t5b-seed3-95ns-plain-v1','gfn16-plain-t5b-seed3-95ns-v1.service','t5b-seed3-95ns-azure-v1/project','full')]
 reports=[]
 for short,slot,name,unit,source,mode in jobs:
  project=DEST/name;shutil.copytree(FPGA/'artifacts'/source,project)
  (project/'run.tcl').write_text(fit.CONTINUE_TCL if mode=='saved_syn' else fit.FULL_TCL)
  qsf=(project/'probe.qsf').read_text();flag='set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON\n'
  if flag not in qsf:qsf+=flag
  (project/'probe.qsf').write_text(qsf)
  m=json.loads((project/'manifest.json').read_text());m['control_sha256']={k:sha(project/k) for k in ('probe.qsf','probe.qpf','probe.sdc','run.tcl')}
  m.update(status='plain_r53_prepared_no_execution',native_DA_gate=dict(post_fit_only=True),promotion_allowed=False,usable_clock_mhz=None,throughput=None)
  (project/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
  context=dict(manifest_sha256=sha(project/'manifest.json'),source_sha256=m['source_sha256'],control_sha256={k:sha(project/k) for k in ('manifest.json','probe.qsf','probe.qpf','probe.sdc','run.tcl')},qsf_parameters=dict(AW=16,NTT_LANES=64))
  budget=meter.make_budget('gfn16-azure-f16',21780,quote,quote_sha,context['manifest_sha256'])
  admitted=meter.validate_budget(budget,'gfn16-azure-f16',21780,source_sha256=context['manifest_sha256'])
  for path,pin in meter.evidence_pins(budget).items():
   assert sha(FPGA/path)==pin;dest=tools/'fpga'/path;dest.parent.mkdir(parents=True,exist_ok=True)
   if not dest.exists():shutil.copy2(FPGA/path,dest)
  approved=dict(schema='plain-fit-request-v1',host='gfn16-azure-f16',project_name=name,unit=unit,slot=slot,mode=mode,
    project=context,host_hours_budget=budget,topology_sha256=sha(tools/'topology.json'),exemption='constraint_seed_only',promotion_allowed=False)
  if mode=='saved_syn':approved['original_tree_sha256']=json.loads((FPGA/'artifacts/core27-crtmont-c1-8ns-azure-v3-prepared/full-original-tree-v1.json').read_text())
  save(tools/(short+'-request.json'),approved);save(DEST/(short+'-host-hours.json'),admitted)
  reports.append(dict(role=short,unit=unit,slot=slot,project_name=name,request_file=short+'-request.json',request_sha256=sha(tools/(short+'-request.json')),manifest_sha256=context['manifest_sha256']))
 with tarfile.open(DEST/'package.tar.gz','w:gz') as t:
  for name in [row['project_name'] for row in reports]+['fit-plain-tools-v1']:t.add(DEST/name,arcname=name)
 save(DEST/'prepared.json',dict(jobs=reports,archive_sha256=sha(DEST/'package.tar.gz'),source_preparer_sha256=sha(__file__),provider_observed=provider['observed_at_utc']))
 print(json.dumps(dict(jobs=reports,archive_sha256=sha(DEST/'package.tar.gz'),provider_observed=provider['observed_at_utc']),indent=2))

if __name__=='__main__':main()
