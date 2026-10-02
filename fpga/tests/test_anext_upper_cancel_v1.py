import unittest
from fpga.reference import anext_upper_cancel_v1 as m
class UpperCancel(unittest.TestCase):
    def test_exact_new_monitor_and_harness(self):
        for path,text in m.expected().items():self.assertEqual((m.ROOT/path).read_text(),text)
        self.assertIn('butterfly.upper_launch_valid',m.expected()[m.SV])
        self.assertNotIn('arithmetic[0].point_launch_valid',m.expected()[m.SV])
    def test_exact_output(self):
        for case in m.CASES:
            out=f'ANEXT_UPPER_CANCEL_PASS case={case} fields=3 captured=1 quiet=16 recovered=32 ntt=115 ticks=1234\n'
            self.assertEqual(m.validate(out,'',0,{'case':case},{})['case'],case)
            for bad in (out.replace('UPPER','POINT'),out.replace('captured=1','captured=0'),out.replace('ntt=115','ntt=116'),out+'extra\n'):
                with self.assertRaises(ValueError):m.validate(bad,'',0,{'case':case},{})
if __name__=='__main__':unittest.main()
