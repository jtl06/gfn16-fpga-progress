"""Mechanical private-copy continuation packet from the preserved v3 phase."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile

FPGA=Path(__file__).resolve().parents[1]
V3=FPGA/'artifacts/core27-crtmont-c1-8ns-azure-v3-prepared'
DEST=FPGA/'artifacts/core27-crtmont-c1-8ns-azure-v4-prepared'
REMOTE=Path('/home/azureuser/gfn16-worker/c1-fit-tools-v4')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')

def main():
 assert not DEST.exists() and not (FPGA/'docs/briefs/PAUSE').exists()
 continuation=load('continue_c1',FPGA/'cloud/azure_c1_fit_continue_v4.py')
 meter=load('c1_meter3',FPGA/'cloud/host_hours_azure_v3.py')
 DEST.mkdir();project=DEST/'project';shutil.copytree(V3/'project',project)
 (project/'run.tcl').write_text(continuation.RESUME_TCL)
 manifest=json.loads((project/'manifest.json').read_text())
 manifest.update(status='prepared_saved_synthesis_continuation_no_execution',native_DA_gate=dict(required=True,phase='saved_syn_before_fit',script=str(REMOTE/'run_prefit_da_gate_v2.py')),
   original_successful_synthesis_context_sha256=continuation.PRIOR_CONTEXT,
   original_failed_loader_phase_result_sha256=continuation.PRIOR_RESULT)
 manifest['control_sha256']={n:sha(project/n) for n in ('probe.qsf','probe.qpf','probe.sdc','run.tcl')}
 (project/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 control={n:sha(project/n) for n in ('manifest.json','probe.qsf','probe.qpf','probe.sdc','run.tcl')}
 context=dict(manifest_sha256=control['manifest.json'],source_sha256=manifest['source_sha256'],control_sha256=control,qsf_parameters=dict(AW=16,NTT_LANES=64))
 tools=DEST/'tools';tools.mkdir()
 mapping={n:FPGA/'cloud'/n for n in ('azure_c1_fit_continue_v4.py','azure_c1_fit_v3.py','azure_fit_v2.py','aws_fit_v6.py','run-c1-azure-fit-v4.sh')}
 mapping.update({n:FPGA/'tools'/n for n in ('prefit_c1_constraint_only_v1.py','run_prefit_da_gate_v2.py','quartus_prefit_native_v3.py')})
 mapping['prefit_design_assistant_v2.tcl']=FPGA/'synthesis/prefit_design_assistant_v2.tcl'
 mapping['fpga/cloud/host_hours_azure_v3.py']=FPGA/'cloud/host_hours_azure_v3.py'
 pins={n:sha(p) for n,p in mapping.items()}; assert pins['run_prefit_da_gate_v2.py']==continuation.GATE_SHA
 provider='results/throughput-20260929/azure-host-hours-v3/provider-inputs-085825-v1.json'
 assert sha(FPGA/provider)=='ec9a88406f55554ca880e2e8a34ba7cb877384c7f4ea12784d415921e791de7c'
 budget=meter.make_budget('gfn16-azure-f16',21780,provider,sha(FPGA/provider),context['manifest_sha256'])
 admission=meter.validate_budget(budget,'gfn16-azure-f16',21780,source_sha256=context['manifest_sha256'])
 for name,pin in meter.evidence_pins(budget).items():
  assert sha(FPGA/name)==pin;target=tools/'fpga'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(FPGA/name,target)
 for name,path in mapping.items():
  target=tools/name;target.parent.mkdir(parents=True,exist_ok=True)
  if not target.exists():shutil.copy2(path,target)
  assert sha(target)==pins[name]
 shutil.copy2(V3/'tools/topology.json',tools/'topology.json')
 old=json.loads((V3/'tools/approval.json').read_text())
 gate=dict(scope='whole_core',helper_sha256={str(REMOTE/n):pins[n] for n in ('run_prefit_da_gate_v2.py','prefit_design_assistant_v2.tcl','quartus_prefit_native_v3.py')},tool_sha256=old['prefit_gate']['tool_sha256'])
 approved=dict(schema='c1-azure-fit-continuation-v4',status='prepared_not_executed',project_name=continuation.PROBE,
   unit='gfn16-azure-crtmont-c1-8ns-v4.service',slot='a',promotion_allowed=False,project=context,helper_sha256=pins,
   tool_sha256=old['tool_sha256'],prefit_gate=gate,topology_sha256=sha(tools/'topology.json'),host_hours_budget=budget,
   ancestor_evidence_sha256=old['ancestor_evidence_sha256'],original_tree_sha256=json.loads((V3/'full-original-tree-v1.json').read_text()))
 save(tools/'approval.json',approved);save(DEST/'host-hours-admission-v1.json',admission)
 with tarfile.open(DEST/'package-v4.tar.gz','w:gz') as t:
  t.add(project,arcname=continuation.PROBE);t.add(tools,arcname='c1-fit-tools-v4')
 report=dict(approval_sha256=sha(tools/'approval.json'),archive_sha256=sha(DEST/'package-v4.tar.gz'),manifest_sha256=context['manifest_sha256'],helper_sha256=pins,
   predecessor_invocation='a93c63b59aa04db58d6d00eedd8d6de3',source_preparer_sha256=sha(__file__))
 save(DEST/'packet-v4.json',report);print(json.dumps({k:v for k,v in report.items() if k!='helper_sha256'},indent=2))

if __name__=='__main__':main()
