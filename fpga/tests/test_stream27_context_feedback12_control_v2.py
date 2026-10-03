"""Exact include-closure successor, preserved v1 failed before native model."""
import unittest
from pathlib import Path
from fpga.reference import stream27_context_feedback12_control as v1
from fpga.reference import stream27_context_feedback12_control_v2 as v2


class Feedback12ControlClosureTests(unittest.TestCase):
    def test_only_missing_generated_header_name_repaired(self):
        old,before=v1.role();new,after=v2.role()
        self.assertEqual(old['build'],new['build'])
        self.assertEqual(before[v1.CPP],after[v2.CPP])
        self.assertEqual(before[v1.HEADER],after[v2.HEADER])
        self.assertNotEqual(Path(v1.HEADER).name,Path(v2.HEADER).name)
        self.assertNotIn(('#include "'+Path(v1.HEADER).name+'"').encode(),before[v1.CPP])
        self.assertIn(('#include "'+Path(v2.HEADER).name+'"').encode(),after[v2.CPP])
        for name in new['build']['sv_sources']:
            self.assertEqual(before[name],after[name])
        self.assertEqual(old['steps'],new['steps'])
        self.assertTrue(new['feedback12_control']['predecessor_R12_v1_build_failure_retained'])
        self.assertTrue(new['feedback12_control']['include_header_name_only_repair'])


if __name__=='__main__':unittest.main()
