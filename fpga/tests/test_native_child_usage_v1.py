"""Mock POSIX process collection only; no child, compiler or model is run."""
import os
import subprocess
import types
import unittest
from unittest.mock import patch

from fpga.tools import native_child_usage_v1 as usage


class ChildUsageTests(unittest.TestCase):
    def child(self):
        child = object.__new__(usage.MeasuredPopen)
        child.pid = 123
        child.args = ['source-only-stub']
        child.returncode = None
        return child

    def test_poll_captures_actual_child_once_and_repeated_wait_never_reaps_twice(self):
        child = self.child()
        values = types.SimpleNamespace(ru_utime=1.25, ru_stime=.5, ru_maxrss=512)
        with patch.object(usage.os, 'wait4', side_effect=[(0, 0, None), (123, 0, values)]) as wait:
            self.assertIsNone(child.poll())
            self.assertEqual(child.poll(), 0)
            self.assertEqual(child.wait(), 0)
            self.assertEqual(wait.call_count, 2)
        with patch.object(usage.platform, 'system', return_value='Linux'):
            receipt = child.resource_receipt()
        self.assertEqual(receipt['peak_rss_kib'], 512)
        self.assertEqual(receipt['user_seconds'], 1.25)

    def test_exit_and_signal_codes_are_exact(self):
        for status, code in ((2 << 8, 2), (9, -9)):
            child = self.child()
            with patch.object(usage.os, 'wait4', return_value=(123, status, object())):
                self.assertEqual(child.wait(), code)
                self.assertEqual(child.poll(), code)

    def test_timeout_and_unknown_collection_fail_without_false_receipt(self):
        child = self.child()
        with patch.object(usage.os, 'wait4', return_value=(0, 0, None)), \
                patch.object(usage.time, 'monotonic', side_effect=[0, 1]):
            with self.assertRaises(subprocess.TimeoutExpired):
                child.wait(timeout=.5)
        with patch.object(usage.platform, 'system', return_value='Linux'):
            with self.assertRaisesRegex(ValueError, 'reaped Linux'):
                child.resource_receipt()
        with patch.object(usage.os, 'wait4', return_value=(124, 0, object())):
            with self.assertRaisesRegex(ValueError, 'child PID'):
                child.poll()


if __name__ == '__main__':
    unittest.main()
