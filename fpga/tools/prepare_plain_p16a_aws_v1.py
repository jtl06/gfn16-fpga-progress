"""Bind ready source-only P16-a to released AWS slotB, reuse frozen tools."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
FPGA=Path(__file__).resolve().parents[1]
DEST=FPGA/'artifacts/plain-p16a-aws-launch-v1'
NAME='stream27-p16a-aw16-p16-f0-aws-plain-v1'
TOOLS='fit-plain-aws-tools-v1'
UNIT='gfn16-plain-p16a-aw16-v1.service'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def main():
 assert not DEST.exists();DEST.mkdir()
 source=FPGA/'artifacts/p16a-aw16-aws-plain-v1'
 assert sha(source/'project/manifest.json')=='df72ee16a96e73ed4692b5bd1733083aef53b94c2add73ebaa1ed7ccfc232721'
 assert sha(source/'project-context.json')=='e0f89f159e28342157623ac6bd7afb23daa4eaedc10dee8dd04679d3d69a4478'
 project=DEST/NAME;shutil.copytree(source/'project',project)
 context=json.loads((source/'project-context.json').read_text())
 request=dict(schema='plain-fit-request-v1',host='gfn16-aws-m8i',project_name=NAME,unit=UNIT,slot='b',mode='full',project=context,
  topology_sha256=sha(FPGA/'artifacts/plain-aws-pair-v1/fit-plain-aws-tools-v1/topology.json'),exemption='component_sizing_probe',promotion_allowed=False)
 tools=DEST/TOOLS;tools.mkdir();save(tools/'p16a-request.json',request)
 with tarfile.open(DEST/'package.tar.gz','w:gz') as t:
  t.add(project,arcname=NAME);t.add(tools/'p16a-request.json',arcname=TOOLS+'/p16a-request.json')
 result=dict(unit=UNIT,project_name=NAME,request_sha256=sha(tools/'p16a-request.json'),archive_sha256=sha(DEST/'package.tar.gz'),
  reused_plain_runner_sha256='6ae141be72ccfdc77b2035d9b7347e5f555b37e94b4d7a7476ccfb3530d9883e',source_preparer_sha256=sha(__file__))
 save(DEST/'prepared.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
