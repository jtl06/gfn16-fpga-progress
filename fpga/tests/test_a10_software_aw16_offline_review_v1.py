"""Pure archive tests, no NTT execution or remote/native commands."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from fpga.reference import a10_software_aw16_offline_review_v1 as review


class A10ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'archive'
        shutil.copytree(review.ARCHIVE, self.directory)

    def test_exact_source_case_fault_limit_and_terminal_replay(self):
        result = review.verify(self.directory)
        self.assertEqual((result['cases'], result['typed_negatives']), (12, 27))
        self.assertEqual(result['residues_compared'], 2359296)
        self.assertTrue(result['CPU0_2_released'])
        self.assertFalse(result['promotion_allowed'])

    def test_missing_typed_negative_cannot_replace_frozen_receipt(self):
        path = self.directory / 'gate/receipt.json'
        report = json.loads(path.read_text())
        report['negative_controls'].pop()
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'collected artifact pin'):
            review.verify(self.directory)

    def test_wrong_invocation_observation_rejected(self):
        path = self.directory / 'terminal-read.json'
        report = json.loads(path.read_text())
        report['invocation_id'] = '0' * 32
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'collected artifact pin'):
            review.verify(self.directory)

    def test_extra_payload_rejected(self):
        (self.directory / 'extra.py').write_text('fixture')
        with self.assertRaisesRegex(ValueError, 'exact archive closure'):
            review.verify(self.directory)


if __name__ == '__main__':
    unittest.main()
