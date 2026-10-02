"""Validate/extract the immutable negative-control bundle on aethia only."""
import hashlib
import json
from pathlib import Path
import shutil
import socket
import tarfile

ROOT=Path('/home/jtl/gfn-fpga-lab/agent-work/crt27-mont')
MANIFEST_SHA='9fc362426b92a77842091eaed3a50c57aa8314b4fcb64f564d6368d0c6acf68c'

def digest(data):return hashlib.sha256(data).hexdigest()

def main():
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    stage=ROOT/'stage-mutations-v1';raw=(stage/'manifest.json').read_bytes()
    if digest(raw)!=MANIFEST_SHA:raise RuntimeError('externally reviewed manifest')
    manifest=json.loads(raw);destination=ROOT/'snapshot-v2'
    if destination.exists() or destination.is_symlink():raise RuntimeError('fresh destination only')
    if shutil.disk_usage(ROOT).free<(10<<30)+(64<<20):raise RuntimeError('disk floor')
    archive=stage/'source.tar.gz'
    if digest(archive.read_bytes())!=manifest['archive_sha256']:raise RuntimeError('archive pin')
    expected={'fpga/'+name:value for name,value in manifest['sources'].items()};payload={}
    if len(expected)!=11:raise RuntimeError('eleven source closure')
    with tarfile.open(archive,'r:gz') as tar:
        members=tar.getmembers()
        if len(members)!=len(expected) or {m.name for m in members}!=set(expected):raise RuntimeError('member closure')
        for member in members:
            path=Path(member.name)
            if not member.isfile() or member.size>1<<20 or path.is_absolute() or '..' in path.parts:raise RuntimeError('unsafe member')
            data=tar.extractfile(member).read()
            if digest(data)!=expected[member.name]:raise RuntimeError('source pin')
            payload[member.name]=data
    destination.mkdir()
    for name,data in payload.items():
        path=destination/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(data)
    print(json.dumps(dict(status='staged_not_executed',sources=len(payload),manifest_sha256=MANIFEST_SHA)))

if __name__=='__main__':main()
