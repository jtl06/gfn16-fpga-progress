"""Symbolic full-N root delivery and bounded negative/source gates only."""
import unittest

from fpga.reference import radix22_root_local_model_v1 as local


class RootLocal(unittest.TestCase):
    def test_frozen_reuse_and_no_hidden_R1_credit(self):
        self.assertEqual(local.source_guard()['reference/radix22_track_a_model_v1.py'], local.MODEL_PIN)
        result = local.resources()
        self.assertEqual(result['ALMs_needed_proxy'], 316712.9)
        self.assertEqual(result['DSP_needed_proxy'], 930)
        self.assertEqual(result['M20K_legal_rectangle_proxy'], 1353)
        self.assertTrue(result['conditional_area_gate_passed'])
        self.assertFalse(result['architectural_RTL_GO'])
        self.assertFalse(result['measured'])

    def test_full_N_exact_local_root_exponents_both_directions(self):
        result = local.symbolic_gate()
        self.assertEqual(result['delivered_exponents_checked'], 786432)
        self.assertFalse(result['numeric_root_values_generated'])

    def test_small_even_AW_root_layouts(self):
        for n in (4, 16, 64, 256):
            partition = tuple((h,) for h in range(1, n.bit_length()-1, 2))
            self.assertEqual(local.symbolic_gate(partition, n=n)['status'], 'PASS_symbolic_root_local_delivery')

    def test_copy_and_inverse_mutants_rejected(self):
        for mutant in ('wrong-copy', 'wrong-direction-address'):
            with self.assertRaisesRegex(ValueError, 'exact exponent'):
                local.symbolic_gate(mutant=mutant)

    def test_memory_vs_pass_route_frontier(self):
        f = local.partition_frontier()
        self.assertEqual(f['partitions_evaluated'], 128)
        self.assertEqual(f['cheapest_M20K_conditional']['partition'], [list(s) for s in local.DEFAULT])
        self.assertEqual(f['cheapest_M20K_conditional']['M20K_legal_rectangle_proxy'], 1353)
        all_in_one = local.resources((tuple(range(1,16,2)),))
        self.assertEqual(all_in_one['M20K_legal_rectangle_proxy'], 2331)
        self.assertFalse(all_in_one['conditional_area_gate_passed'])

    def test_no_free_split_pair_schedule_overhead(self):
        h = local.hybrid_calendar()
        self.assertEqual(h['extra_cycles_per_square'], 1030)
        self.assertEqual(h['ntt_cycles'], 10499)
        self.assertEqual(h['A4_warm_conditional'], 14661)
        self.assertIsNone(h['physical_frequency'])

    def test_malformed_partition_request_rejected(self):
        for bad in (((1,), (5, 3, 7, 9, 11, 13, 15)), ((1,3), (5,7)), ((), tuple(range(1,16,2)))):
            with self.assertRaisesRegex(ValueError, 'partition'):
                local.layout(bad)
        with self.assertRaisesRegex(ValueError, 'types'):
            local.request(local.layout(), 1, 0, 1, 0)
        with self.assertRaisesRegex(ValueError, 'beat'):
            local.request(local.layout(), 1, 512, False, 0)


if __name__ == '__main__':
    unittest.main()
