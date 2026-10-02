"""Fail-closed retained generated-source closure; never invokes native."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from fpga.reference import a10_upper_sum_replay_v2 as replay


class UpperSumReplay(unittest.TestCase):
    def archive(self, path, entries):
        with tarfile.open(path, 'w:gz') as archive:
            for name, raw in entries:
                item = tarfile.TarInfo(name); item.size = len(raw)
                archive.addfile(item, io.BytesIO(raw))

    def test_generated_exact_and_mismatches(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'sources.tar.gz'; pins = {'Vpair.cpp': hashlib.sha256(b'source').hexdigest()}
            self.archive(path, [('Vpair.cpp', b'source')])
            self.assertEqual(replay.generated_closure(path, pins), 1)
            with self.assertRaisesRegex(ValueError, 'GENERATED_SHA'):
                replay.generated_closure(path, {'Vpair.cpp': '0'*64})
            with self.assertRaisesRegex(ValueError, 'GENERATED_CLOSURE'):
                replay.generated_closure(path, dict(pins, missing='0'*64))
            for entries in ([('Vpair.cpp', b'source'), ('Vpair.cpp', b'source')],
                            [('../escape', b'source')], [('/absolute', b'source')]):
                self.archive(path, entries)
                with self.assertRaisesRegex(ValueError, 'GENERATED_MEMBER'):
                    replay.generated_closure(path, pins)


if __name__ == '__main__': unittest.main()
