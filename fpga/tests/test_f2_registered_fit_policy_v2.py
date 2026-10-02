"""r53 metadata successor checks; no vendor, worker or numerical work."""
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from fpga.reference import f2_registered_fit_policy_v2 as policy


class FitPolicy(unittest.TestCase):
    def test_only_metadata_changes_and_archives_close_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory).resolve()/'policy'
            result = policy.prepare(output)
            self.assertTrue(result['design_policy_allows_exploratory_fit'])
            self.assertTrue(result['normal_dispatch_checks_still_required'])
            self.assertFalse(result['promotion_allowed'])
            for role, record in result['projects'].items():
                project, original = output/role, policy.PARENT/role
                manifest = json.loads((project/'manifest.json').read_text())
                old = json.loads((original/'manifest.json').read_text())
                self.assertEqual(manifest['source_sha256'], old['source_sha256'])
                self.assertEqual(manifest['control_sha256'], old['control_sha256'])
                self.assertTrue(manifest['r53_policy']['design_prescreen_exempt'])
                self.assertTrue(manifest['r53_policy']['normal_dispatch_resource_source_version_PAUSE_budget_deadline_locks_required'])
                saved = json.loads((project/'structural-source-result-v2.json').read_text())
                self.assertTrue(saved['old_fit_allowed_false_is_superseded_r47_metadata'])
                self.assertTrue(saved['DA_early_placement_graph_are_post_fit_diagnostics'])
                self.assertFalse(saved['production_promotion_allowed'])
                spec = json.loads((project/'structural-spec.json').read_text())
                self.assertEqual(policy.structural.source_inventory(project, spec)['findings'], [])
                expected = {'project/'+p.relative_to(project).as_posix(): policy.sha(p)
                            for p in project.rglob('*') if p.is_file()}
                with tarfile.open(record['source_archive'], 'r:gz') as archive:
                    self.assertTrue(all(m.isfile() for m in archive.getmembers()))
                    self.assertEqual({m.name: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                                      for m in archive.getmembers()}, expected)
                self.assertEqual(record['manifest_sha256'], policy.sha(project/'manifest.json'))
            with self.assertRaisesRegex(ValueError, 'fresh canonical'):
                policy.prepare(output)

    def test_relative_or_existing_output_refused(self):
        with self.assertRaisesRegex(ValueError, 'fresh canonical'):
            policy.prepare(Path('relative'))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'fresh canonical'):
                policy.prepare(Path(directory).resolve())


if __name__ == '__main__':
    unittest.main()
