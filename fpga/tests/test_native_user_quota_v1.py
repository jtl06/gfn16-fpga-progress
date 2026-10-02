"""Quota/headroom negative controls; no kernel call on Mac."""
import ctypes
import inspect
import time
import unittest
from unittest.mock import patch

from fpga.tools import native_user_quota_v1 as q


def receipt(**changes):
    value = dict(schema='native-own-user-quota-v1', status='known_read_only_kernel_quota',
        observed_at_unix=time.time(), global_available_bytes=10 * q.GIB, global_available_inodes=10000,
        user_blocks=dict(limit=12 * q.GIB, remaining=5 * q.GIB, used=7 * q.GIB),
        user_inodes=dict(limit=10000, remaining=5000, used=5000))
    value.update(changes)
    return value


class UserQuota(unittest.TestCase):
    def test_exact_read_only_abi_and_units(self):
        self.assertEqual(q.GET_USER_QUOTA, 0x80000700)
        self.assertEqual(ctypes.sizeof(q.Dqblk), 72)
        self.assertEqual(q.Dqblk.valid.offset, 64)
        source = inspect.getsource(q)
        self.assertNotIn('Q_SET', source)
        self.assertNotIn('sudo', source)

    def test_limits_use1024byte_blocks_and_soft_limit_without_grace(self):
        self.assertEqual(q.effective_remaining(12, 10, 512, 1024), dict(limit=10240, remaining=9728, used=512))
        self.assertEqual(q.effective_remaining(10, 0, 20480, 1024)['remaining'], 0)
        self.assertEqual(q.effective_remaining(0, 0, 100), dict(limit=None, remaining=None, used=100))

    def test_real_edquot_snapshot_blocks_despite_global_free(self):
        raw = receipt(global_available_bytes=2950905856,
                      user_blocks=dict(limit=11460404224, used=11374600192, remaining=85804032),
                      user_inodes=dict(limit=None, used=13269, remaining=None))
        with self.assertRaisesRegex(q.QuotaError, 'user blocks'):
            q.admit_receipt(raw, 512 * 1024**2)

    def test_all_live_jobs_outstanding_reservations_are_counted(self):
        q.admit_receipt(receipt(), 2 * q.GIB, outstanding_reservation_inodes=4000)
        with self.assertRaisesRegex(q.QuotaError, 'user blocks'):
            q.admit_receipt(receipt(), 4 * q.GIB)

    def test_global_block_and_inode_and_user_inode_negative_controls(self):
        cases = [receipt(global_available_bytes=q.GIB), receipt(global_available_inodes=1),
                 receipt(user_inodes=dict(limit=100, remaining=1, used=99))]
        for raw in cases:
            with self.subTest(receipt=raw), self.assertRaises(q.QuotaError):
                q.admit_receipt(raw, q.GIB)

    def test_known_unlimited_user_quota_still_obeys_global_floors(self):
        raw = receipt(user_blocks=dict(limit=None, remaining=None, used=10), user_inodes=dict(limit=None, remaining=None, used=2))
        q.admit_receipt(raw, q.GIB)
        raw['global_available_bytes'] = q.GIB
        with self.assertRaises(q.QuotaError):
            q.admit_receipt(raw, q.GIB)

    def test_unknown_stale_and_future_quota_or_invalid_reservations_fail(self):
        for raw in (receipt(status='unknown'), receipt(observed_at_unix=time.time() - 31),
                    receipt(observed_at_unix=time.time() + 31)):
            with self.subTest(receipt=raw), self.assertRaises(q.QuotaError):
                q.admit_receipt(raw, 1)
        for value in (-1, True, 1.5):
            with self.subTest(reservation=value), self.assertRaises(q.QuotaError):
                q.admit_receipt(receipt(), value)

    def test_cannot_read_other_uid_or_use_unverified_host_abi(self):
        with self.assertRaisesRegex(q.QuotaError, 'own UID'):
            q.user_quota('/dev/shm', uid=q.os.getuid() + 1)
        with patch.object(q.platform, 'system', return_value='Darwin'), self.assertRaises(q.QuotaError):
            q.user_quota('/dev/shm')


if __name__ == '__main__':
    unittest.main()
