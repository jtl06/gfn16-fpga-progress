"""Pure guard tests for the exact-entry destructive helper; no source writes."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location('evict',
    Path(__file__).resolve().parents[1] / 'tools' / 'evict_cold_cache_entry.py')
evict = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evict)


class GuardTests(unittest.TestCase):
    def test_known_infrastructure_requires_exact_argv(self):
        self.assertEqual(evict.infrastructure('systemd', ['/usr/lib/systemd/systemd', '--user'],
                         10, set(), []), 'exact-systemd-user')
        self.assertIsNone(evict.infrastructure('systemd', ['/usr/lib/systemd/systemd', '--system'],
                          10, set(), []))
        self.assertEqual(evict.infrastructure('(sd-pam)', ['(sd-pam)'], 11, set(), []), 'exact-sd-pam')
        self.assertIsNone(evict.infrastructure('(sd-pam)', ['(sd-pam)', 'extra'], 11, set(), []))
        self.assertIsNone(evict.infrastructure('dbus-daemon', ['/usr/bin/dbus-daemon'], 12, set(), []))

    def test_jobs_and_consumers_are_detected(self):
        for comm, argv in [('cc1plus', ['/usr/lib/gcc/cc1plus']),
                           ('Vgenefer_squar', ['./Vgenefer_square_core']),
                           ('python3', ['python3', 'square_core_regression.py']),
                           ('python3', ['python3', '/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/reference/probe.py'])]:
            self.assertTrue(evict.is_job(comm, argv))
        self.assertFalse(evict.is_job('python3', ['python3', '-', '--apply', '--confirm-key', evict.KEY]))

    def test_tailscaled_cannot_be_unrelated_process(self):
        argv = ['/usr/sbin/tailscaled'] + ['x'] * 13 + ['--cmd=python3 -']
        self.assertIsNone(evict.infrastructure('tailscaled', argv, 10, set(), ['python3', '-']))
        self.assertIsNone(evict.infrastructure('tailscaled', argv, 10, {10}, ['python3', '-']))

    def test_tailscaled_exact_command_validation(self):
        prefix = ['/usr/sbin/tailscaled'] + ['x'] * 13
        sha = hashlib.sha256(evict.canonical(prefix)).hexdigest()
        original = evict.TAILSCALED_PREFIX_SHA
        evict.TAILSCALED_PREFIX_SHA = sha
        try:
            self.assertEqual(evict.infrastructure('tailscaled', prefix + ['--cmd=python3 -'],
                             10, {10}, ['python3', '-']), 'exact-current-ssh-ancestor')
            for command in ['python3 -; touch /tmp/x', 'python3 - && true',
                            'python3 - > /tmp/x', 'python3 unrelated.py']:
                self.assertIsNone(evict.infrastructure('tailscaled', prefix + ['--cmd=' + command],
                                  10, {10}, ['python3', '-']))
        finally:
            evict.TAILSCALED_PREFIX_SHA = original

    def test_saved_receipt_hashes_match(self):
        receipt_root = Path(__file__).resolve().parents[1] / 'results/throughput-20260929/cold-cache-fe1ea1907ad7-v1'
        for filename, _, sha in evict.RECEIPTS.values():
            evict.pinned_bytes(receipt_root / filename, sha)
            with self.assertRaises(RuntimeError):
                evict.pinned_bytes(receipt_root / filename, '0' * 64)


if __name__ == '__main__':
    unittest.main()
