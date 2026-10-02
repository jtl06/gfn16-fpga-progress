"""Additive quota admission: positively verified quota-disabled ext4 mounts.

Frozen v1 remains the own-user quota reader/space guard. An ESRCH alone is
never an admission pass. The ext4 path additionally requires read-only kernel
Q_GETFMT ESRCH, no quota flags in a stable mountinfo identity, the same opened
filesystem device, and normal global block/inode reservations and floors.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import time

from fpga.tools import native_user_quota_v1 as parent


PARENT_SHA256 = 'a55c3192c85b272dad59acc5d4b782b69f78e927e2f559106534b27ba6aab3c3'
Q_GETFMT = 0x800004


def mount_state(path, source=None):
    source = Path('/proc/self/mountinfo').read_text() if source is None else source
    path = str(Path(path))
    matches = []
    def unescape(value):
        return re.sub(r'\\([0-7]{3})', lambda match: chr(int(match.group(1), 8)), value)
    for line in source.splitlines():
        fields = line.split()
        separator = fields.index('-')
        root = unescape(fields[4])
        if path == root or path.startswith(root.rstrip('/') + '/'):
            matches.append(dict(mount_id=int(fields[0]), parent_id=int(fields[1]), device=fields[2],
                mountpoint=root, filesystem=fields[separator + 1], source=unescape(fields[separator + 2]),
                mount_options=sorted(fields[5].split(',')), super_options=sorted(fields[separator + 3].split(','))))
    parent.need(matches, 'exact containing mountinfo identity')
    return max(matches, key=lambda value: len(value['mountpoint']))


def disabled_receipt(path, *, observed_at, before, after, quota_errno, format_errno, device, available_bytes, available_inodes):
    parent.need(before == after and before['filesystem'] == 'ext4', 'stable exact ext4 mount identity')
    parent.need(quota_errno == 3 and format_errno == 3, 'Q_GETQUOTA and Q_GETFMT both prove no active quota')
    parent.need(not any('quota' in value.lower() for value in before['mount_options'] + before['super_options']),
                'mount has quota flags; ESRCH cannot establish disabled admission')
    parent.need(before['device'] == str(os.major(device)) + ':' + str(os.minor(device)), 'opened device/mountinfo mismatch')
    return dict(schema='native-own-user-quota-v1', status='known_read_only_kernel_quota',
        observed_at_unix=observed_at, path=str(path), uid=os.getuid(), device=device,
        quota_state='positively_verified_disabled_on_ext4', mount=before,
        kernel_call='read-only quotactl_fd Q_GETQUOTA then Q_GETFMT; exact mountinfo crosscheck',
        raw=dict(q_getquota_errno=quota_errno, q_getfmt_errno=format_errno),
        user_blocks=dict(limit=None, remaining=None, used=None), user_inodes=dict(limit=None, remaining=None, used=None),
        global_available_bytes=available_bytes, global_available_inodes=available_inodes,
        policy='known quota-disabled ext4; global block/inode reservations and floors still mandatory')


def user_quota(path):
    with Path(parent.__file__).open('rb') as stream:
        parent.need(hashlib.file_digest(stream, 'sha256').hexdigest() == PARENT_SHA256, 'frozen quota parent SHA')
    path = Path(path)
    try:
        return parent.user_quota(path)
    except parent.QuotaError as failure:
        # v1 performed exact ABI/header/own-UID validation before this failure.
        parent.need(str(failure).startswith('own-UID Q_GETQUOTA unavailable: errno3 '),
                    'quota state unknown; only exact kernel ESRCH is eligible for ext4 proof')
    before = mount_state(path)
    parent.need(before['filesystem'] == 'ext4', 'quota-disabled proof restricted to ext4')
    header = Path('/usr/include/linux/quota.h').read_bytes()
    parent.need(re.search(rb'^#define\s+Q_GETFMT\s+0x800004\b', header, re.M), 'installed read-only Q_GETFMT identity')
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        actual = os.fstat(descriptor)
        usage = os.fstatvfs(descriptor)
        value = ctypes.c_uint32()
        libc = ctypes.CDLL(None, use_errno=True)
        call = libc.syscall
        call.restype = ctypes.c_long
        result = call(ctypes.c_long(443), ctypes.c_int(descriptor), ctypes.c_uint(Q_GETFMT << 8),
                      ctypes.c_int(0), ctypes.byref(value))
        format_errno = ctypes.get_errno() if result == -1 else 0
        return disabled_receipt(path, observed_at=time.time(), before=before, after=mount_state(path),
            quota_errno=3, format_errno=format_errno, device=actual.st_dev,
            available_bytes=usage.f_bavail * usage.f_frsize, available_inodes=usage.f_favail)
    finally:
        os.close(descriptor)


def validate_headroom(scratch_path, outstanding_reservation_bytes, *, floor_bytes=2 * parent.GIB,
                      outstanding_reservation_inodes=2048, floor_inodes=256):
    return parent.admit_receipt(user_quota(scratch_path), outstanding_reservation_bytes,
        floor_bytes=floor_bytes, outstanding_reservation_inodes=outstanding_reservation_inodes, floor_inodes=floor_inodes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    print(json.dumps(user_quota(args.path), indent=2))
