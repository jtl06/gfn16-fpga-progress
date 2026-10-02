import unittest
from fpga.reference import anext_hostcut_fault_v1 as m
class Seams(unittest.TestCase):
    def test_source(self):
        for n,t in m.expected().items():self.assertEqual((m.ROOT/n).read_text(),t)
        t=m.expected()[m.CPP];self.assertIn('d.clk=0;d.eval();if(d.monitor_cancel)',t);self.assertIn('d.ntt_cycles==115',t)
    def test_contract(self):
        for c in m.CASES:
            reset=c.startswith('reset-');out=f'ANEXT_HOSTCUT_PASS case={c} injected=1 errors={int(not reset)} recovered=1 words=32 quiet=12 ticks=1600 cancel_samples={int(not reset)}\n'
            self.assertEqual(m.validate(out,'',0,{'case':c},{})['case'],c)
            with self.assertRaises(ValueError):m.validate(out+'extra\n','',0,{'case':c},{})
            if not reset:
                with self.assertRaises(ValueError):m.validate(out.replace('cancel_samples=1','cancel_samples=0'),'',0,{'case':c},{})
if __name__=='__main__':unittest.main()
