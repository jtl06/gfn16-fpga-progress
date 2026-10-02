import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fpga.tools import snapshot_native_sources_v1 as snapshot


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root/'draft'; self.source.mkdir()
        (self.source/'core.sv').write_text('module core; endmodule\n')
        (self.source/'roots.hex').write_text('0000001\n')
        self.manifest = self.root/'manifest.json'
        self.manifest.write_text(json.dumps(dict(schema='native-source-gate-v1',
            status='prepared_not_executed', source_root='/approved-worker/fpga',
            sources={p.name:snapshot.sha(p) for p in self.source.iterdir()})))

    def capture(self, name='capture'):
        return snapshot.capture(self.manifest, self.source, self.root/name)

    def test_closed_capture_and_archive_are_deterministic(self):
        one, two = self.capture('one'), self.capture('two')
        self.assertEqual(one['status'], 'captured_not_executed')
        self.assertEqual(one['archive_sha256'], two['archive_sha256'])
        self.assertEqual((self.root/'one/approved-manifest.json').read_bytes(), self.manifest.read_bytes())
        self.assertEqual(one['files'], 2)

    def test_existing_snapshot_is_never_overwritten(self):
        self.capture()
        before = snapshot.sha(self.root/'capture/source.tar.gz')
        with self.assertRaises(FileExistsError): self.capture()
        self.assertEqual(snapshot.sha(self.root/'capture/source.tar.gz'), before)

    def test_extra_file_and_changed_source_rejected(self):
        (self.source/'extra').write_text('not in manifest')
        with self.assertRaisesRegex(ValueError, 'closure'): self.capture()
        (self.source/'extra').unlink()
        (self.source/'core.sv').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'drift'): self.capture()

    def test_symlink_rejected(self):
        (self.source/'core.sv').unlink()
        (self.source/'core.sv').symlink_to(self.source/'roots.hex')
        with self.assertRaisesRegex(ValueError, 'symlink'): self.capture()

    def test_midcopy_source_change_preserves_failed_attempt(self):
        original = snapshot.shutil.copyfile
        def change(source, target):
            result = original(source, target)
            (self.source/'core.sv').write_text('edited during capture')
            return result
        with patch.object(snapshot.shutil, 'copyfile', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'drift'): self.capture()
        report = json.loads((self.root/'capture/capture.json').read_text())
        self.assertEqual(report['status'], 'failed_capture_preserved')


if __name__ == '__main__': unittest.main()
