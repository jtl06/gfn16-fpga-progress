import unittest
from fpga.reference import anext_writeback_cancel_v1 as m
class Cancel(unittest.TestCase):
    def test_source_and_output(self):
        for n,t in m.expected().items():self.assertEqual((m.ROOT/n).read_text(),t)
        self.assertIn('memories[b].ram_write_en',m.expected()[m.SV])
        self.assertNotIn('engine.data_we',m.expected()[m.SV])
        for c in m.CASES:
            out=f'ANEXT_WRITEBACK_CANCEL_PASS case={c} fields=3 captured=1 quiet=16 recovered=32 ntt=126 ticks=1200\n'
            self.assertEqual(m.validate(out,'',0,{'case':c},{})['case'],c)
            for bad in (out.replace('quiet=16','quiet=15'),out.replace('ntt=126','ntt=115'),out+'extra\n'):
                with self.assertRaises(ValueError):m.validate(bad,'',0,{'case':c},{})
if __name__=='__main__':unittest.main()
