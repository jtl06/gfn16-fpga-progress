"""Extract the reviewed G4 source-only snapshot on aethia; never compile."""
import hashlib
import json
from pathlib import Path
import shutil
import socket
import tarfile

ROOT = Path('/home/jtl/gfn-fpga-lab/agent-work/core27-prefetch-r2-rootfused-crtmont')
MANIFEST_SHA = 'fc10698824eb675c490eefd06c517c1a00cdf58e952185532c0c3552dff8172d'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if socket.gethostname() != 'aethia':
        raise RuntimeError('aethia only')
    stage = ROOT / 'stage-v1'
    raw = (stage / 'manifest.json').read_bytes()
    if digest(raw) != MANIFEST_SHA:
        raise RuntimeError('reviewed manifest mismatch')
    manifest = json.loads(raw)
    destination = ROOT / 'snapshot-v1'
    if ROOT.resolve() != ROOT or destination.exists() or destination.is_symlink():
        raise RuntimeError('canonical fresh destination required')
    if shutil.disk_usage(ROOT).free < (10 << 30) + (64 << 20):
        raise RuntimeError('disk floor')
    for name, expected in [('parent-metrics.json', manifest['parent_metrics_sha256']),
                           ('g2-report.json', manifest['g2_sha256']),
                           ('source.tar.gz', manifest['archive_sha256'])]:
        if digest((stage / name).read_bytes()) != expected:
            raise RuntimeError('stage identity mismatch: ' + name)
    expected = {'fpga/' + name: value for name, value in manifest['sources'].items()}
    if len(expected) != 65:
        raise RuntimeError('65-source closure required')
    payload = {}
    with tarfile.open(stage / 'source.tar.gz', 'r:gz') as archive:
        members = archive.getmembers()
        if len(members) != len(expected) or {m.name for m in members} != set(expected):
            raise RuntimeError('member closure')
        for member in members:
            path = Path(member.name)
            if not member.isfile() or member.size > 1 << 20 or path.is_absolute() or '..' in path.parts:
                raise RuntimeError('unsafe member')
            data = archive.extractfile(member).read()
            if digest(data) != expected[member.name]:
                raise RuntimeError('source identity')
            payload[member.name] = data
    destination.mkdir()
    for name, data in payload.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
    print(json.dumps(dict(status='staged_not_executed', sources=len(payload), manifest_sha256=MANIFEST_SHA)))


if __name__ == '__main__':
    main()
