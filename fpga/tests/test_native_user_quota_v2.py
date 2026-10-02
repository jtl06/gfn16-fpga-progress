"""No-quota proof requires kernel state and exact mount identity together."""
import os
from pathlib import Path
import time
import unittest

from fpga.tools import native_user_quota_v2 as q


class DisabledQuota(unittest.TestCase):
    def setUp(self):
        self.device = os.makedev(2, 3)
        self.mount = dict(mount_id=30, parent_id=1, device='2:3', mountpoint='/', filesystem='ext4',
                          source='/dev/nvme0n1p3', mount_options=['relatime', 'rw'], super_options=['rw', 'stripe=8191'])

    def receipt(self, **changes):
        options = dict(path=Path('/lab/scratch'), observed_at=time.time(), before=self.mount, after=self.mount,
                       quota_errno=3, format_errno=3, device=self.device, available_bytes=50 * q.parent.GIB, available_inodes=10000)
        options.update(changes)
        return q.disabled_receipt(**options)

    def test_disabled_ext4_is_positive_proof_but_still_checks_global_floors(self):
        raw = self.receipt()
        self.assertEqual(raw['quota_state'], 'positively_verified_disabled_on_ext4')
        q.parent.admit_receipt(raw, q.parent.GIB, floor_bytes=10 * q.parent.GIB)
        raw['global_available_bytes'] = 10 * q.parent.GIB
        with self.assertRaises(q.parent.QuotaError):
            q.parent.admit_receipt(raw, q.parent.GIB, floor_bytes=10 * q.parent.GIB)

    def test_esrch_alone_eperm_enosys_active_format_are_not_positive_proof(self):
        for quota, fmt in ((3, 1), (3, 38), (1, 3), (38, 3), (3, 0)):
            with self.subTest(quota=quota, format=fmt), self.assertRaises(q.parent.QuotaError):
                self.receipt(quota_errno=quota, format_errno=fmt)

    def test_quota_mount_flags_changed_mount_wrong_fs_and_wrong_device_fail(self):
        for changed in (dict(self.mount, filesystem='tmpfs'), dict(self.mount, super_options=['rw', 'usrquota']),
                        dict(self.mount, mount_id=31), dict(self.mount, device='259:4')):
            with self.subTest(changed=changed), self.assertRaises(q.parent.QuotaError):
                self.receipt(after=changed)
        flagged = dict(self.mount, super_options=['rw', 'usrquota'])
        with self.assertRaises(q.parent.QuotaError):
            self.receipt(before=flagged, after=flagged)
        with self.assertRaises(q.parent.QuotaError):
            self.receipt(device=os.makedev(2, 4))

    def test_longest_mountpoint_and_mountinfo_escaped_spaces(self):
        source = '30 1 259:3 / / rw,relatime - ext4 /dev/nvme0n1p3 rw\n31 30 0:26 / /lab\\040scratch rw - tmpfs tmpfs rw,usrquota\n'
        self.assertEqual(q.mount_state('/lab scratch/work', source)['mount_id'], 31)
        self.assertEqual(q.mount_state('/lab/work', source)['mount_id'], 30)


if __name__ == '__main__':
    unittest.main()
