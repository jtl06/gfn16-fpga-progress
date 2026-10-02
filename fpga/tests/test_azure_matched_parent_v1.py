from pathlib import Path
import shutil
import tempfile
import unittest
from fpga.cloud.verify_azure_matched_parent_v1 import verify


class MatchedParentTests(unittest.TestCase):
    def test_exact_baseline_and_no_changed_blocks(self):
        project=Path(__file__).parents[1]/'artifacts/azure-matched-crt-hostbench-prepared-v2/crt27-mont-azure-hostbench-v1'
        self.assertEqual(verify(project)['changed_rtl_blocks'],[])

    def test_even_benign_control_comment_is_not_a_matched_benchmark(self):
        original=Path(__file__).parents[1]/'artifacts/azure-matched-crt-hostbench-prepared-v2/crt27-mont-azure-hostbench-v1'
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder).resolve()/'project';shutil.copytree(original,project)
            qsf=project/'probe.qsf';qsf.write_text(qsf.read_text()+'# changed\n')
            with self.assertRaisesRegex(ValueError,'changed source/control'):verify(project)


if __name__=='__main__':unittest.main()
