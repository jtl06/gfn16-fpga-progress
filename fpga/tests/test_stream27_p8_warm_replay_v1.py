"""Read-only archive closure controls; no numerical or native execution."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from fpga.reference import stream27_p8_warm_replay_v1 as replay


class P8WarmReplay(unittest.TestCase):
    def archive(self, path, entries):
        with tarfile.open(path, 'w:gz') as archive:
            for name, raw in entries:
                item = tarfile.TarInfo(name); item.size = len(raw); archive.addfile(item, io.BytesIO(raw))

    def test_exact_archive_and_fail_closed_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'sources.tar.gz'; pins = {'Vfield.cpp': hashlib.sha256(b'source').hexdigest()}
            self.archive(path, [('Vfield.cpp', b'source')]); self.assertEqual(replay.archive_closure(path, pins), 1)
            with self.assertRaisesRegex(ValueError, 'ARCHIVE_SHA'): replay.archive_closure(path, {'Vfield.cpp': '0'*64})
            with self.assertRaisesRegex(ValueError, 'ARCHIVE_CLOSURE'): replay.archive_closure(path, dict(pins, missing='0'*64))
            for entries in ([('Vfield.cpp', b'source'), ('Vfield.cpp', b'source')], [('../escape', b'source')]):
                self.archive(path, entries)
                with self.assertRaisesRegex(ValueError, 'ARCHIVE_MEMBER'): replay.archive_closure(path, pins)


if __name__ == '__main__': unittest.main()
