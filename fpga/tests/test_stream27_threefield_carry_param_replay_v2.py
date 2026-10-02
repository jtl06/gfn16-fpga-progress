"""Candidate hashes cannot disappear/change under the launcher-only join."""
import unittest
from fpga.reference.stream27_threefield_carry_param_replay_v2 import candidate_source_join

class ReplayJoin(unittest.TestCase):
    def test_candidate_subset_is_exact(self):
        expected={'rtl/one.sv':'a','rtl/tb/one.cpp':'b','reference/validator.py':'c'}
        selected=dict(expected);selected['tools/known_control.py']='d'
        self.assertEqual(candidate_source_join(expected,selected),3)
        for name in expected:
            wrong=dict(selected);wrong[name]='wrong'
            with self.assertRaisesRegex(ValueError,'CANDIDATE_SOURCE'):candidate_source_join(expected,wrong)
            missing=dict(selected);missing.pop(name)
            with self.assertRaisesRegex(ValueError,'CANDIDATE_SOURCE'):candidate_source_join(expected,missing)

if __name__=='__main__':unittest.main()
