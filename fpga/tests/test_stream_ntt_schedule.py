"""Pure Python arithmetic, literal token permutations and memory-port checks."""
import random
import unittest

from reference.stream_ntt_model import FIELDS, forward_dif, inverse_dit, bit_reverse, ModelMismatch
from reference.stream_ntt_schedule import (Token, adapter, commutator, transform,
                                         m20k, resource_and_interval, wrap2_recurrence)


class StreamScheduleTests(unittest.TestCase):
    def test_fig3_input_is_strided_not_contiguous(self):
        self.assertEqual([bit_reverse(l,2)*4 for l in range(4)], [0,8,4,12])
        result=transform(16,4,butterfly_edges=0)
        self.assertEqual(result['core_delay_words'], 12)
        self.assertEqual(result['fifo_first_output_latency'], 3)
        self.assertEqual([s['shuffle_depth_per_buffer'] for s in result['stages']], [0,0,2,1])
        self.assertEqual(result['output_indices'][0], [0,1,2,3])

    def test_literal_fig4_ABCD_shuffle(self):
        incoming=[[Token(i),Token(8+i)] for i in range(8)]
        output=commutator(incoming,0,2)
        self.assertEqual([[x.index for x in r] for r in output],
            [[0,2],[1,3],[8,10],[9,11],[4,6],[5,7],[12,14],[13,15]])

    def test_wrong_commutator_phase_typed_failure(self):
        with self.assertRaises(ModelMismatch) as raised:
            transform(64,8,wrong_shuffle_stage=3)
        self.assertIn(raised.exception.kind, ('commutator-valid','stage-token-order'))

    def test_forward_inverse_modular_arithmetic_matches_frozen_model(self):
        rng=random.Random(230930)
        for n in (16,32,64,256):
            for lanes in (2,4,8,16):
                for field,(prime,generator) in enumerate(FIELDS):
                    with self.subTest(n=n,p=lanes,field=field):
                        data=[rng.randrange(prime) for _ in range(n)]
                        omega=pow(generator,(prime-1)//n,prime)
                        expected=forward_dif(data,prime,omega)
                        forward=transform(n,lanes,values=data,field=field)
                        self.assertEqual(forward['output_values'],expected)
                        inverse=transform(n,lanes,inverse=True,values=expected,field=field)
                        self.assertEqual(inverse['output_values'],inverse_dit(expected,prime,omega))
                        self.assertEqual(inverse['output_values'],data)
                        self.assertEqual(inverse['core_delay_words'],n-lanes)

    def test_core_storage_latency_and_ports_p8_p16(self):
        for n in (32,256,4096):
            for p in (8,16):
                for inv in (False,True):
                    with self.subTest(n=n,p=p,inverse=inv):
                        r=transform(n,p,inverse=inv)
                        self.assertEqual(r['core_delay_words'],n-p)
                        self.assertEqual(r['fifo_first_output_latency'],n//p-1)
                        self.assertEqual(r['modeled_first_output_latency'],n//p-1+5*(n.bit_length()-1))
                        for stage in r['stages']:
                            self.assertEqual(stage['parallel_butterflies'],p//2)
                            self.assertLessEqual(stage['max_reads_per_fifo_per_tick'],1)
                            self.assertLessEqual(stage['max_writes_per_fifo_per_tick'],1)

    def test_three_frame_adapters_order_bank_ports_no_overwrite(self):
        for n in (32,256,4096):
            for p in (8,16):
                for incoming in (False,True):
                    with self.subTest(n=n,p=p,incoming=incoming):
                        r=adapter(n,p,to_strided=incoming)
                        self.assertEqual(r['first_output_latency_lower_bound'],(n-n//p)//p)
                        self.assertEqual(r['allocated_words_conservative'],2*n)
                        self.assertEqual(r['max_reads_per_bank_per_tick'],1)
                        self.assertEqual(r['max_writes_per_bank_per_tick'],1)
                        self.assertEqual(r['frames_checked'],3)

    def test_discrete_ram_geometry_not_bits_only(self):
        self.assertEqual(m20k(512,27),1)
        self.assertEqual(m20k(1024,27),2)
        self.assertEqual(m20k(8192,27),12)
        self.assertEqual(m20k(16384,27),24)
        self.assertEqual(m20k(4096,216),44)
        self.assertGreater(m20k(1,27),0)  # A shallow independent buffer is not fractional RAM.

    def test_N_equals_P_adapter_is_fixed_wire_not_colliding_RAM_banks(self):
        for p in (8,16):
            for incoming in (False,True):
                with self.subTest(p=p,incoming=incoming):
                    r=adapter(p,p,to_strided=incoming)
                    self.assertEqual(r['status'],'zero_memory_fixed_lane_bit_reversal')
                    self.assertEqual(r['allocated_words_conservative'],0)
                    self.assertEqual(r['first_output_latency_lower_bound'],0)
                    self.assertEqual(r['max_reads_per_bank_per_tick'],0)
                    self.assertEqual(r['lane_permutation'],[bit_reverse(i,p.bit_length()-1) for i in range(p)])
                    self.assertEqual([r['lane_permutation'][r['lane_permutation'][i]] for i in range(p)],list(range(p)))

    def test_resource_counts_no_free_twist_or_wrap_generator(self):
        r=resource_and_interval(256,8)
        costs=r['resources']; timing=r['timing']
        self.assertEqual(costs['mdc_butterfly_units_three_fields_two_pipes'],3*2*8*4)
        self.assertEqual(costs['mdf_sdf_alternative_butterfly_units_three_fields_two_pipes'],3*2*(5*8+3*4))
        self.assertEqual(costs['twist_square_untwist_modular_multipliers_three_fields'],72)
        self.assertEqual(costs['optional_wrap2_term_and_weight_recurrence_dsp_three_fields'],48)
        self.assertFalse(timing['complete_square_cycle_qualified'])
        self.assertTrue(timing['exact_carry_streaming_II_P_not_proved'])
        self.assertGreater(timing['wrap2_interval_scenario'],timing['ideal_two_frame_bound'])

    def test_bad_geometry_refused(self):
        for n,p in ((30,8),(32,3),(32,64),(32,True)):
            with self.subTest(n=n,p=p),self.assertRaises(ValueError): transform(n,p)

    def test_wrap2_four_context_recurrence_same_DSP_for_seeds_and_updates(self):
        for n in (32,256,4096):
            for p in (8,16):
                for field in range(3):
                    for c1 in (0,-131096,131096):
                        with self.subTest(n=n,p=p,field=field,c1=c1):
                            r=wrap2_recurrence(n,p,c1,field)
                            self.assertEqual(r['multipliers_per_field'],p)
                            self.assertEqual(r['total_multiplier_operations'],n)
                            self.assertEqual(r['seed_batches'],min(4,n//p))
                            self.assertEqual(r['conservative_initialization_barrier_ticks'],min(4,n//p)-1+3)

    def test_wrap2_step_and_feedback_negative_controls_typed(self):
        with self.assertRaises(ModelMismatch) as raised:
            wrap2_recurrence(256,8,7,wrong_step=True)
        self.assertEqual(raised.exception.kind,'wrap2-generator')
        with self.assertRaises(ModelMismatch) as raised:
            wrap2_recurrence(256,8,7,contexts=2)
        self.assertEqual(raised.exception.kind,'recurrence-feedback')


if __name__=='__main__': unittest.main()
