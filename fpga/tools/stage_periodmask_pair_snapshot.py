"""Stage one reviewed recurrence-pair source snapshot; never execute HDL."""
import hashlib
import json
from pathlib import Path
import socket
import tarfile

ROOT = Path('/home/jtl/gfn-fpga-lab/agent-work/root-recurrence27-periodmask-pair')
MANIFEST_SHA = 'b31968abb12df60dafc4250e69c8721862c1f2ab548b2c09fa13b9ab341bf25e'
ARCHIVE_SHA = 'fecb0fc0bc0d24af5bd59546f94e725f02e74d24c5e2a813ad4639b26e9d5177'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    require(socket.gethostname() == 'aethia', 'aethia only')
    require(ROOT.resolve() == ROOT and ROOT.is_dir(), 'exact experiment root')
    manifest_path, archive_path = ROOT / 'manifest.json', ROOT / 'source.tar.gz'
    require(not manifest_path.is_symlink() and not archive_path.is_symlink(), 'regular inputs')
    require(digest(manifest_path) == MANIFEST_SHA, 'manifest hash')
    require(digest(archive_path) == ARCHIVE_SHA, 'archive hash')
    manifest = json.loads(manifest_path.read_text())
    destination = ROOT / 'snapshot-v1'
    require(manifest['source_root'] == str(destination / 'fpga'), 'manifest destination')
    require(not destination.exists() and not destination.is_symlink(), 'fresh snapshot only')
    expected = {'fpga/' + name: sha for name, sha in manifest['sources'].items()}
    require(len(expected) == 20, 'exact source closure')
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        require(len(members) == 20 and {m.name for m in members} == set(expected), 'exact archive inventory')
        for member in members:
            require(member.isfile() and not Path(member.name).is_absolute()
                    and '..' not in Path(member.name).parts, 'safe regular source member')
            with archive.extractfile(member) as stream:
                require(hashlib.file_digest(stream, 'sha256').hexdigest() == expected[member.name], 'member hash')
        destination.mkdir()
        archive.extractall(destination, filter='data')
    for name, sha in expected.items():
        require(digest(destination / name) == sha, 'extracted source hash')
    # Native proposal expects the approved manifest beside the fpga directory.
    # This is an exact generated snapshot copy, not a rewrite of source evidence.
    import shutil
    shutil.copyfile(manifest_path, destination / 'manifest.json')
    require(digest(destination / 'manifest.json') == MANIFEST_SHA, 'copied manifest hash')
    print(json.dumps({'status': 'staged_not_executed', 'source_count': 20,
                      'manifest_sha256': MANIFEST_SHA, 'archive_sha256': ARCHIVE_SHA,
                      'destination': str(destination)}))


if __name__ == '__main__':
    main()
