from pathlib import Path
import json
import tempfile
import unittest
from fpga.reference import stream27_full_probe_lint_v1 as m


class FullLint(unittest.TestCase):
    def test_exact_physical_rtl_no_numeric_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            for variant,count in [('p16c',13),('p8b',12)]:
                out=Path(tmp)/variant;r=m.prepare(out,variant)
                self.assertEqual(r['unchanged_rtl_sources'],count)
                self.assertEqual(r['required_package_phase'],'lint')
                manifest=json.loads((out/'manifest.json').read_text())
                self.assertEqual(manifest['build']['parameters'],{'AW':16,'CONTEXTS':1})
                self.assertEqual(len(manifest['build']['sv_sources']),count)
                self.assertIn('no-numerical-test',manifest['steps'][0]['name'])


if __name__=='__main__':unittest.main()
