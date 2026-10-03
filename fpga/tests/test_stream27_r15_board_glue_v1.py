import unittest
from fpga.reference.stream27_r15_board_glue_v1 import emit


class Glue(unittest.TestCase):
    def test_actual_generated_ports_all_classified(self):
        sv,p=emit()
        self.assertEqual(len(p['ports']),243)
        for i in range(8):
            self.assertEqual(p['ports'][f'pcie_rx_in{i}']['connection'],f'pcie1_rx[{i}]')
            self.assertEqual(p['ports'][f'pcie_tx_out{i}']['connection'],f'pcie1_tx[{i}]')
        self.assertIn('.pcie_test_in(32\'h00000188)',sv)
        self.assertIn('.core_pll_rst(!pcie1_perstn)',sv)
        self.assertNotIn('VIRTUAL_PIN',sv)
        self.assertFalse(p['vendor_simulation_claim'])
        self.assertTrue(all(v['connection'] for v in p['ports'].values() if v['direction']=='input'))


if __name__=='__main__':unittest.main()
