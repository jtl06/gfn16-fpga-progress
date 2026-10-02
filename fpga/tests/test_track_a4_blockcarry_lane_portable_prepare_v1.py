"""Source-only preparation checks; no HDL/native compilation."""
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from fpga.reference import track_a4_blockcarry_lane_portable_prepare_v1 as p
from fpga.reference.track_a4_blockcarry_lane_vectors_v1 import corpus


class PortableA4PreparationTests(unittest.TestCase):
    def test_pinned_author_and_launcher(self):
        pins, receipt = p.source_pins()
        self.assertEqual(pins[p.LAUNCHER], '5205f587313a1403fddabff58bbcf4565d27c8219aa2e0c3f4aaa3af2901c2cd')
        self.assertEqual(receipt['native_top'], p.TOP)
        with patch.dict(p.PINS, {p.LAUNCHER: '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'source pin drift'):
                p.source_pins()

    def test_footer_and_compile_geometry_are_bound(self):
        for aw in (5, 8):
            text, metadata = corpus(aw)
            stdout, counts = p.footer(text, metadata)
            manifest = p.manifest(aw, {}, stdout)
            self.assertEqual(manifest['build']['parameters'], {'AW': aw})
            self.assertIn(f'-DA4_LANE_AW={aw}', manifest['build']['cflags'])
            self.assertEqual(manifest['steps'][0]['expected_stderr'], '')
            self.assertGreater(counts['error_edges'], metadata['errors'])
            self.assertEqual(counts['completed'], 89)
            self.assertEqual(metadata['errors'], 12)
        for aw in (4, 6, 16, True):
            with self.assertRaises(ValueError):
                p.manifest(aw, {}, '')

    def test_fresh_complete_snapshot_and_exact_manifest_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'stage'
            report = p.prepare(output)
            for aw in (5, 8):
                entry = report['manifests'][f'aw{aw}']
                manifest = json.loads((output / entry['path']).read_text())
                self.assertEqual(manifest['sources'], report['source_sha256'])
                self.assertEqual(p.sha(output / entry['path']), entry['sha256'])
            source = output / 'source/fpga'
            self.assertEqual({str(f.relative_to(source)) for f in source.rglob('*') if f.is_file()}, set(report['source_sha256']))
            with tarfile.open(output / 'source.tar.gz') as archive:
                self.assertEqual({m.name for m in archive}, {'fpga/' + name for name in report['source_sha256']})
            with self.assertRaisesRegex(ValueError, 'fresh preparation'):
                p.prepare(output)


if __name__ == '__main__':
    unittest.main()
