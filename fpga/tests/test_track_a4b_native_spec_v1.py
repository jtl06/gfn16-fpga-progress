import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference.track_a4b_native_spec_v1 import prepare
from fpga.reference.track_a4_admission_boundary_v1 import MUTANT_CASES
from fpga.tools.prefit_structural_guard_v1 import file_digest

class A4bNativeRoleTests(unittest.TestCase):
    def test_closed_roles_and_precise_mutant_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            for role in ('normal-aw5','boundary-control','representative-aw16','raw_fault_regating'):
                root=Path(d)/role;result=prepare(root,role);m=json.loads((root/'manifest.json').read_text())
                actual={str(p.relative_to(root/'source/fpga')) for p in (root/'source/fpga').rglob('*') if p.is_file()}
                self.assertEqual(actual,set(m['sources']))
                self.assertTrue(all(file_digest(root/'source/fpga'/name)==pin for name,pin in m['sources'].items()))
                self.assertFalse(result['promotion_allowed'])
                if role=='raw_fault_regating':
                    self.assertEqual(m['steps'][0]['expected_returncode'],1)
                    self.assertEqual(m['steps'][0]['expected_stderr'],MUTANT_CASES[role][1]+'\n')
                if role=='boundary-control':self.assertEqual(len(m['steps']),5)
                if role=='representative-aw16':self.assertEqual(m['build']['parameters'],{'AW':16})
                with self.assertRaises(AssertionError):prepare(root,role)

if __name__=='__main__':unittest.main()
