"""Same-profile budget refresh preserves the actual A-next GCP24 role."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_gcp_variant_refresh_v1 as refresh

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'artifacts/anext-soak-chunk00-aw16-gcp01-packet-v2'
NEW = ROOT / 'results/throughput-20260929/gcp-same-profile-refresh-v1/anext-chunk00-01'
RUNNER = 'tools/native_class_package_gcp24_v1.py'


class GcpRefreshTests(unittest.TestCase):
    def test_actual_source_profile_contract_and_fresh_budget(self):
        old = json.loads((OLD / 'manifest.json').read_text())
        new = json.loads((NEW / 'packet/manifest.json').read_text())
        before = json.loads((OLD / 'ticket.json').read_text())
        after = json.loads((NEW / 'packet/ticket.json').read_text())
        for key in ('build', 'probe', 'steps'): self.assertEqual(old[key], new[key])
        self.assertEqual(before['profile'], after['profile'])
        self.assertEqual(before['max_seconds'], after['max_seconds'])
        self.assertNotEqual(before['id'], after['id'])
        self.assertGreater(after['budget']['observed_at'], before['budget']['observed_at'])
        self.assertEqual(after['budget']['source_receipt_sha256'], refresh.sha(NEW / 'host-hours.json'))
        from fpga.tools import native_stage_gcp24_v1 as stage
        receipt = json.loads((NEW / 'refresh-receipt.json').read_text())
        stage.worker().inspect_archive(NEW / 'packet/package.tar.gz', receipt['archive_sha256'], receipt['ticket_sha256'])

    def test_unknown_runner_and_same_id_before_output(self):
        old = json.loads((OLD / 'ticket.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve() / 'new'
            for runner, id in [('tools/native_threaded_package_v1.py', 'new-budget'), (RUNNER, old['id'])]:
                with self.assertRaises(ValueError): refresh.repackage_variant(OLD, runner, id, output)
                self.assertFalse(output.exists())

    def test_drift_and_wrong_host_quote_before_output(self):
        original = refresh.sha
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve() / 'new'
            with patch.object(refresh, 'sha', side_effect=lambda p: '0' * 64 if Path(p) == OLD / 'manifest.json' else original(p)):
                with self.assertRaises(ValueError): refresh.repackage_variant(OLD, RUNNER, 'new-budget', output)
            self.assertFalse(output.exists())
            original_load = refresh.load
            def altered(name, pin):
                result = original_load(name, pin)
                if name.startswith('cloud/'):
                    result.admit = lambda *args: {'status': 'PASS_budget_only_no_job_reservation', 'host_id': 'aws-m8azn', 'outer_runtime_plus_stop_seconds': 3715}
                return result
            with patch.object(refresh, 'load', side_effect=altered):
                with self.assertRaises(ValueError): refresh.repackage_variant(OLD, RUNNER, 'new-budget', output)
            self.assertFalse(output.exists())


if __name__ == '__main__': unittest.main()
