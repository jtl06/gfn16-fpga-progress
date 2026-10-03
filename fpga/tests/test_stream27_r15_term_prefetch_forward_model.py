import unittest
from fpga.reference import stream27_r15_term_prefetch_forward_model as m


class TermForwardModelTests(unittest.TestCase):
    def test_arbitrary_accepted_collisions_and_full_owner(self):
        r=m.random_state_relation()
        self.assertEqual(r['raw_pre_post_comparisons'],200000)
        self.assertEqual(r['accepted_collisions'],r['accepted_write_forwards'])
        self.assertFalse(r['numeric_changed'])

    def test_first_pw_anticipates_cache_transition(self):
        r=m.first_pw_and_cache_cases()
        self.assertFalse(r['current_ready_at_prefetch'])
        self.assertTrue(r['next_ready_at_consumer'])
        self.assertTrue(r['mutated_seed3_row_to_zero']['numeric_equal_with_forward'])
        self.assertFalse(r['mutated_seed3_row_to_zero']['new_collision_fault_added'])

    def test_async_reset_known_payload_needs_default_cell_shadow(self):
        r=m.reset_default_counterexample()
        self.assertTrue(r['prefetch_q_hold_only_changes_first_malformed_origin_RAW'])
        self.assertTrue(r['shadow_fallback_raw_equal'])

    def test_actual_captured_calendars_not_old_timing10(self):
        for n in (256,65536):
            r=m.captured_calendar(n)
            self.assertEqual(len(r['frames']),8)
            self.assertTrue(r['scalar_calendar_only'])


if __name__=='__main__':unittest.main()
