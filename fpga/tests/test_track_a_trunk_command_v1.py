import unittest
from fpga.reference.track_a_trunk_command_prepare_v1 import ROOT,PARENTS,expected,cpp

class CommandBranches(unittest.TestCase):
    def test_exact_two_branch_harnesses(self):
        for mode,(_,_,old,_) in PARENTS.items():
            child=(ROOT/cpp(mode)).read_text()
            self.assertEqual(child,expected(mode));self.assertNotIn(old,child)
            self.assertIn('A4_CORE_RESPONSE_HOLD',child)
            self.assertIn('A4_CORE_RESET_CANCEL',child)

if __name__=='__main__':unittest.main()
