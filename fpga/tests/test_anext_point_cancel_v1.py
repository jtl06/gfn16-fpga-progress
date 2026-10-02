import unittest
from fpga.reference import anext_point_cancel_v1 as m
class Cancel(unittest.TestCase):
    def test_source_delta(self):
        self.assertEqual((m.ROOT/m.SV).read_text(),m.expected())
        self.assertIn('.cancel(square_cancel || sim_cancel)',m.expected())
        self.assertIn('engine.arithmetic[0].point_launch_valid',m.expected())
    def test_exact_finite_outputs(self):
        for case in m.CASES:
            out=f'ANEXT_POINT_CANCEL_PASS case={case} fields=3 captured=1 quiet=16 recovered=32 ntt=115 ticks=1200\n'
            self.assertEqual(m.validate(out,'',0,{'case':case},{})['case'],case)
            for bad in (out.replace('fields=3','fields=1'),out.replace('quiet=16','quiet=0'),out.replace('ntt=115','ntt=114'),out+'extra\n'):
                with self.assertRaises(ValueError):m.validate(bad,'',0,{'case':case},{})
            with self.assertRaises(ValueError):m.validate(out,'',False,{'case':case},{})
if __name__=='__main__':unittest.main()
