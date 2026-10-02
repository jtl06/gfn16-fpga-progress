import unittest
from dataclasses import replace
from fpga.reference.stream27_field_square_warm_v3_compile import prepare,replay_small_overlap
from fpga.reference.stream27_field_square_oracle import image_cases,residues


class WarmFieldCompositionV3(unittest.TestCase):
    def test_true_two_owner_data_and_cache_seams(self):
        images=(image_cases()[9][1],image_cases()[3][1])
        for starts,corrections in (((0,20),(0,25)),((0,4),(0,4)),((0,4),(4,9))):
            result=replay_small_overlap(images,starts,corrections)
            self.assertEqual(result['output'],tuple(residues(image) for image in images))
            self.assertEqual(result['peak_owners'],2)
            self.assertEqual(result['sink_rows'],8)
            self.assertEqual(result['producer_products_remaining'],0)

    def test_real_warm_late_correction_and_owner_bank_reuse(self):
        images=tuple(replace(image,generation=0) for _,image in image_cases()[3:6])
        result=replay_small_overlap(images,(0,130,260),(0,135,265))
        self.assertEqual(result['output'],tuple(residues(image) for image in images))
        self.assertEqual(result['peak_owners'],1)
        self.assertFalse(result['full_N_numeric_NTT_performed'])

    def test_deadline_and_seed_capacity_are_fail_closed(self):
        images=(image_cases()[9][1],image_cases()[3][1])
        with self.assertRaisesRegex(ValueError,'SEED_CAPACITY'):
            replay_small_overlap(images,(0,4),(0,3))
        with self.assertRaisesRegex(AssertionError,'DEADLINE'):
            replay_small_overlap(images,(0,20),(7,25))

    def test_source_prospective_base_split_and_compound_correction_tags(self):
        p=prepare();s=p['files'][p['top']+'.sv']
        self.assertNotIn('frame_start && (!in_slot_valid || busy)',s)
        self.assertIn('wire raw_frame_begin=in_slot_valid && frame_start && !stop && !digit_admission_bad',s)
        self.assertNotIn('digit_admission_bad=admission_bad',s)
        self.assertIn('boundary_base=accepted_correction ? epoch_correction_base : high_base',s)
        self.assertIn('high_owner<={correction_epoch,correction_generation}',s)
        self.assertIn('term_table[addA_bank][addA_row]',s)
        self.assertIn('cache_epoch(term_generation[23:8])',s)
        self.assertEqual(s.count('.PAYLOAD_W(24)'),8)
        self.assertIn('#(.GEN_W(24)) correction_transform',s)
        self.assertEqual(p['epoch_RAM_bits_added'],0)
        self.assertFalse(p['full_N_arithmetic_ready'])


if __name__=='__main__':unittest.main()
