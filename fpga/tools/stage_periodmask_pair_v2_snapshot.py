"""Stage exactly the reviewed V2 recurrence harness; never execute HDL."""
import hashlib
import json
from pathlib import Path
import shutil
import socket
import tarfile

ROOT = Path('/home/jtl/gfn-fpga-lab/agent-work/root-recurrence27-periodmask-pair')
MANIFEST_SHA = '6d1b10d06afb73681eae1c7aee3df658ca98093a2447f2edb074608a69eec013'
ARCHIVE_SHA = '1497f7277e56b4b98d536cf31dba99d09de63944588bc36e1ae8295f8ee89570'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    require(socket.gethostname() == 'aethia', 'aethia only')
    require(ROOT.resolve() == ROOT and ROOT.is_dir(), 'exact experiment root')
    manifest_path, archive_path = ROOT / 'manifest-v2.json', ROOT / 'source-v2.tar.gz'
    require(not manifest_path.is_symlink() and not archive_path.is_symlink(), 'regular inputs')
    require(digest(manifest_path) == MANIFEST_SHA, 'manifest hash')
    require(digest(archive_path) == ARCHIVE_SHA, 'archive hash')
    manifest = json.loads(manifest_path.read_text())
    destination = ROOT / 'snapshot-v2'
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
    shutil.copyfile(manifest_path, destination / 'manifest.json')
    require(digest(destination / 'manifest.json') == MANIFEST_SHA, 'copied manifest hash')
    print(json.dumps({'status': 'staged_not_executed', 'source_count': 20,
                      'manifest_sha256': MANIFEST_SHA, 'archive_sha256': ARCHIVE_SHA,
                      'destination': str(destination)}))


if __name__ == '__main__':
    main()
