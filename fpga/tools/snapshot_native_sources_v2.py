"""Capture an existing native test manifest's exact closed inputs; never dispatch.

The native manifest stays byte-identical. A local evolving source directory can
therefore be captured before each admitted test without renaming its RTL modules.
Existing destinations are never overwritten; failed captures remain inspectable.
V2 validates receipt metadata before creating any destination and starts failure
recording immediately after successful destination creation. V1 stays frozen.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def closed_inputs(root, pins):
    need(root.is_dir() and root.resolve() == root, 'canonical source directory')
    actual = set()
    for path in root.rglob('*'):
        need(not path.is_symlink(), 'no source symlinks')
        if path.is_file():
            actual.add(str(path.relative_to(root)))
    need(actual == set(pins), 'exact source closure')
    for name, digest in pins.items():
        rel = PurePosixPath(name)
        need(str(rel) == name and not rel.is_absolute() and '..' not in rel.parts,
             'safe source member')
        path = root / name
        need(path.is_file() and path.stat().st_nlink == 1 and sha(path) == digest,
             'source identity drift: ' + name)


def capture(manifest_path, source_root, destination):
    manifest_path, source_root, destination = map(Path, (manifest_path, source_root, destination))
    need(manifest_path.is_file() and not manifest_path.is_symlink(), 'regular manifest')
    manifest_bytes = manifest_path.read_bytes()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes)
    need(type(manifest) is dict and manifest.get('schema') == 'native-source-gate-v1' and
         manifest.get('status') == 'prepared_not_executed', 'prepared native manifest')
    native_source_root = manifest.get('source_root')
    need(type(native_source_root) is str and bool(native_source_root.strip()),
         'nonempty native source_root metadata')
    pins = manifest.get('sources')
    need(type(pins) is dict and bool(pins), 'nonempty source hash mapping')
    for name, digest in pins.items():
        need(type(name) is str and bool(name), 'source member name type')
        need(type(digest) is str and len(digest) == 64 and
             all(c in '0123456789abcdef' for c in digest), 'source SHA256 type')
    closed_inputs(source_root, pins)
    need(destination.is_absolute() and destination.parent.is_dir()
         and destination.parent.resolve() == destination.parent
         and not destination.is_relative_to(source_root), 'new external snapshot destination')
    # Construct every receipt field while the destination is still untouched.
    report = dict(schema='native-source-snapshot-v1', status='capturing',
                  manifest_sha256=manifest_sha, source_sha256=pins,
                  source_root=str(source_root), native_source_root=native_source_root,
                  scope='immutable test input capture only; no test, execution or qualification',
                  capture_tool_sha256=sha(Path(__file__)))
    destination.mkdir()  # Atomic refusal of an existing directory/file/symlink.
    try:
        snapshot = destination/'source'/'fpga'
        snapshot.mkdir(parents=True)
        for name in sorted(pins):
            output = snapshot/name
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_root/name, output)
            need(sha(output) == pins[name], 'copied source hash: ' + name)
        closed_inputs(snapshot, pins)
        # Recheck the live draft and manifest after the copy. Mid-copy edits
        # fail the attempt rather than combining evidence from two versions.
        closed_inputs(source_root, pins)
        need(manifest_path.read_bytes() == manifest_bytes, 'manifest changed during capture')
        with (destination/'approved-manifest.json').open('xb') as stream:
            stream.write(manifest_bytes)
        archive_path = destination/'source.tar.gz'
        with archive_path.open('xb') as raw:
            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode='w') as archive:
                    for name in sorted(pins):
                        path = snapshot/name
                        entry = tarfile.TarInfo('fpga/'+name)
                        entry.size = path.stat().st_size
                        entry.mode = 0o644
                        with path.open('rb') as data:
                            archive.addfile(entry, data)
        archived = {}
        with tarfile.open(archive_path, 'r:gz') as archive:
            for entry in archive:
                need(entry.isfile() and entry.name.startswith('fpga/'), 'regular archived source')
                name = entry.name.removeprefix('fpga/')
                need(name not in archived, 'unique archived source')
                archived[name] = hashlib.file_digest(archive.extractfile(entry), 'sha256').hexdigest()
        need(archived == pins, 'archive identity replay')
        report.update(status='captured_not_executed', files=len(pins),
                      archive_sha256=sha(archive_path), archive_bytes=archive_path.stat().st_size)
    except BaseException as error:
        report.update(status='failed_capture_preserved', error=repr(error))
        raise
    finally:
        with (destination/'capture.json').open('x') as stream:
            json.dump(report, stream, indent=2); stream.write('\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(capture(args.manifest, args.source_root, args.destination), indent=2))
