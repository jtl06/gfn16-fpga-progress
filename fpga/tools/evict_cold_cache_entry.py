#!/usr/bin/env python3
"""Evict ONLY the pinned fe1ea190 cache entry after two verified cold copies.

Default: verify backups/source/processes while holding both existing locks.
Apply: add --apply --confirm-key <full KEY>. Run via `ssh ... 'python3 - ...'`
with this file on stdin. There is no configurable source or recursive deletion.
The unchanged archive helper and saved receipts must exist in the pinned SHM
folder. Visibility exceptions are only exact known infrastructure processes.
"""
import argparse
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import stat
import sys
import types

sys.dont_write_bytecode = True
KEY = 'fe1ea1907ad7af18a7905aed803cb19937f42f40568fed2c8f4a4713e9b17fc6'
ROOT = Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/executable-cache-v2')
ENTRY = ROOT / 'objects' / KEY
COMPILE_LOCK = ROOT.parent / 'compile.lock'
SHM = Path('/dev/shm/cold-cache-fe1ea1907ad7-y3gc6gwb')
ARCHIVE = SHM / (KEY + '.tar.gz')
ARCHIVE_SHA = 'a319462806c7d0fc070a889dfb9d6b4936dcbdefd889729df1bd0a733f314aa0'
PROOF_SHA = '36ecc1b726d979b6c364e43767c944c8ab1926c4de034ce72e20251e99970f95'
HELPER_SHA = '274eebdec46e0c4510339bd8c5f5c905a8552ff72b0e2fd48444188b72764224'
RECEIPTS = {
    'local': ('local-verification.json', 'local-mac',
              '325b0e8976f6dff31913368081348ccd57adf7ca6ad3477e9627b0347c109c60'),
    'gcp': ('gcp-verification.json', 'gfn16-pilot-c4',
            'ce8e3913c7e62f27a69b90ebf834e0b65b604d4341a2c2de863f80e2ed6ec00e'),
}
# Canonical SHA of the exact observed tailscaled argv prefix through
# --force-v1-behavior. Personal account/IP strings are not embedded in source.
TAILSCALED_PREFIX_SHA = '0634666c51506105945e8837beb44e44fa778bbe8f983ed99b2a34d442d232c3'
TOOLS = {'make', 'gmake', 'gcc', 'g++', 'cc', 'c++', 'cc1', 'cc1plus',
         'clang', 'clang++', 'verilator', 'verilator_bin', 'yosys', 'sby',
         'iverilog', 'vvp', 'pytest', 'pytest-3', 'ld', 'ld.bfd', 'ld.gold', 'as'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode()


def pinned_bytes(path, expected_sha):
    require(path.resolve() == path and path.is_file(), 'unsafe input: ' + str(path))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        s = os.fstat(stream.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_size < 10_000_000, 'nonregular/oversized input')
        raw = stream.read()
    require(hashlib.sha256(raw).hexdigest() == expected_sha, 'input SHA changed: ' + str(path))
    return raw


def load_helper():
    path = SHM / 'cold_archive_build_cache_entry.py'
    raw = pinned_bytes(path, HELPER_SHA)
    module = types.ModuleType('cold_archive_build_cache_entry')
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    require(module.KEY == KEY and module.ENTRY == ENTRY, 'helper source target mismatch')
    return module


def verify_backups(cold):
    proof = json.loads(pinned_bytes(SHM / 'source-proof.json', PROOF_SHA))
    archive = cold.verify_archive(ARCHIVE)
    require(archive['archive_sha256'] == ARCHIVE_SHA, 'original archive SHA changed')
    require(proof['source'] == str(ENTRY) and proof['key'] == KEY and
            proof['source_unchanged_after_archive'] is True and
            proof['full_source_inventory_verified'] is True, 'source proof mismatch')
    receipts = {}
    comparison = ('key', 'archive_sha256', 'archive_bytes', 'archive_members',
                  'manifest_sha256', 'inventory_sha256', 'executable_sha256',
                  'output_files', 'output_bytes', 'full_archive_inventory_verified')
    for role, (name, host, sha) in RECEIPTS.items():
        receipt = json.loads(pinned_bytes(SHM / name, sha))
        require(receipt.get('copy_role') == role and receipt.get('host') == host and
                receipt.get('proof_sha256') == PROOF_SHA and
                receipt.get('verified_at_utc') == '2026-09-30T16:36:41Z',
                'backup receipt identity mismatch')
        require(all(receipt.get(k) == archive.get(k) for k in comparison),
                'backup receipt inventory mismatch')
        require(Path(receipt['archive']).is_absolute() and receipt['archive'] != str(ARCHIVE),
                'backup must be a separate absolute copy')
        receipts[role] = receipt
    require(receipts['local']['archive'] != receipts['gcp']['archive'], 'backup locations coincide')
    return proof, receipts


def proc_identity(proc):
    raw = (proc / 'stat').read_text()
    fields = raw[raw.rfind(')') + 2:].split()
    return int(fields[1]), int(fields[19])  # PPid and process start tick.


def process_ancestors():
    result = set(); pid = os.getpid()
    while pid > 1:
        require(pid not in result, 'cyclic process ancestry')
        result.add(pid)
        pid, _ = proc_identity(Path('/proc') / str(pid))
    return result


def is_job(comm, argv):
    names = [comm, *(Path(arg).name for arg in argv if arg)]
    if any(name in TOOLS or name.startswith(('Vgenefer_', 'Vntt_', 'Vsquare_', 'Vmontgomery_'))
           for name in names):
        return True
    return any(('gfn-fpga-lab' in arg and ('/fpga/reference/' in arg or
                '/fpga/tools/run_' in arg)) or
               (arg.endswith('.py') and any(word in Path(arg).name for word in
                 ('regression', 'replay', 'fault', 'pytest', 'qualified', 'recovery')))
               for arg in argv)


def infrastructure(comm, argv, pid, ancestors, own_argv):
    if comm == 'systemd' and argv == ['/usr/lib/systemd/systemd', '--user']:
        return 'exact-systemd-user'
    if comm == '(sd-pam)' and argv == ['(sd-pam)']:
        return 'exact-sd-pam'
    if comm != 'tailscaled' or pid not in ancestors or len(argv) != 15:
        return None
    if hashlib.sha256(canonical(argv[:-1])).hexdigest() != TAILSCALED_PREFIX_SHA:
        return None
    if not argv[-1].startswith('--cmd='):
        return None
    command = argv[-1][len('--cmd='):]
    # Exact argv equality rejects separators, redirection, extra commands and
    # unrelated Python invocations. The daemon must be our own SSH ancestor.
    if shlex.split(command) != own_argv:
        return None
    return 'exact-current-ssh-ancestor'


def quiet_processes():
    ancestors = process_ancestors()
    own_argv = [a.decode() for a in Path('/proc/self/cmdline').read_bytes().split(b'\0') if a]
    require(own_argv[0] in ('python3', '/usr/bin/python3') and own_argv[1] == '-',
            'helper must run as the exact stdin Python invocation')
    approved = []; inspected = 0
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            identity = proc_identity(proc)
            argv = [a.decode() for a in (proc / 'cmdline').read_bytes().split(b'\0') if a]
            comm = (proc / 'comm').read_text().strip()
            if not argv:
                continue
            require(not is_job(comm, argv), 'active HDL/compiler/test job PID ' + proc.name)
            require(not any(str(ENTRY) in a for a in argv), 'cache consumer argv PID ' + proc.name)
            if proc.stat().st_uid != os.getuid():
                continue  # All UIDs' readable argv/comm checked for jobs.
            inspected += 1; gaps = set()
            for label in ('cwd', 'exe'):
                try:
                    require(not os.readlink(proc / label).startswith(str(ENTRY)),
                            'cache consumer ' + label + ' PID ' + proc.name)
                except PermissionError:
                    gaps.add(label)
            try:
                require(str(ENTRY) not in (proc / 'maps').read_text(), 'cache mapping PID ' + proc.name)
            except PermissionError:
                gaps.add('maps')
            try:
                for fd in (proc / 'fd').iterdir():
                    try:
                        require(not os.readlink(fd).startswith(str(ENTRY)), 'cache fd PID ' + proc.name)
                    except FileNotFoundError:
                        pass
                    except PermissionError:
                        gaps.add('fd_links')
            except PermissionError:
                gaps.add('fd')
            require(proc_identity(proc) == identity, 'process identity changed PID ' + proc.name)
            if gaps:
                category = infrastructure(comm, argv, int(proc.name), ancestors, own_argv)
                require(category is not None, 'unresolved /proc visibility PID ' + proc.name)
                if category == 'exact-current-ssh-ancestor':
                    command = argv[-1][len('--cmd='):]
                    for ancestor in ancestors - {os.getpid(), int(proc.name)}:
                        a = Path('/proc') / str(ancestor)
                        shell_argv = [v.decode() for v in (a / 'cmdline').read_bytes().split(b'\0') if v]
                        if (a / 'comm').read_text().strip() == 'zsh':
                            require(len(shell_argv) == 3 and shell_argv[0] in ('zsh', '/usr/bin/zsh')
                                    and shell_argv[1] == '-c' and shell_argv[2] == command,
                                    'SSH shell invocation mismatch')
                approved.append(dict(pid=int(proc.name), category=category, inaccessible_fields=sorted(gaps)))
        except (FileNotFoundError, ProcessLookupError):
            pass
    return dict(active_jobs=0, detected_consumers=0, inspected_same_user=inspected,
                narrowed_infrastructure_exceptions=approved)


def existing_lock(stack, path):
    require(path.resolve() == path, 'unsafe lock path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    stack.callback(os.close, fd)
    s = os.fstat(fd)
    require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'unsafe existing lock')
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fd


def metadata(s):
    return dict(size=s.st_size, mode=stat.S_IMODE(s.st_mode), device=s.st_dev,
                inode=s.st_ino, mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns)


def unlink_verified(cold, fd, name, record):
    file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
    with os.fdopen(file_fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                metadata(before) == {k: v for k, v in record.items() if k != 'sha256'},
                'file identity changed before unlink: ' + name)
        require(cold.stream_hash(stream) == record['sha256'], 'file hash changed before unlink: ' + name)
        require(metadata(os.fstat(stream.fileno())) == metadata(before), 'file changed while rehashing')
        require(metadata(os.stat(name, dir_fd=fd, follow_symlinks=False)) == metadata(before),
                'file replaced before unlink')
        os.unlink(name, dir_fd=fd)


def remove_exact(cold, snapshots, process_check, receipts):
    # This pinned entry is flat; no recursive deletion or generated paths.
    require(set(snapshots) == {'manifest.json'} | {'build/' + n for n in
            json.loads((ENTRY / 'manifest.json').read_bytes())['outputs']['files']},
            'unlink inventory mismatch')
    removed = 0
    with ExitStack() as stack:
        objects_fd = os.open(ROOT / 'objects', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, objects_fd)
        entry_fd = os.open(KEY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=objects_fd)
        stack.callback(os.close, entry_fd)
        build_fd = os.open('build', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=entry_fd)
        stack.callback(os.close, build_fd)
        require(sorted(os.listdir(entry_fd)) == ['build', 'manifest.json'], 'entry membership changed')
        names = sorted(name[len('build/'):] for name in snapshots if name.startswith('build/'))
        require(all('/' not in name for name in names) and sorted(os.listdir(build_fd)) == names,
                'flat build membership changed')
        audit_path = SHM / 'eviction-receipt.jsonl'
        with audit_path.open('x') as audit:
            def record(status, **extra):
                audit.write(json.dumps(dict(status=status, source=str(ENTRY), key=KEY,
                    archive_sha256=ARCHIVE_SHA, proof_sha256=PROOF_SHA,
                    recoverability_receipts=receipts, process_check=process_check,
                    files_removed=removed, **extra), sort_keys=True) + '\n')
                audit.flush(); os.fsync(audit.fileno())
            record('begin_exact_eviction')
            try:
                os.fchmod(entry_fd, 0o700); os.fchmod(build_fd, 0o755)
                for name in names:
                    unlink_verified(cold, build_fd, name, snapshots['build/' + name]); removed += 1
                require(not os.listdir(build_fd), 'build directory not empty')
                os.rmdir('build', dir_fd=entry_fd)
                unlink_verified(cold, entry_fd, 'manifest.json', snapshots['manifest.json']); removed += 1
                require(not os.listdir(entry_fd), 'entry directory not empty')
                os.rmdir(KEY, dir_fd=objects_fd)
                record('exact_eviction_complete')
            except Exception as error:
                # Freeze surviving opened directories without following paths.
                os.fchmod(build_fd, 0o555); os.fchmod(entry_fd, 0o500)
                record('partial_eviction_requires_restore', error=str(error))
                raise
    return dict(status='exact_eviction_complete', key=KEY, source=str(ENTRY),
                files_removed=removed, output_bytes_removed=cold.OUTPUT_BYTES,
                archive_sha256=ARCHIVE_SHA, audit_receipt=str(audit_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-key')
    args = parser.parse_args()
    require(not args.apply or args.confirm_key == KEY, 'apply requires exact --confirm-key')
    require(platform.node().startswith('aethia') and os.getuid() == 1000,
            'source actions require aethia UID 1000')
    cold = load_helper()
    with ExitStack() as stack:
        existing_lock(stack, COMPILE_LOCK)
        existing_lock(stack, ROOT / 'locks' / (KEY + '.lock'))
        proof, receipts = verify_backups(cold)
        _, snapshots, directories = cold.source_snapshot()
        require(snapshots == proof['source_files'] and directories == proof['directory_modes'],
                'source identity/content differs from archived proof')
        require(directories == {'': 0o500, 'build': 0o555}, 'unexpected directory topology')
        process_check = quiet_processes()
        if args.apply:
            print(json.dumps(remove_exact(cold, snapshots, process_check, receipts), sort_keys=True))
        else:
            print(json.dumps(dict(status='ready_exact_entry_only', key=KEY,
                locks_held=['global_compile', 'cache_key'], process_check=process_check,
                output_files=cold.OUTPUT_COUNT, output_bytes=cold.OUTPUT_BYTES,
                backups_verified=['local-mac', 'gfn16-pilot-c4']), sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        sys.exit(1)
