"""Presentation evidence gates; not replacement HDL or timing tests."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.progress.selected_clock import verified_whole16_clock

RESULTS = Path(__file__).resolve().parents[1] / 'results/throughput-20260929'


class SelectedClockTests(unittest.TestCase):
    def test_real_source_linked_archive(self):
        evidence = verified_whole16_clock(RESULTS)
        self.assertEqual(evidence['planning_clock_mhz'], 85)
        self.assertGreater(evidence['audited_clock_mhz'], 85)
        self.assertEqual(evidence['minimum_slack_ns'], dict(setup=.358, hold=.017, mpw=5.231))
        self.assertIn('excluded', evidence['scope'])

    def test_missing_archive_is_not_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                verified_whole16_clock(Path(directory))

    def test_changed_review_fails_closed(self):
        with patch.object(Path, 'read_bytes', return_value=b'{}'):
            with self.assertRaisesRegex(ValueError, 'review changed'):
                verified_whole16_clock(RESULTS)

    def test_changed_artifact_fails_closed(self):
        original = Path.read_bytes
        def read(path):
            return b'changed' if path.name == 'audit.log' else original(path)
        with patch.object(Path, 'read_bytes', read):
            with self.assertRaisesRegex(ValueError, 'artifact changed'):
                verified_whole16_clock(RESULTS)

    def test_changed_regression_fails_closed(self):
        original = Path.read_bytes
        def read(path):
            return b'changed' if path.name == 'report.json' else original(path)
        with patch.object(Path, 'read_bytes', read):
            with self.assertRaisesRegex(ValueError, 'regression changed'):
                verified_whole16_clock(RESULTS)


if __name__ == '__main__':
    unittest.main()
