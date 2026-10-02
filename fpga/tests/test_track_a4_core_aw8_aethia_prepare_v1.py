import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import track_a4_core_aw8_aethia_prepare_v1 as prepare
from fpga.tools import native_source_gate_v1 as policy


class AW8PreparationTests(unittest.TestCase):
    def test_exact_aw8_snapshot_and_review_path(self):
        with tempfile.TemporaryDirectory() as directory:
            stage=Path(directory).resolve()/'fresh'
            report=prepare.prepare(stage)
            manifest=json.loads((stage/'aw8-manifest.json').read_text())
            policy.check_sources(stage/'snapshot/source/fpga',manifest['sources'])
            self.assertEqual(manifest['build']['parameters'],{'AW':8})
            self.assertIn('-DA4_CORE_AW=8',manifest['build']['cflags'])
            self.assertEqual(report['corpus']['commands'],3092)
            self.assertEqual(report['corpus']['sha256'],'30f2db61016b3a2d26632beae08e80ee42dd38244155a622419af346b7147080')
            self.assertEqual(manifest['stdout_review']['parser_sha256'],'9ec50d9beb703e7b594f20bab41c18dd6a8ed6772990fb9f3b57c12b4b2cfa9f')
            self.assertIn(prepare.PARSER_BASE,manifest['sources'])
            self.assertIn(prepare.PARSER_TEST,manifest['sources'])
            self.assertEqual(report['required_output_replay'][0],'env')
            self.assertTrue(report['required_output_replay'][1].endswith('/snapshot-v1'))
            self.assertNotIn('expected_stdout',manifest['steps'][0])
            with self.assertRaisesRegex(ValueError,'fresh'):prepare.prepare(stage)


if __name__=='__main__':unittest.main()
