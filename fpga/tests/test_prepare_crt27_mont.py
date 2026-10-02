import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from fpga.synthesis.prepare_crt27_mont import FILES, prepare_pair


class MatchedCrtProbeTests(unittest.TestCase):
    def test_exact_pair_no_execution_and_fresh_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'pair'
            pair = prepare_pair(root)
            self.assertEqual(pair['status'],'prepared_pair_not_dispatched')
            left, right = root/'frozen', root/'montgomery'
            self.assertEqual((left/'probe.qsf').read_text().replace('USE_MONT 0','USE_MONT 1'),
                             (right/'probe.qsf').read_text())
            for p in ('run.tcl','probe.qpf','probe.sdc'):
                self.assertEqual((left/p).read_bytes(),(right/p).read_bytes())
            for project in (left,right):
                manifest=json.loads((project/'manifest.json').read_text())
                self.assertFalse(manifest['bitstream_generation'])
                self.assertEqual(len(manifest['source_sha256']),len(FILES))
                for name,digest in manifest['source_sha256'].items():
                    self.assertEqual(hashlib.sha256((project/'rtl'/name).read_bytes()).hexdigest(),digest)
                self.assertFalse((project/'output_files').exists())
            with self.assertRaises(FileExistsError):prepare_pair(root)


if __name__ == '__main__':unittest.main()
