from pathlib import Path
import sys
import tempfile
import unittest
from fpga.reference.ntt27_prefetch_relink import expected_cases,run

class PrefetchRelinkTests(unittest.TestCase):
    def test_full_normal_manifest_is_93_distinct_cases(self):
        names=sum((expected_cases(field) for field in (1,2,3)),[])
        self.assertEqual(len(names),93)
        self.assertEqual(len(set(names)),93)
        for field in (1,2,3):
            self.assertIn(f"transform-p{field}-aw16-n65536",names)
            self.assertIn(f"squares-p{field}-aw16-n65536",names)
            self.assertIn(f"size-reload-p{field}-aw16",names)

    def test_receipt_command_is_not_a_mutable_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            command=[sys.executable,"-c","pass"]
            receipt=run(Path(tmp),"local-logging-test",command)
            command[-1]="raise SystemExit(1)"
            self.assertEqual(receipt["command"][-1],"pass")
            self.assertTrue(receipt["passed"])

if __name__=="__main__":unittest.main()
