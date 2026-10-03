import unittest
from fpga.reference.stream27_r15_board_constraints_v1 import pins,base_clocks


class Board(unittest.TestCase):
    def test_exact_observed_ports_and_no_virtualization(self):
        s=pins();c=base_clocks()
        self.assertEqual(s.count('set_location_assignment '),36)
        self.assertIn('PIN_AP20 -to {clk_u59}',s)
        self.assertIn('PIN_AN29 -to {clk_pcie1}',s)
        self.assertIn('PIN_AN28 -to {clk_pcie1(n)}',s)
        self.assertIn('PIN_AW16 -to {pcie1_perstn}',s)
        self.assertEqual(s.count('set_instance_assignment -name IO_STANDARD '),19)
        self.assertEqual(c.count('create_clock '),2)
        self.assertEqual(c.count('-period 10.000'),2)
        self.assertNotIn('set_false_path',c)
        self.assertNotIn('set_clock_groups',c)


if __name__=='__main__':unittest.main()
