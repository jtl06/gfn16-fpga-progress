import unittest
from fpga.reference import stream27_term_prefetch_density_model as m


class PrefetchModel(unittest.TestCase):
    def test_small_and_full_exact_calendar_symbolic_pair(self):
        for n in (256,65536):
            result=m.simulate(n)
            self.assertEqual(result['symbolic_lane_comparisons'],8*(n//16)*16)
            self.assertEqual(result['rdw_collisions'],0)
            self.assertEqual(result['enabled_prefetch_reads'],8*(n//16))
            self.assertEqual(result['accepted_e4_writes'],8*(n//16))

    def test_canceled_raw_tail_remains_numeric_equal(self):
        result=m.simulate(65536,canceled_ctx=1)
        self.assertEqual(result['canceled_raw_lane_comparisons'],4*65536)
        self.assertEqual(result['rdw_collisions'],0)

    def test_unreset_stale_payload_and_stop_after_origin(self):
        self.assertEqual(m.simulate(256,stale_payload=True)['symbolic_lane_comparisons'],8*256)
        stopped=m.simulate(256,fault_at=85)
        self.assertEqual(stopped['symbolic_lane_comparisons'],7*16)
        self.assertEqual(stopped['rdw_collisions'],0)

    def test_collision_proof_not_overgeneralized(self):
        examples=m.address_counterexamples()
        self.assertFalse(examples['required_explicit_numeric_predicted_valid']['predicted_valid'])
        example=examples['no_universal_collision_proof_for_arbitrary_product_row_mutation']
        self.assertEqual(example['read'],example['write'])

    def test_midpoint_reset_retains_payload_and_reseeds_new_owner(self):
        result=m.simulate(256,reset_at=85,stale_payload=True)
        self.assertEqual(result['recovery_frames'],8)
        self.assertEqual(result['symbolic_lane_comparisons'],(6+8*16)*16)
        self.assertEqual(result['rdw_collisions'],0)

    def test_malformed_tag_numeric_read_inhibit_not_equivalence(self):
        result=m.malformed_seed_behavior()
        self.assertTrue(result['existing_write_owner_guard_passes'])
        self.assertTrue(result['collision'])
        self.assertNotEqual(result['old_FF_raw_current_term_E79'],result['sync_OLD_DATA_prefetch_E79'])
        self.assertFalse(result['numeric_read_inhibit_alone_equivalent'])


if __name__=='__main__':unittest.main()
