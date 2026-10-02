"""Stage only the reviewed 68-file first-eight reset-probe bundle; never HDL.

Inputs: fixed experiment root/stage-v1/{manifest.json,source.tar.gz,vectors-aw16.txt}.
Output: fresh snapshot-v1/fpga plus approved manifest/vector beside fpga. No
existing file is replaced and incomplete staging is retained. --verify-payload
may check the same pinned local payload without writes or host requirements.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import socket
import tarfile

ROOT = Path('/home/jtl/gfn-fpga-lab/agent-work/rowcompact-reset-probe')
STAGE = ROOT / 'stage-v1'
DESTINATION = ROOT / 'snapshot-v1'
MANIFEST_SHA = '5837037dd1582e40631872bc50d399e6af3a68838b69e8213bd1e86d849a2f08'
ARCHIVE_SHA = 'a753916c4bf1ef0cbac0d58b8b35d70cd9f2acf5fbfd3f021a1a57af76112ed8'
VECTOR_SHA = '3449c1e3e1d7c0820842ecb30295b963b4aa81af6b27be8e38b7c87f2bd39f3d'
BATCH = [dict(kind=kind, variant=variant, age=age, bit=0)
         for kind in ('bf', 'mul') for variant in (0, 1) for age in (0, 6)]


def require(value, message):
    if not value:
        raise RuntimeError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def regular(path):
    require(path.resolve() == path and path.is_file() and not path.is_symlink(),
            'regular direct input required: ' + str(path))


def validate_members(archive, expected):
    members = archive.getmembers()
    require(len(members) == 68 and len(expected) == 68 and
            {member.name for member in members} == set(expected), 'exact archive inventory')
    for member in members:
        parts = member.name.split('/')
        require(member.isfile() and parts[0] == 'fpga' and
                all(part not in ('', '.', '..') for part in parts), 'safe regular source member')
        with archive.extractfile(member) as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == expected[member.name],
                    'source member SHA: ' + member.name)


def inspect_payload(stage):
    stage = Path(stage)
    require(stage.resolve() == stage and stage.is_dir(), 'direct payload directory')
    manifest_path = stage / 'manifest.json'
    archive_path = stage / 'source.tar.gz'
    vector_path = stage / 'vectors-aw16.txt'
    for path in (manifest_path, archive_path, vector_path):
        regular(path)
    require(digest(manifest_path) == MANIFEST_SHA, 'manifest SHA')
    require(digest(archive_path) == ARCHIVE_SHA, 'archive SHA')
    require(digest(vector_path) == VECTOR_SHA, 'vector SHA')
    manifest = json.loads(manifest_path.read_text())
    require(manifest['status'] == 'prepared_not_executed' and
            manifest['source_root'] == str(DESTINATION / 'fpga') and
            manifest['top'] == 'rowcompact_reset_probe' and
            manifest['profile'] == dict(aw=16, lanes=64, fields=3) and
            manifest['batch'] == BATCH and manifest['eventual_matrix_cases'] == 64 and
            manifest['archive_sha256'] == ARCHIVE_SHA and manifest['vector']['sha256'] == VECTOR_SHA,
            'fixed reviewed first-eight manifest contract')
    require(manifest['native_reset_qualified'] is False and
            manifest['full_matrix_qualified'] is False and
            manifest['mutant_sensitivity_qualified'] is False, 'unexecuted qualification flags')
    expected = {'fpga/' + name: pin for name, pin in manifest['sources'].items()}
    with tarfile.open(archive_path, 'r:gz') as archive:
        validate_members(archive, expected)
    return manifest, expected


def exclusive_copy(source, destination):
    with source.open('rb') as stream, destination.open('xb') as output:
        shutil.copyfileobj(stream, output)


def stage_snapshot():
    require(socket.gethostname() == 'aethia', 'aethia only')
    require(ROOT.resolve() == ROOT and ROOT.is_dir(), 'exact experiment root')
    manifest, expected = inspect_payload(STAGE)
    require(not DESTINATION.exists() and not DESTINATION.is_symlink(), 'fresh snapshot only')
    DESTINATION.mkdir(mode=0o700)
    with tarfile.open(STAGE / 'source.tar.gz', 'r:gz') as archive:
        validate_members(archive, expected)
        archive.extractall(DESTINATION, filter='data')
    for name, pin in expected.items():
        regular(DESTINATION / name)
        require(digest(DESTINATION / name) == pin, 'extracted source SHA')
    # Executor reads vectors beside --manifest, not from imported source code.
    for name, pin in (('manifest.json', MANIFEST_SHA), ('vectors-aw16.txt', VECTOR_SHA)):
        exclusive_copy(STAGE / name, DESTINATION / name)
        require(digest(DESTINATION / name) == pin, 'copied approved input SHA')
    inspect_payload(STAGE)  # Preserve immutable original inputs during staging.
    return dict(status='staged_not_executed', source_count=len(expected), cases=len(manifest['batch']),
                manifest_sha256=MANIFEST_SHA, archive_sha256=ARCHIVE_SHA, vector_sha256=VECTOR_SHA,
                destination=str(DESTINATION), approved_manifest=str(DESTINATION / 'manifest.json'),
                native_reset_qualified=False, full_matrix_qualified=False,
                mutant_sensitivity_qualified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-payload', type=Path)
    args = parser.parse_args()
    if args.verify_payload:
        manifest, expected = inspect_payload(args.verify_payload.resolve())
        result = dict(status='payload_verified_not_staged', source_count=len(expected),
                      cases=len(manifest['batch']), manifest_sha256=MANIFEST_SHA,
                      archive_sha256=ARCHIVE_SHA, vector_sha256=VECTOR_SHA)
    else:
        result = stage_snapshot()
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
