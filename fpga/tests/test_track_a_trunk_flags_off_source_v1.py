import unittest
from fpga.reference.track_a_trunk_flags_off_source_v1 import expected,verify

class FlagsOff(unittest.TestCase):
    def test_exact_successors(self):self.assertFalse(verify()['native_pass'])
    def test_probe_binding_and_lockstep(self):
        probe=expected()['rtl/tb/track_a_trunk_flags_off_probe_v1.sv']
        self.assertIn('selected.baseline.dut.field_lane[f].engine.child.data_we',probe)
        self.assertIn('A_TRUNK_FLAGS_OFF_CYCLE_MISMATCH',probe)
        self.assertIn('A_TRUNK_FLAGS_OFF_WORD_MISMATCH',probe)
        self.assertIn('.cmd_valid(1\'b1)',probe)

if __name__=='__main__':unittest.main()
