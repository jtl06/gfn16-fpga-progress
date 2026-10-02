"""Closed digit-image manifest tests, no HDL execution."""
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from fpga.reference import track_a4_digit_image_prepare_v1 as p


class DigitImagePreparationTests(unittest.TestCase):
    def test_source_tamper_rejected_before_import(self):
        with patch.dict(p.PINS,{p.SV[1]:'0'*64}),patch.object(p.importlib,'import_module',side_effect=AssertionError('too early')):
            with self.assertRaisesRegex(ValueError,'source drift'):
                p.prepare(Path('/tmp/must-not-exist-a4-image'))

    def test_manifest_closure_and_exact_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'stage';report=p.prepare(output)
            self.assertEqual(report['source_members'],11)
            for aw in (5,8):
                entry=report['manifests'][f'aw{aw}'];manifest=json.loads((output/entry['path']).read_text())
                self.assertEqual(manifest['build']['parameters'],dict(AW=aw))
                self.assertIn(f'-DA4_IMAGE_AW={aw}',manifest['build']['cflags'])
                self.assertEqual(manifest['sources'],report['source_sha256'])
                self.assertEqual(p.sha(output/entry['path']),entry['sha256'])
                self.assertEqual(manifest['steps'][0]['expected_stderr'],'')
                self.assertGreater(entry['expected_counts']['before_checks'],0)
            with tarfile.open(output/'source.tar.gz') as archive:
                self.assertEqual({m.name for m in archive},{'fpga/'+name for name in report['source_sha256']})
            with self.assertRaisesRegex(ValueError,'fresh preparation'):
                p.prepare(output)


if __name__=='__main__':unittest.main()
