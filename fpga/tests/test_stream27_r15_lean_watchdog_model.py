import unittest
from fpga.reference.stream27_r15_lean_watchdog_model import Watchdog, old_falseabort, repaired_same_trace


class R15WatchdogModelTests(unittest.TestCase):
    def test_preserved_old_falseabort_and_actual_square_progress(self):
        old = old_falseabort()
        self.assertEqual((old['host_age'], old['watchdog_counter'], old['limit']), (20805, 20479, 20480))
        self.assertEqual(old['started'], [97, 96])
        self.assertEqual(old['completed'], [96, 95])
        fixed = repaired_same_trace()
        self.assertEqual(fixed['error'], [False, False])
        self.assertEqual(fixed['completed'], [96, 95])

    def test_peer_progress_does_not_mask_inflight_stall(self):
        watch = Watchdog(8)
        for edge in range(8):
            watch.step(completed=(edge, 0))
        self.assertEqual(watch.error, [False, True])

    def test_legitimate_gap_and_sticky_cancel_reset(self):
        watch = Watchdog(4)
        for _ in range(20):
            watch.step(demand=(False, False))
        self.assertEqual(watch.error, [False, False])
        for _ in range(4):
            watch.step(demand=(False, True))
        self.assertEqual(watch.error, [False, True])
        watch.step(stop=(False, True), new_job=(True, False))
        self.assertEqual(watch.age, [0, 0])
        self.assertEqual(watch.error, [False, True])
        watch.step(reset=True)
        self.assertEqual(watch.error, [False, False])

    def test_completion_on_deadline_and_decrease_not_progress(self):
        watch = Watchdog(4)
        for _ in range(4):
            watch.step(completed=(7, 0), demand=(True, False))
        self.assertEqual(watch.age[0], 3)
        watch.step(completed=(8, 0), demand=(True, False))
        self.assertFalse(watch.error[0])
        for _ in range(4):
            watch.step(completed=(0, 0), demand=(True, False))
        self.assertTrue(watch.error[0])


if __name__ == '__main__':
    unittest.main()
