"""Complete tiny-field source/domain checks; no HDL/native dispatch."""
import unittest

from fpga.reference.stream27_field_square_compile import prepare,evaluate_small_image
from fpga.reference.stream27_field_square_oracle import image_cases,residues


class TinyCompleteFieldSource(unittest.TestCase):
    def test_full_effective_image_square_all_independent_cases(self):
        for label,image in image_cases():
            self.assertEqual(evaluate_small_image(image),residues(image),label)

    def test_all_three_arithmetic_negative_controls_are_observable(self):
        for mutation in ('wrong_final_domain','missing_c0','missing_c1'):
            changed=sum(evaluate_small_image(image,mutation)!=residues(image)
                        for label,image in image_cases())
            self.assertGreater(changed,0,mutation)

    def test_source_closure_physical_canceled_rows_and_root_files(self):
        bundle=prepare();source=bundle['files'][bundle['top']+'.sv']
        self.assertTrue(bundle['tiny_complete_field_source'])
        self.assertFalse(bundle['full_N_ready'] or bundle['native_run_performed'])
        self.assertEqual(bundle['first_physical_output'],87)
        self.assertEqual(bundle['first_terminal_commit'],88)
        self.assertIn('c1_pending ||',source.replace('accepted_start || c1_pending','c1_pending || accepted_start'))
        self.assertIn('high_correction<=c1_in',source)
        self.assertIn('commit_generation<=generation_out',source)
        self.assertIn('generation_out==live_generation',source)
        self.assertIn('.in_slot_valid(addB_slot)',source)
        self.assertNotIn('.in_slot_valid(out_eligible)',source)
        self.assertEqual(sum(len(text.splitlines()) for name,text in bundle['files'].items()
                             if name.endswith('.hex')),150)
        self.assertEqual(len(bundle['mutations']),3)
        self.assertTrue(all(path in bundle['source_dependencies'] or path in bundle['files']
                            for path in bundle['rtl_sources']))


if __name__=='__main__':
    unittest.main()
