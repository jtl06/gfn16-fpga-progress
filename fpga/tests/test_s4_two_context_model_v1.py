import unittest

from fpga.reference.s4_two_context_model_v1 import (
    fifo_replay, geometry, schedule, small_reference, source_guard,stopped_context_buffer,
    SmallImage,integer_digits,whole_integer)


class TwoContextNormal(unittest.TestCase):
    def test_source_and_actual_single_context_geometry(self):
        self.assertIn('reference/stream27_host_chain_param_v2.py',source_guard())
        for p,values in ((8,(8192,16653,16610,24801,16652,24847,36)),
                         (16,(4096,8459,8416,12511,8458,12557,42))):
            g=geometry(65536,p)
            self.assertEqual(tuple(g[k] for k in ('rows','warm_interval','sink_accept',
                'last_sink','first_digit','carry_done','correction_cache_latency')),values)

    def test_full_size_balanced_finite_resource_calendar(self):
        for p,gaps,cold_b_corr in ((8,[8326,8327],16467),(16,[4229,4230],8268)):
            r=schedule(65536,p,4)
            self.assertEqual(r['launch_gaps'],gaps)
            self.assertEqual((r['field_peak_leases'],r['whole_peak_leases']),(3,3))
            self.assertEqual(r['correction'][1]['accept'],cold_b_corr)
            self.assertTrue(all(x['margin']>=0 for x in r['correction']))
            self.assertEqual(r['resources']['extra_shadow_M20K_rectangle_proxy'],112)
            self.assertEqual(r['resources']['extra_shadow_M20K_512x32_proxy'],128)
            self.assertEqual(r['resources']['extra_context_shadow_image_bits'],2097152)
            self.assertEqual(r['resources']['extra_transform_data_FIFO_words'],0)
            self.assertFalse(r['full_N_numeric_NTT_performed'])
            self.assertFalse(r['resources']['ALM_DSP_M20K_delta_physically_qualified'])
            gain=r['finite_throughput_gain']
            self.assertLess(gain[0],2*gain[1])
            self.assertEqual(r['steady_model_throughput_gain'],2)

    def test_all_legal_geometries_finite_calendar(self):
        for aw in range(5,17):
            for p in (8,16):
                r=schedule(1<<aw,p,4)
                self.assertEqual(r['finite_total_operations'],8)
                self.assertLessEqual(max(r['feedback_peak_rows']),r['geometry']['feedback_fifo_rows'])

    def test_serialized_l1_correction_resource_hypothesis(self):
        # L1 owner supplies two-vector pool: P8 accepts a pair every34 edges;
        # P16 every60. Cache latency rises15/35, not an arbitrary inserted FF.
        for p,latency,pair_interval,cold_b,margin in ((8,51,34,16452,58),(16,77,60,8233,31)):
            r=schedule(65536,p,4,correction_latency=latency,correction_pair_interval=pair_interval)
            old=schedule(65536,p,4)
            self.assertEqual(r['correction'][1]['accept'],cold_b)
            self.assertEqual(min(x['margin'] for x in r['correction']),margin)
            self.assertEqual(r['finite_finish_exclusive'],old['finite_finish_exclusive'])
            self.assertEqual(r['launch_gaps'],old['launch_gaps'])
            self.assertEqual(r['correction_pair_min_interval'],pair_interval)

    def test_shared_canonical_needs_full_waiting_final_image(self):
        for p in (8,16):
            r=stopped_context_buffer(65536,p)
            self.assertEqual(r['peak_waiting_rows'],65536//p)
            self.assertEqual(r['required_bits'],32*65536)
            self.assertLess(r['last_row'],r['canonical_scratch_not_free_before'])

    def test_all_stage_tagged_fifo_order_and_root_row_restart(self):
        for n in (32,256):
            for p in (8,16):
                r=fifo_replay(n,p,4)
                self.assertEqual(r['checked_stage_tokens'],2*8*n*(n.bit_length()-1))
                self.assertEqual(r['transform_data_FIFO_extra_words'],0)
                self.assertTrue(all(s['resident_frames']<=2 for s in r['shuffle_residency']))

    def test_fifo_tail_overlaps_next_frame_without_extra_storage(self):
        for p in (8,16):
            for gap in (0,1,3):
                r=fifo_replay(256,p,4,transform_gap=gap)
                self.assertTrue(any(s['resident_frames']==2 for s in r['shuffle_residency']))
                self.assertTrue(all(s['peak_live_words']<=s['allocated_words'] for s in r['shuffle_residency']))

    def test_independent_signed_three_field_and_integer_references(self):
        for n in (32,256):
            for p in (8,16):
                r=small_reference(n,p,4)
                self.assertEqual(r['signed_canonical_words_checked'],8*n)
                self.assertEqual(r['three_field_schoolbook_coefficients_checked'],8*n)
                self.assertGreater(r['both_correction_terms_nonzero_cases'],0)
                self.assertNotEqual(*r['distinct_bases'])

    def test_exact_minus_one_publication_both_redundant_representations(self):
        for p in (8,16):
            n=32;base=1009
            for d,c0 in (((0,)*n,(-1,)+(0,)*(p-1)),
                         ((base-1,)*n,(1,)+(0,)*(p-1))):
                value=whole_integer(SmallImage(d,base,c0,(0,)*p))
                self.assertEqual(value,base**n)
                self.assertEqual(integer_digits(value,base,n),(-1,)+(0,)*(n-1))


if __name__=='__main__':unittest.main()
