#!/usr/bin/env python3
"""Check or archive one pinned completed aethia cache entry; never evict it.

Run remotely via stdin: ssh aethia-ts 'python3 - --archive' < this_file.
Default action is read-only checking. --archive writes a fresh /dev/shm folder
only. Copy and independently verify the archive before any separate eviction.
--verify-archive PATH verifies a copied tar.gz without accessing the cache.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile


ROOT = Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/executable-cache-v2')
KEY = 'fe1ea1907ad7af18a7905aed803cb19937f42f40568fed2c8f4a4713e9b17fc6'
ENTRY = ROOT / 'objects' / KEY
MANIFEST_SHA = 'db00dcdb954be5bd00bcbfe4f2676a8590f0cf74b9db3664bd0a277ed7d039cf'
EXECUTABLE_SHA = 'a168a6b80fa22ec08498fc121bc07968beb4eb43d2604124edf6337ab5273084'
INVENTORY_SHA = 'e1e6436e6bbd47f4b92c06e4814cae8bdf398cd7e677135ca9d7186776fded3d'
OUTPUT_COUNT = 344
OUTPUT_BYTES = 354368548


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode()


def stream_hash(stream):
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(1 << 20), b''):
        h.update(block)
    return h.hexdigest()


def digest(path):
    with path.open('rb') as stream:
        return stream_hash(stream)


def safe_relative(name):
    parts = name.split('/')
    require(name and not name.startswith('/') and all(p not in ('', '.', '..') for p in parts),
            'unsafe inventory member')
    return name


def check_manifest(raw):
    require(hashlib.sha256(raw).hexdigest() == MANIFEST_SHA, 'manifest pin changed')
    m = json.loads(raw)
    require(m['schema'] == 1 and m['key'] == KEY, 'schema/key mismatch')
    require(hashlib.sha256(canonical(m['inputs'])).hexdigest() == KEY, 'input key mismatch')
    require(m['executable'] == 'Vgenefer_square_core' and
            m['executable_sha256'] == EXECUTABLE_SHA, 'executable pin mismatch')
    require(hashlib.sha256(canonical(m['outputs'])).hexdigest() == INVENTORY_SHA,
            'inventory pin mismatch')
    require(len(m['outputs']['files']) == OUTPUT_COUNT and
            sum(r['size'] for r in m['outputs']['files'].values()) == OUTPUT_BYTES,
            'inventory count/size mismatch')
    for name in [*m['outputs']['files'], *m['outputs']['directories']]:
        safe_relative(name)
    executable = m['outputs']['files'][m['executable']]
    require(executable['sha256'] == EXECUTABLE_SHA and executable['mode'] & 0o111,
            'executable inventory mismatch')
    return m


def check_ancestors():
    for path in reversed([ENTRY, *ENTRY.parents][:-1]):
        require(not path.is_symlink() and path.is_dir(), 'symlink/missing ancestor: ' + str(path))
    require(ENTRY.resolve() == ENTRY, 'entry resolves outside exact target')


def file_snapshot(path):
    s = path.lstat()
    require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'nonregular/hardlinked file: ' + str(path))
    mode = stat.S_IMODE(s.st_mode)
    require(not mode & (0o222 | 0o7000), 'writable/special file: ' + str(path))
    h = digest(path)
    t = path.lstat()
    require((s.st_dev, s.st_ino, s.st_size, s.st_mode, s.st_mtime_ns, s.st_ctime_ns) ==
            (t.st_dev, t.st_ino, t.st_size, t.st_mode, t.st_mtime_ns, t.st_ctime_ns),
            'file changed while hashing: ' + str(path))
    return dict(sha256=h, size=s.st_size, mode=mode, device=s.st_dev,
                inode=s.st_ino, mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns)


def source_snapshot():
    check_ancestors()
    require(sorted(p.name for p in ENTRY.iterdir()) == ['build', 'manifest.json'],
            'unexpected top-level entry member')
    require(stat.S_IMODE(ENTRY.stat().st_mode) == 0o500, 'entry mode changed')
    require(stat.S_IMODE((ENTRY / 'build').lstat().st_mode) == 0o555,
            'build mode changed')
    m = check_manifest((ENTRY / 'manifest.json').read_bytes())
    files = {}; directories = []; dir_modes = {'': 0o500, 'build': 0o555}
    snapshots = {'manifest.json': file_snapshot(ENTRY / 'manifest.json')}
    require(snapshots['manifest.json']['mode'] == 0o444, 'manifest mode changed')
    for path in sorted((ENTRY / 'build').rglob('*')):
        s = path.lstat(); relative = path.relative_to(ENTRY / 'build').as_posix()
        safe_relative(relative)
        if stat.S_ISDIR(s.st_mode):
            mode = stat.S_IMODE(s.st_mode)
            require(not mode & (0o222 | 0o7000), 'writable/special directory')
            directories.append(relative); dir_modes['build/' + relative] = mode
        else:
            r = file_snapshot(path)
            snapshots['build/' + relative] = r
            files[relative] = {k: r[k] for k in ('sha256', 'size', 'mode')}
    require(dict(files=files, directories=directories) == m['outputs'],
            'full frozen inventory/hash mismatch')
    for control in ('staging', 'quarantine'):
        path = ROOT / control
        require(not path.is_symlink() and path.is_dir(), 'unsafe control directory')
        require(not any(p.name.startswith(KEY) for p in path.iterdir()),
                'matching ' + control + ' entry exists')
    return m, snapshots, dir_modes


def check_processes():
    """Report visibility gaps; archive creation is safe for immutable readers.

    This is evidence for packing, NOT sufficient authorization for eviction.
    Privileged user daemons can have inaccessible /proc fields even at our UID.
    """
    matches = []; gaps = []; needle = str(ENTRY); uid = os.getuid()
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            if proc.stat().st_uid != uid:
                continue
            reasons = []; unreadable = set()
            try:
                cmdline = (proc / 'cmdline').read_bytes()
                if needle.encode() in cmdline or KEY.encode() in cmdline:
                    reasons.append('cmdline')
            except PermissionError:
                unreadable.add('cmdline'); cmdline = None
            # Empty cmdline denotes a kernel task/zombie with no cache use.
            if cmdline != b'':
                for label in ('cwd', 'exe'):
                    try:
                        if os.readlink(proc / label).startswith(needle):
                            reasons.append(label)
                    except PermissionError:
                        unreadable.add(label)
                try:
                    if needle in (proc / 'maps').read_text():
                        reasons.append('maps')
                except PermissionError:
                    unreadable.add('maps')
                try:
                    for fd in (proc / 'fd').iterdir():
                        try:
                            if os.readlink(fd).startswith(needle):
                                reasons.append('fd'); break
                        except FileNotFoundError:
                            pass
                        except PermissionError:
                            unreadable.add('fd_links')
                except PermissionError:
                    unreadable.add('fd')
            if reasons:
                matches.append(dict(pid=int(proc.name), reasons=reasons))
            if unreadable:
                gaps.append(dict(pid=int(proc.name), comm=(proc / 'comm').read_text().strip(),
                                 fields=sorted(unreadable)))
        except (FileNotFoundError, ProcessLookupError):
            pass  # Process exited during scan.
        except PermissionError:
            gaps.append(dict(pid=int(proc.name), fields=['process_metadata']))
    require(not matches, 'active cache references: ' + json.dumps(matches))
    return dict(scope='same-user accessible /proc fields', uid=uid,
                detected_entry_references=len(matches), visibility_complete=not gaps,
                visibility_gaps=gaps, sufficient_for_eviction=False)


def verify_archive(path):
    require(not path.is_symlink() and path.is_file(), 'unsafe archive path')
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers()
        names = [item.name for item in members]
        require(len(names) == len(set(names)), 'duplicate archive members')
        by_name = dict(zip(names, members))
        manifest = by_name.get(KEY + '/manifest.json')
        require(manifest is not None and manifest.isfile() and manifest.size < 10_000_000,
                'archive manifest missing/invalid')
        with archive.extractfile(manifest) as stream:
            raw = stream.read()
        m = check_manifest(raw)
        expected_files = {KEY + '/manifest.json':
                          dict(sha256=MANIFEST_SHA, size=len(raw), mode=0o444)}
        expected_files.update({KEY + '/build/' + name: record
                               for name, record in m['outputs']['files'].items()})
        expected_dirs = {KEY: 0o500, KEY + '/build': 0o555}
        # This pinned entry has no nested directories; refuse a changed topology.
        require(m['outputs']['directories'] == [], 'unexpected directory topology')
        require(set(names) == set(expected_files) | set(expected_dirs),
                'archive inventory membership mismatch')
        for item in members:
            safe_relative(item.name)
            if item.name in expected_dirs:
                require(item.isdir() and item.mode == expected_dirs[item.name],
                        'archive directory mismatch')
            else:
                record = expected_files[item.name]
                require(item.isfile() and item.mode == record['mode'] and
                        item.size == record['size'], 'archive file metadata mismatch')
                with archive.extractfile(item) as stream:
                    require(stream_hash(stream) == record['sha256'], 'archive file hash mismatch')
    return dict(archive=str(path), archive_sha256=digest(path), archive_bytes=path.stat().st_size,
                archive_members=len(names), manifest_sha256=MANIFEST_SHA,
                inventory_sha256=INVENTORY_SHA, executable_sha256=EXECUTABLE_SHA,
                key=KEY, output_files=OUTPUT_COUNT, output_bytes=OUTPUT_BYTES,
                full_archive_inventory_verified=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--archive', action='store_true')
    actions.add_argument('--verify-archive', type=Path)
    args = parser.parse_args()
    if args.verify_archive:
        print(json.dumps(verify_archive(args.verify_archive), sort_keys=True)); return
    check_ancestors()
    lock_path = ROOT / 'locks' / (KEY + '.lock')
    require(not lock_path.parent.is_symlink(), 'unsafe lock directory')
    fd = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'nonregular lock')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        process_check = check_processes()
        manifest, snapshots, dir_modes = source_snapshot()
        proof = dict(source=str(ENTRY), key=KEY, manifest_sha256=MANIFEST_SHA,
                     executable_sha256=EXECUTABLE_SHA, inventory_sha256=INVENTORY_SHA,
                     output_files=OUTPUT_COUNT, output_bytes=OUTPUT_BYTES,
                     full_source_inventory_verified=True, key_lock_held=True,
                     process_reference_check_before=process_check,
                     source_files=snapshots, directory_modes=dir_modes)
        if args.archive:
            shm = Path('/dev/shm')
            require(shm.resolve() == shm and shm.is_dir() and os.path.ismount(shm),
                    '/dev/shm is not a direct mounted directory')
            # Linux tmpfs magic: never use a disk-backed fallback.
            import subprocess
            require(subprocess.check_output(['stat', '-f', '-c', '%T', str(shm)], text=True).strip()
                    == 'tmpfs', '/dev/shm is not tmpfs')
            v = os.statvfs(shm)
            require(v.f_bavail * v.f_frsize > OUTPUT_BYTES + 128 * 1024 * 1024,
                    'insufficient /dev/shm free space')
            temp = Path(tempfile.mkdtemp(prefix='cold-cache-' + KEY[:12] + '-', dir=shm))
            path = temp / (KEY + '.tar.gz')
            with tarfile.open(path, 'x:gz', compresslevel=6) as archive:
                archive.add(ENTRY, arcname=KEY, recursive=False)
                for member in sorted(ENTRY.rglob('*')):
                    archive.add(member, arcname=KEY + '/' + member.relative_to(ENTRY).as_posix(),
                                recursive=False)
            proof.update(verify_archive(path))
            _, after, after_dirs = source_snapshot()
            require(after == snapshots and after_dirs == dir_modes, 'source changed during archive')
            proof['process_reference_check_after'] = check_processes()
            proof['source_unchanged_after_archive'] = True
            proof_path = temp / 'source-proof.json'
            with proof_path.open('x') as stream:
                json.dump(proof, stream, sort_keys=True); stream.write('\n')
            proof['proof_file'] = str(proof_path)
            proof['proof_sha256'] = digest(proof_path)
        # Summary stays bounded; the archived sidecar has the full source proof.
        summary = {k: v for k, v in proof.items() if k not in ('source_files', 'directory_modes')}
        print(json.dumps(summary, sort_keys=True))
    finally:
        os.close(fd)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        sys.exit(1)
