"""Portable route preparation checks; no HDL or native dispatch."""
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from fpga.reference import track_a4_blockroute_portable_prepare_v1 as p
from fpga.reference.track_a4_blockroute_vectors_v1 import corpus


class PortableRoutePreparationTests(unittest.TestCase):
    def test_author_parent_and_launcher_pins(self):
        pins, receipt = p.source_pins()
        self.assertEqual(pins[p.LAUNCHER], '5205f587313a1403fddabff58bbcf4565d27c8219aa2e0c3f4aaa3af2901c2cd')
        for name, digest in receipt['parent_pins'].items():
            self.assertEqual(pins['rtl/kernel/' + name + '.sv'], digest)
        with patch.dict(p.PINS, {p.LAUNCHER: '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'source pin drift'):
                p.source_pins()

    def test_footer_matches_exact_checked_words_and_geometry(self):
        for aw in (5, 8):
            text, meta = corpus(aw)
            stdout, counts = p.footer(text, meta)
            rows = [list(map(int, row.split())) for row in text.splitlines()[1:]]
            expected_words = sum(1 for row in rows for lane in range(16) if row[25] and row[27] & (1 << lane))
            self.assertEqual(counts['words'], expected_words)
            self.assertEqual(counts['responses'], meta['responses'])
            self.assertEqual(counts['errors'], meta['errors'])
            manifest = p.manifest(aw, {}, stdout)
            self.assertEqual(manifest['build']['parameters'], {'AW': aw})
            self.assertIn(f'-DA4_ROUTE_AW={aw}', manifest['build']['cflags'])
            self.assertEqual(manifest['build']['sv_sources'], p.SV)
            self.assertEqual(len(p.SV), 3)
            self.assertEqual(manifest['steps'][0]['expected_stderr'], '')
        for aw in (4, 6, 16, True):
            with self.assertRaises(ValueError):
                p.manifest(aw, {}, '')

    def test_complete_fresh_snapshot_and_manifest_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'stage'
            report = p.prepare(output)
            source = output / 'source/fpga'
            self.assertEqual({str(f.relative_to(source)) for f in source.rglob('*') if f.is_file()}, set(report['source_sha256']))
            for aw in (5, 8):
                entry = report['manifests'][f'aw{aw}']
                manifest = json.loads((output / entry['path']).read_text())
                self.assertEqual(manifest['sources'], report['source_sha256'])
                self.assertEqual(p.sha(output / entry['path']), entry['sha256'])
            with tarfile.open(output / 'source.tar.gz') as archive:
                self.assertEqual({m.name for m in archive}, {'fpga/' + name for name in report['source_sha256']})
            with self.assertRaisesRegex(ValueError, 'fresh preparation'):
                p.prepare(output)


if __name__ == '__main__':
    unittest.main()
