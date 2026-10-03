import unittest
from fpga.reference.stream27_r15_qsys_aperture_component_v1 import component


class Component(unittest.TestCase):
    def test_full64_precedes_generated_decoder(self):
        text=component()
        self.assertEqual(text.count('address Input 64'),2)
        self.assertEqual(text.count('address Output 64'),2)
        self.assertEqual(text.count('addressUnits SYMBOLS'),4)
        self.assertEqual(text.count('bitsPerSymbol 8'),4)
        self.assertIn('write_in wr_waitrequest waitrequest Output 1',text)
        self.assertIn('write_out down_wr_waitrequest waitrequest Input 1',text)
        self.assertIn('read_in rd_readdata readdata Output 256',text)
        self.assertIn('read_out down_rd_readdata readdata Input 256',text)
        self.assertIn('fault_valid valid Output 1',text)
        self.assertIn('fault_ready ready Input 1',text)
