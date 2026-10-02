import unittest
from fpga.reference.stream27_warm_recurrence_v1 import prepare
from fpga.reference.stream27_warm_recurrence_native_v1 import compile_bench


class FiniteWarmSource(unittest.TestCase):
    def test_actual_feedback_geometry_not_external_reference(self):
        for n in (32,256):
            b=prepare(n);s=b['files'][b['top']+'.sv']
            self.assertIn('feedback_issue=digit_valid && need_feedback',s)
            self.assertIn('auto_correction=boundary_valid && carry_feedback_enabled',s)
            self.assertIn('permuted_digit[32*lane+:32]=digit_data[32*NATURAL+:32]',s)
            self.assertIn('square_count>32\'d32',s)
            self.assertIn('completed_frames+32\'d1==latched_count',s)
            if n==32:self.assertIn('fifo_valid[3]',s)
            else:self.assertIn('Direct next-edge accepted transfer',s)
            self.assertNotIn('reference',s)

    def test_native_driver_cold_only_and_checks_internal_events(self):
        s=compile_bench()
        self.assertIn('if(i==0&&tick>=f.start',s)
        self.assertIn('if(i==0&&tick==f.correction)',s)
        self.assertIn('d.internal_frame_accept',s)
        self.assertIn('d.internal_correction_accept',s)
        self.assertIn('S4_FINITE_DRAIN',s)
        self.assertIn('d.double_mask=kind==2?10u:0u',s)


if __name__=='__main__':unittest.main()
