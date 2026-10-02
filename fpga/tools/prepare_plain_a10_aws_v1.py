"""Ready canonical A10 one-field wrapper to released AWS slotB."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import types
FPGA=Path(__file__).resolve().parents[1]
DEST=FPGA/'artifacts/plain-a10-aws-launch-v1'
NAME='a10-aw16-f0-registered-aws-plain-v1'
TOOLS='fit-plain-aws-tools-v1'
UNIT='gfn16-plain-a10-aw16-v1.service'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def main():
 assert not DEST.exists();DEST.mkdir()
 source=FPGA/'results/throughput-20260929/a10-field-physical-probe-v1/project-workers6'
 assert sha(source/'manifest.json')=='69f75e841081af51ada7173d6dc6f1465b5a9fe17655cd22c7a8c18f1be40da2'
 project=DEST/NAME;shutil.copytree(source,project)
 raw=(FPGA/'cloud/aws_fit_v6.py').read_text().replace("manifest['compile_processors']==4","manifest['compile_processors']==6").replace("assignment('NUM_PARALLEL_PROCESSORS')==['4']","assignment('NUM_PARALLEL_PROCESSORS')==['6']")
 verify=types.ModuleType('source_only_sixworkers');exec(compile(raw,'frozen_v6[local_source]','exec'),verify.__dict__)
 context=verify.verify_project(project)
 request=dict(schema='plain-fit-request-v1',host='gfn16-aws-m8i',project_name=NAME,unit=UNIT,slot='b',mode='full',project=context,
  topology_sha256=sha(FPGA/'artifacts/plain-aws-pair-v1/fit-plain-aws-tools-v1/topology.json'),exemption='component_sizing_probe',promotion_allowed=False)
 tools=DEST/TOOLS;tools.mkdir();save(tools/'a10-request.json',request)
 with tarfile.open(DEST/'package.tar.gz','w:gz') as t:
  t.add(project,arcname=NAME);t.add(tools/'a10-request.json',arcname=TOOLS+'/a10-request.json')
 result=dict(unit=UNIT,project_name=NAME,request_sha256=sha(tools/'a10-request.json'),archive_sha256=sha(DEST/'package.tar.gz'),
  reused_plain_runner_sha256='6ae141be72ccfdc77b2035d9b7347e5f555b37e94b4d7a7476ccfb3530d9883e',source_preparer_sha256=sha(__file__))
 save(DEST/'prepared.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
