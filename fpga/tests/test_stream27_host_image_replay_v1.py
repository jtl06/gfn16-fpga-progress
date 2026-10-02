"""Fail-closed retained-source archive replay controls; no native execution."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from fpga.reference import stream27_host_image_replay_v1 as replay


class HostImageReplay(unittest.TestCase):
    def archive(self, path, entries):
        with tarfile.open(path, 'w:gz') as archive:
            for name, raw in entries:
                item = tarfile.TarInfo(name); item.size = len(raw)
                archive.addfile(item, io.BytesIO(raw))

    def test_generated_closure_exact_and_mismatches(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'sources.tar.gz'
            self.archive(path, [('Vpair.cpp', b'source')])
            pins = {'Vpair.cpp': hashlib.sha256(b'source').hexdigest()}
            self.assertEqual(replay.generated_closure(path, pins), 1)
            with self.assertRaisesRegex(ValueError, 'GENERATED_SHA'):
                replay.generated_closure(path, {'Vpair.cpp': '0'*64})
            with self.assertRaisesRegex(ValueError, 'GENERATED_CLOSURE'):
                replay.generated_closure(path, dict(pins, missing='0'*64))
            self.archive(path, [('Vpair.cpp', b'source'), ('Vpair.cpp', b'source')])
            with self.assertRaisesRegex(ValueError, 'GENERATED_MEMBER'):
                replay.generated_closure(path, pins)
            self.archive(path, [('../escape', b'source')])
            with self.assertRaisesRegex(ValueError, 'GENERATED_MEMBER'):
                replay.generated_closure(path, {'../escape': hashlib.sha256(b'source').hexdigest()})


if __name__ == '__main__':
    unittest.main()
