import unittest
from fpga.reference.stream27_r15_board_glue_v2 import emit


class Board(unittest.TestCase):
    def test_actual_guarded_system_same_real_external_wiring(self):
        text,proof=emit()
        self.assertEqual(len(proof['ports']),243)
        self.assertIn('r15_pcie_system_v2 system_i',text)
        self.assertTrue(proof['external_ports_exactly_unchanged'])
        self.assertFalse(proof['automatic_link_retrain_or_FLR_reset_claim'])
