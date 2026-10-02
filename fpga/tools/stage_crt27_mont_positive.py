"""Fresh-only aethia staging of the reviewed CRT positive snapshot; no HDL."""
import hashlib
import json
from pathlib import Path
import shutil
import socket
import tarfile

ROOT=Path('/home/jtl/gfn-fpga-lab/agent-work/crt27-mont')
STAGE=ROOT/'stage-positive-v1'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    manifest=json.loads((STAGE/'manifest.json').read_text())
    raw=(STAGE/'source.tar.gz').read_bytes()
    if sha(raw)!=manifest['archive_sha256']:raise RuntimeError('archive digest')
    destination=ROOT/'snapshot-v1'
    if destination.exists() or destination.is_symlink():raise RuntimeError('fresh snapshot required')
    if shutil.disk_usage(ROOT).free<(10<<30)+(192<<20):raise RuntimeError('disk floor and reservation')
    expected={'fpga/'+name:value for name,value in manifest['sources'].items()}
    payload={}
    with tarfile.open(STAGE/'source.tar.gz','r:gz') as archive:
        members=archive.getmembers()
        if len(members)!=len(expected) or {m.name for m in members}!=set(expected):raise RuntimeError('member closure')
        for member in members:
            if not member.isfile() or member.size>1<<20:raise RuntimeError('regular bounded source required')
            path=Path(member.name)
            if path.is_absolute() or '..' in path.parts:raise RuntimeError('unsafe member')
            data=archive.extractfile(member).read()
            if sha(data)!=expected[member.name]:raise RuntimeError('source identity')
            payload[member.name]=data
    destination.mkdir()
    for name,data in payload.items():
        path=destination/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(data)
    for name,expected_hash in expected.items():
        if sha((destination/name).read_bytes())!=expected_hash:raise RuntimeError('staged identity')
    print(json.dumps(dict(status='staged_not_executed',sources=len(payload),
                         manifest_sha256=sha((STAGE/'manifest.json').read_bytes()),source_root=manifest['source_root'])))


if __name__=='__main__':main()
