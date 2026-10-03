import copy
import unittest
from fpga.reference import stream27_context_lean_r9_bind as own


class LeanR9Tests(unittest.TestCase):
    def test_default_off_exact_and_strict_parent(self):
        parent = own.capture(256)
        saved = copy.deepcopy(parent)
        self.assertEqual(own.bind(parent, enabled=0), saved)
        self.assertEqual(parent, saved)
        for flag in (True, False, 2, '1'):
            with self.assertRaisesRegex(ValueError, 'BOOLEAN_SWITCH'):
                own.bind(parent, enabled=flag)
        parent['parameters']['GEN_RETIRE'] = 1
        with self.assertRaisesRegex(ValueError, 'EXACT_R9_ONLY'):
            own.bind(parent, enabled=1)

    def test_reversible_leaf_delta_and_publication_literal(self):
        for n in (256, 65536):
            parent = own.capture(n)
            out = own.bind(parent, enabled=1)
            meta = out['lean_production']
            self.assertEqual(len(out['files']), 55)
            self.assertTrue(meta['r9_publication_proposal_and_drain_literal'])
            self.assertTrue(meta['r9_arithmetic_warm_error_barrier_literal'])
            self.assertTrue(meta['functional_generation_eligibility_retained'])
            self.assertEqual(out['geometry'], parent['geometry'])
            self.assertEqual(out['parameters'], dict(parent['parameters'], LEAN_PRODUCTION=1))
            for name, delta in meta['modified'].items():
                text = out['files'][name]
                for before, after in reversed(delta['edits']):
                    text = text.replace(after, before)
                self.assertEqual(text, parent['files'][delta['parent']])
            text = out['files'][out['top']+'.sv']
            self.assertIn('canon_error || lean_watchdog_error;', text)
            self.assertFalse(meta['host_gl_implemented'])
            self.assertFalse(meta['twin_fault_immunity_inherited'])
            canonical = out['files']['genefer_stream27_canonical_image_lean_r9_v1.sv']
            self.assertIn('base_ext=$signed({2\'b00,base_reg});two_base=base_ext<<<1;three_base=two_base+base_ext;', canonical)
            self.assertIn("else if(value>= -base_ext)begin fold_q=-3'sd1;remainder=value+base_ext;end", canonical)
            self.assertIn('next_all_max=all_max && remainder==base_ext-34\'sd1;', canonical)


if __name__ == '__main__':
    unittest.main()
