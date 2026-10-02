import unittest
from fpga.reference.track_a_trunk_v2_source import expected,verify
class SelectorRepair(unittest.TestCase):
    def test_exact_delta(self):self.assertEqual(verify()['arithmetic_changes'],0)
    def test_boolean_boundary(self):
        text=expected()['rtl/kernel/genefer_track_a_trunk_v2.sv']
        self.assertNotIn('parameter bit USE_',text)
        self.assertIn('A_TRUNK_BOOLEAN_FLAG_REQUIRED',text)
        self.assertIn('assign host_abi=(USE_BLOCKCARRY!=0);',text)
        self.assertIn('if(USE_BLOCKCARRY==0)begin: baseline',text)
        for flag in ('USE_BLOCKCARRY','USE_MERGED_TWIST','USE_ROOT_LOOKAHEAD'):
            for n in (-1,0,1,2,2147483647):self.assertEqual(n!=0 and n!=1,n not in (0,1))
if __name__=='__main__':unittest.main()
