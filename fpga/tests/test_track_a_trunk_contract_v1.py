import unittest
from fpga.reference.track_a_trunk_contract_v1 import ROOT,TRUNK,branch,verify

class Trunk(unittest.TestCase):
    def test_baseline_source(self):self.assertFalse(verify()['native_flags_off_validated'])
    def test_flags_and_abi(self):
        self.assertEqual(branch()['host_abi'],'T5b_pulse_load_read_start')
        self.assertEqual(branch(True)['child'],'genefer_track_a4_core_v4')
        self.assertEqual(branch(True,True)['child'],'genefer_anext_core_v1')
        for args in ((False,True,False),(False,False,True),(True,False,True),(True,True,True)):
            with self.assertRaises(ValueError):branch(*args)
    def test_port_and_register_mutations(self):
        text=(ROOT/TRUNK).read_text()
        for changed in (text.replace('.load_we,.read_en,.start','.load_we(start),.read_en,.start',1),
                        text.replace('.cycles,.conversion_cycles','.cycles(),.conversion_cycles',1),
                        text+'\nalways_ff @(posedge clk) begin end\n',
                        text.replace('A_TRUNK_LOOKAHEAD_BRANCH_NOT_PORTED','ignored')):
            with self.assertRaises(ValueError):verify(changed)

if __name__=='__main__':unittest.main()
