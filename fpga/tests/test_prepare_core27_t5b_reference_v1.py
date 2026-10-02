"""Archive/config construction only; no arithmetic, subprocess or dispatch."""
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('_prepare_t5b_reference',ROOT/'tools/prepare_core27_t5b_reference_v1.py')
PREP=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(PREP)


class PrepareReference(unittest.TestCase):
    def test_dual_short_and_full_closed_packets(self):
        for recipe,count in (('short',7),('full',25)):
            with tempfile.TemporaryDirectory() as temporary:
                result=PREP.prepare(Path(temporary)/'new-packet','soak-test-'+recipe,recipe)
                self.assertFalse(result['arithmetic_executed'])
                self.assertFalse(result['HDL_executed'])
                self.assertEqual(result['source_count'],55)
                ticket=json.loads(Path(result['ticket']).read_text())
                self.assertEqual(ticket['priority'],'P1')
                self.assertEqual(len(ticket['packages']),2)
                for package in ticket['packages']:
                    config=json.loads(Path(package['config']).read_text())
                    self.assertEqual(len(config['expected_files']),count)
                    self.assertEqual(config['containment']['runtime_seconds'],1800)
                    self.assertEqual(config['containment']['memory_bytes'],8<<30)
                    with tarfile.open(package['archive'],'r:gz') as archive:
                        files={m.name for m in archive.getmembers()}
                        self.assertEqual(files,{'reference-config.json',*('source/fpga/'+n for n in config['sources'])})
                        self.assertTrue(all(m.isfile() and m.mode==0o644 for m in archive.getmembers()))

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with self.assertRaisesRegex(ValueError,'fresh reference packet'):
                PREP.prepare(root,'soak-test-v1','short')


if __name__=='__main__':
    unittest.main()
