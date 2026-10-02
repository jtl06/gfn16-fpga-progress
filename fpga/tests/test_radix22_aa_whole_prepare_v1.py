"""Pure role/closure checks, no native/HDL/vendor/full-N numerical work."""
import unittest
from fpga.reference import radix22_aa_whole_prepare_v1 as a


class AAWholePrepareTests(unittest.TestCase):
    def test_all_four_source_roles_and_exact_normal_oracle(self):
        for kind in ('block-aw5-f0','whole-aw5','whole-aw8','representative-aw16'):
            m,files=a.role(kind)
            self.assertIn(a.s.BLOCK,m['build']['sv_sources']);self.assertIn(a.s.field.RAM,m['build']['sv_sources'])
            self.assertNotIn('rtl/kernel/genefer_anext_point_block_engine_v1.sv',m['build']['sv_sources'])
            self.assertFalse(m['aa_whole']['whole_native_executed']);self.assertTrue(m['aa_whole']['no_F3_upper_cancel_merge'])
            if kind!='block-aw5-f0':
                aw={'whole-aw5':5,'whole-aw8':8,'representative-aw16':16}[kind]
                self.assertEqual(len(m['build']['sv_sources']),31)
                parent=a.ROOT/a.PARENTS[aw][0]/'source/fpga'
                if aw<16:self.assertEqual(files[f'vectors/anext-aw{aw}.txt'],(parent/f'vectors/anext-aw{aw}.txt').read_bytes())
                # Alias-only C++ expected/reverse checks occur in source.verify; no numerical oracle was regenerated.
                self.assertEqual(m['steps'][0]['expected_returncode'],0)
                self.assertEqual(m['probe']['expected_json'],dict(context_threads=1,model_threads=1,expected_threads=1))


if __name__=='__main__':unittest.main()
