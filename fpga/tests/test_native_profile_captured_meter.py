"""Historical identity reads captured accounting; never grants live admission."""
import copy
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from fpga.tools import global_queue_v1 as queue
from fpga.tools import native_profile_variants_v14 as matcher


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'queue/done/s4-p16-c2-storage2-aw8-normal-q1-v1.json'


class CapturedMeterIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_bytes = ORIGINAL.read_bytes()
        cls.original = json.loads(cls.original_bytes)
        cls.package = next(p for p in queue.packages(cls.original)
                           if p['profile'].startswith('azure-burst16-'))
        archive = Path(cls.package['archive'])
        with tarfile.open(archive, 'r:gz') as source:
            cls.manifest = json.loads(source.extractfile('manifest.json').read())
            cls.budget = json.loads(source.extractfile('ticket.json').read())['budget']
        cls.root = archive.parent / 'capture/source/fpga'
        cls.meter = cls.root / matcher.METERS[cls.budget['checker_sha256']]

    def test_all_historical_variants_bind_same_existing_pass_identity(self):
        self.assertEqual(queue.expected_identity(self.original),
                         self.original['dependency_gate']['functional_sha256'])
        self.assertEqual(ORIGINAL.read_bytes(), self.original_bytes)

    def test_actual_captured_parser_not_mutable_workspace_and_no_admission(self):
        before = hashlib.sha256(self.meter.read_bytes()).hexdigest()
        live = ROOT / matcher.METERS[self.budget['checker_sha256']]
        live_before = hashlib.sha256(live.read_bytes()).hexdigest()
        self.assertEqual(before, self.budget['checker_sha256'])
        self.assertNotEqual(before, live_before)
        with patch.object(matcher, 'load', wraps=matcher.load) as loads:
            value = matcher.functional_fingerprint(self.manifest, self.budget, self.root)
        self.assertIn((self.meter, before), [call.args for call in loads.call_args_list])
        self.assertNotIn((live, before), [call.args for call in loads.call_args_list])
        self.assertEqual(value['sha256'], self.original['dependency_gate']['functional_sha256'])
        self.assertIs(value['fresh_budget_admission_conferred'], False)
        self.assertEqual(hashlib.sha256(self.meter.read_bytes()).hexdigest(), before)
        self.assertEqual(hashlib.sha256(live.read_bytes()).hexdigest(), live_before)

    def test_captured_parser_drift_still_rejected_before_import(self):
        with tempfile.TemporaryDirectory(prefix='captured-meter-negative-') as directory:
            root = Path(directory).resolve()
            target = root / matcher.METERS[self.budget['checker_sha256']]
            target.parent.mkdir(parents=True)
            target.write_bytes(self.meter.read_bytes() + b'\n# deliberate identity drift\n')
            with self.assertRaisesRegex(ValueError, 'exact trusted helper'):
                matcher.functional_fingerprint(self.manifest, self.budget, root)

    def test_current_or_unknown_meter_cannot_replace_historical_descriptor(self):
        current = hashlib.sha256((ROOT / matcher.METERS[self.budget['checker_sha256']]).read_bytes()).hexdigest()
        for pin in (current, '0' * 64):
            budget = copy.deepcopy(self.budget)
            budget['checker_sha256'] = pin
            with self.subTest(pin=pin), self.assertRaisesRegex(ValueError, 'exact source-bound finite'):
                matcher.functional_fingerprint(self.manifest, budget, self.root)

    def test_captured_accounting_evidence_pin_still_required(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['sources'][matcher.METERS[self.budget['checker_sha256']]] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'source-closed accounting/control evidence'):
            matcher.functional_fingerprint(manifest, self.budget, self.root)

    def test_noncanonical_captured_root_still_rejected(self):
        with tempfile.TemporaryDirectory(prefix='captured-root-negative-') as directory:
            link = Path(directory).resolve() / 'capture'
            link.symlink_to(self.root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'canonical accounting closure'):
                matcher.functional_fingerprint(self.manifest, self.budget, link)


if __name__ == '__main__':
    unittest.main()
