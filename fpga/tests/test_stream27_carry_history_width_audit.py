import unittest

from fpga.reference.stream27_carry_history_width_audit import analyze, history_step, signed


class CarryHistoryAuditTests(unittest.TestCase):
    def test_full_profile_and_existing_synthesis(self):
        result = analyze()
        self.assertEqual(result["minimum_signed_history_width"], 19)
        self.assertEqual(result["exhaustive_legal_q_checks"], 262881)
        self.assertEqual(len(result["registered_mux_groups"]), 16)

    def test_reset_bubble_and_origin_fault_do_not_capture(self):
        history = (1, -2, 3, -4)
        self.assertEqual(history_step(history, None, 131440, 19), (history, False))
        self.assertEqual(history_step(history, 524291, 131440, 19), (history, True))
        self.assertEqual(history_step(history, None, 131440, 19, reset=True), ((0, 0, 0, 0), False))

    def test_pre_guard_trimming_hides_a_real_fault(self):
        self.assertEqual(signed(524291, 19), 3)
        self.assertTrue(history_step((0, 0, 0, 0), 524291, 131440, 19)[1])


if __name__ == "__main__":
    unittest.main()
