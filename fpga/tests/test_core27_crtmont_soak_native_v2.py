"""Candidate static-serial dependency checks; no HDL or full-N compute."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fpga.reference import core27_crtmont_soak_native_v2 as n


class SerialSoakRuntimeTests(unittest.TestCase):
    def test_frozen_v1_parent_source_is_unchanged(self):
        self.assertEqual(n.sha(n.ROOT/n.BASE), n.BASE_SHA)
        self.assertEqual(n.base().TOP, 'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont')

    def test_exact_runtime_inventory_refuses_extra_missing_drift_and_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); path = root/'module'; path.write_text('scalar fixture')
            pins = {str(path):n.sha(path)}
            self.assertEqual(n.regular_inventory(root, pins), set(pins))
            extra = root/'extra'; extra.write_text('extra')
            with self.assertRaisesRegex(ValueError, 'EXACT_CLOSURE'):
                n.regular_inventory(root, pins)
            extra.unlink()
            path.write_text('drift')
            with self.assertRaisesRegex(ValueError, 'FILE_DRIFT'):
                n.regular_inventory(root, pins)
            link = root/'linked'; link.symlink_to(path)
            with self.assertRaisesRegex(ValueError, 'SYMLINK'):
                n.regular_inventory(root, pins)

    def test_native_auxiliary_admission_refuses_mac_before_import(self):
        with patch.object(n.platform, 'system', return_value='Darwin'):
            with self.assertRaisesRegex(ValueError, 'REFERENCE_LINUX'):
                n.admit_runtime('{}')

    def test_capture_is_complete_fresh_project_only_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); runtime = root/'runtime.json'; runtime.write_text('{}\n')
            result = n.prepare_reference_source(root/'capture', runtime)
            source = root/'capture/source/fpga'
            actual = {str(path.relative_to(source)):n.sha(path) for path in source.rglob('*') if path.is_file()}
            self.assertEqual(actual, result['sources'])
            self.assertEqual(result['runtime_manifest_sha256'], n.sha(runtime))
            self.assertIn(n.base().AUDIT, actual)
            self.assertIn(n.base().PARENT+'/manifest.json', actual)
            self.assertIn(n.base().PARENT+'/rtl/'+n.base().TOP+'.sv', actual)
            with self.assertRaisesRegex(ValueError, 'FRESH_REFERENCE_CAPTURE'):
                n.prepare_reference_source(root/'capture', runtime)

    def test_wrong_assets_are_not_a_native_replay(self):
        with self.assertRaisesRegex(ValueError, 'VALIDATOR_ASSETS'):
            n.validate('', '', 0, {'negative':'none'}, {'oracle':'{}'})


if __name__ == '__main__':
    unittest.main()
