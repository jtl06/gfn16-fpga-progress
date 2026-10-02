import unittest
from fpga.reference import stream27_warm_contexts as core


class SourceTests(unittest.TestCase):
    def test_shared_feedback_and_context_ordinal(self):
        for n, p in ((32, 8), (256, 8), (32, 16), (256, 16)):
            b = core.prepare(n, p)
            s = b['files'][b['top'] + '.sv']
            self.assertIn('digit_data[32*NATURAL+:32]', s)
            self.assertIn('digit_epoch+16\'d1,digit_generation', s)
            self.assertIn('.c0_in(auto_correction ? next_c0 : c0_in)', s)
            self.assertIn('command_index[feedback_context*32+:32]!=launched[feedback_context]', s)
            self.assertIn('result_sequence[0:1]', s)
            self.assertIn('digit_sequence==latched_count[digit_context]-32\'d1', s)
            self.assertIn('final_load_owner={digit_sequence,digit_epoch,digit_generation}', s)
            self.assertIn('warm_done[done_context]<=1', s)
            self.assertNotIn('canonical_ready', s)
            self.assertEqual(len([name for name in b['files'] if name.startswith('genefer_stream27_shared_warm_')]), 3)

    def test_full_count_feed_and_no_fabricated_head(self):
        s = core.prepare(32, 8)['files']['genefer_stream27_warm_contexts_aw5_p8_v1.sv']
        self.assertIn('(!feed_mode && square_count>32\'d32)', s)
        self.assertIn('!command_valid[feedback_context]', s)
        self.assertIn('wire child_slot=(cold_slot || feedback_slot) && !command_bad', s)
        self.assertIn('latched_count[0:1]', s)
        self.assertIn('warm_cancelled<=2\'b11', s)


if __name__ == '__main__':
    unittest.main()
