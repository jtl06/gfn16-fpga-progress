import unittest
from fpga.reference.stream27_r11_density_consumer_audit import audit


class Consumers(unittest.TestCase):
    def test_only_row_context_and_double_are_tail_consumers(self):
        result=audit()
        self.assertEqual(result['source_consumer_live_width'],14)
        self.assertEqual(result['unused_at_tail_owner_bits'],24)
        self.assertEqual(result['original_consumer_live_nominal_ff'],224)
        self.assertEqual(result['candidate_consumer_live_nominal_ff'],37)
        self.assertEqual(result['consumer_live_ff_reduction_upper_bound'],187)
        self.assertTrue(result['full_owner_origin_and_carry_authority_retained'])
        self.assertTrue(result['native_checks_full_word'])
        self.assertIsNone(result['whole_lab_saving'])


if __name__=='__main__':unittest.main()
