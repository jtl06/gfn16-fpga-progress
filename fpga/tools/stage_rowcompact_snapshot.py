"""Extract only the reviewed 58-file snapshot into its fresh aethia destination."""
import hashlib
import json
from pathlib import Path
import socket
import tarfile

ROOT = Path('/home/jtl/gfn-fpga-lab/agent-work/core27-prefetch-r2-rowcompact')
MANIFEST_SHA = '825f767cc82dc62ee68919f9aa0cf9d4d20b173e2225a42453d08a98e33c552e'
ARCHIVE_SHA = '444b2ffd74d535ad49dd8e3144b8adb4937a988331023b4869bf7c95564925af'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    require(socket.gethostname() == 'aethia', 'aethia only')
    require(ROOT.resolve() == ROOT and ROOT.is_dir(), 'exact experiment root')
    manifest_path = ROOT / 'manifest.json'
    archive_path = ROOT / 'source.tar.gz'
    require(not manifest_path.is_symlink() and not archive_path.is_symlink(), 'regular inputs')
    require(digest(manifest_path) == MANIFEST_SHA, 'manifest hash')
    require(digest(archive_path) == ARCHIVE_SHA, 'archive hash')
    manifest = json.loads(manifest_path.read_text())
    destination = ROOT / 'snapshot-v1'
    require(manifest['target'] == str(destination), 'manifest destination')
    require(not destination.exists() and not destination.is_symlink(), 'fresh snapshot only')
    expected = {'fpga/' + name: sha for name, sha in manifest['sources'].items()}
    require(len(expected) == 58, 'exact source closure')
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        require(len(members) == 58 and {m.name for m in members} == set(expected), 'exact archive inventory')
        for member in members:
            require(member.isfile() and not Path(member.name).is_absolute()
                    and '..' not in Path(member.name).parts, 'safe regular source member')
            with archive.extractfile(member) as stream:
                require(hashlib.file_digest(stream, 'sha256').hexdigest() == expected[member.name], 'member hash')
        destination.mkdir()
        archive.extractall(destination, filter='data')
    for name, sha in expected.items():
        require(digest(destination / name) == sha, 'extracted source hash')
    print(json.dumps({'status': 'staged_not_executed', 'source_count': 58,
                      'manifest_sha256': MANIFEST_SHA, 'archive_sha256': ARCHIVE_SHA,
                      'destination': str(destination)}))


if __name__ == '__main__':
    main()
