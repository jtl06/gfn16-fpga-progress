"""Own-UID read-only Linux tmpfs quota/headroom admission.

The only kernel quota operation is Q_GETQUOTA via quotactl_fd (syscall443 on
the verified installed x86_64 ABI). Never sets a quota or raises privileges.
Unknown quota state is a failed guard, even if statvfs reports global space.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import time


GIB = 1 << 30
Q_GETQUOTA = 0x800007
USRQUOTA = 0
GET_USER_QUOTA = (Q_GETQUOTA << 8) | USRQUOTA


class QuotaError(ValueError):
    pass


def need(ok, why):
    if not ok:
        raise QuotaError(why)


class Dqblk(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in ('bhardlimit', 'bsoftlimit', 'curspace',
        'ihardlimit', 'isoftlimit', 'curinodes', 'btime', 'itime')] + [('valid', ctypes.c_uint32)]


def effective_remaining(hard, soft, used, multiplier=1):
    need(all(type(value) is int and value >= 0 for value in (hard, soft, used, multiplier)) and multiplier > 0,
         'typed quota limits/usage')
    limits = [value * multiplier for value in (hard, soft) if value]
    # Conservatively obey soft limits immediately, regardless of grace expiry.
    limit = min(limits) if limits else None
    return dict(limit=limit, remaining=max(0, limit - used) if limit is not None else None, used=used)


def user_quota(path, *, uid=None):
    uid = os.getuid() if uid is None else uid
    need(type(uid) is int and uid == os.getuid(), 'own UID quota read only')
    need(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'verified Linux x86_64 quota ABI')
    path = Path(path)
    need(path.is_absolute() and path.is_dir() and path.resolve() == path, 'canonical existing quota path')
    syscall_header = Path('/usr/include/x86_64-linux-gnu/asm/unistd_64.h')
    quota_header = Path('/usr/include/linux/quota.h')
    syscall_source, quota_source = syscall_header.read_bytes(), quota_header.read_bytes()
    need(re.search(rb'^#define\s+__NR_quotactl_fd\s+443\s*$', syscall_source, re.M), 'installed quotactl_fd443 identity')
    for pattern in (rb'^#define\s+Q_GETQUOTA\s+0x800007\b', rb'^#define\s+USRQUOTA\s+0\b',
                    rb'^#define\s+SUBCMDSHIFT\s+8\b', rb'^#define\s+QIF_DQBLKSIZE_BITS\s+10\b'):
        need(re.search(pattern, quota_source, re.M), 'installed read-only quota constants/units')
    need(ctypes.sizeof(Dqblk) == 72 and Dqblk.valid.offset == 64, 'if_dqblk72-byte ABI')
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        actual = os.fstat(descriptor)
        usage = os.fstatvfs(descriptor)
        libc = ctypes.CDLL(None, use_errno=True)
        call = libc.syscall
        call.restype = ctypes.c_long
        payload = Dqblk()
        result = call(ctypes.c_long(443), ctypes.c_int(descriptor), ctypes.c_uint(GET_USER_QUOTA),
                      ctypes.c_int(uid), ctypes.byref(payload))
        if result != 0:
            error = ctypes.get_errno()
            raise QuotaError('own-UID Q_GETQUOTA unavailable: errno' + str(error) + ' ' + os.strerror(error))
        need(payload.valid & 15 == 15, 'complete block/inode quota limits and usage')
        fields = {name: int(getattr(payload, name)) for name, _ in payload._fields_}
        blocks = effective_remaining(payload.bhardlimit, payload.bsoftlimit, payload.curspace, 1024)
        inodes = effective_remaining(payload.ihardlimit, payload.isoftlimit, payload.curinodes)
        return dict(schema='native-own-user-quota-v1', status='known_read_only_kernel_quota',
            observed_at_unix=time.time(), path=str(path), uid=uid, device=actual.st_dev,
            kernel_call='quotactl_fd syscall443 QCMD(Q_GETQUOTA,USRQUOTA)', command=GET_USER_QUOTA,
            structure_bytes=72, limit_block_unit_bytes=1024, raw=fields,
            user_blocks=blocks, user_inodes=inodes,
            global_available_bytes=usage.f_bavail * usage.f_frsize, global_available_inodes=usage.f_favail,
            installed_headers_sha256={str(syscall_header): hashlib.sha256(syscall_source).hexdigest(),
                                      str(quota_header): hashlib.sha256(quota_source).hexdigest()},
            policy='min(nonzero soft,hard); zero limit is known unlimited; grace is never used to inflate admission')
    finally:
        os.close(descriptor)


def admit_receipt(receipt, outstanding_reservation_bytes, *, floor_bytes=2 * GIB,
                  outstanding_reservation_inodes=2048, floor_inodes=256):
    for value in (outstanding_reservation_bytes, floor_bytes, outstanding_reservation_inodes, floor_inodes):
        need(type(value) is int and value >= 0, 'typed nonnegative disk reservations/floors')
    need(receipt['schema'] == 'native-own-user-quota-v1' and receipt['status'] == 'known_read_only_kernel_quota'
         and 0 <= time.time() - receipt['observed_at_unix'] <= 30, 'fresh known kernel quota receipt')
    bytes_needed = outstanding_reservation_bytes + floor_bytes
    inodes_needed = outstanding_reservation_inodes + floor_inodes
    for name, remaining, needed in (
        ('global blocks', receipt['global_available_bytes'], bytes_needed),
        ('user blocks', receipt['user_blocks']['remaining'], bytes_needed),
        ('global inodes', receipt['global_available_inodes'], inodes_needed),
        ('user inodes', receipt['user_inodes']['remaining'], inodes_needed)):
        need(remaining is None or remaining >= needed, name + ' below outstanding reservations plus floor')
    return dict(schema='native-quota-headroom-v1', status='admitted_blocks_and_inodes', quota=receipt,
        outstanding_reservation_bytes=outstanding_reservation_bytes, floor_bytes=floor_bytes,
        outstanding_reservation_inodes=outstanding_reservation_inodes, floor_inodes=floor_inodes)


def validate_headroom(scratch_path, outstanding_reservation_bytes, *, floor_bytes=2 * GIB,
                      outstanding_reservation_inodes=2048, floor_inodes=256):
    return admit_receipt(user_quota(scratch_path), outstanding_reservation_bytes,
        floor_bytes=floor_bytes, outstanding_reservation_inodes=outstanding_reservation_inodes, floor_inodes=floor_inodes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    print(json.dumps(user_quota(args.path), indent=2))
