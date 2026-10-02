from pathlib import Path
import unittest
from fpga.tools.run_rootpipe_host_fault import mutation, expected_rejection


class HostQuarterFault(unittest.TestCase):
    def test_exact_delta(self):
        path=Path(__file__).resolve().parents[1]/'rtl/kernel/genefer_ntt_banked27_host_rootpipe_engine.sv'
        original=path.read_text();changed=mutation(original)
        before,after=original.split('read_group<=host_group;')
        self.assertEqual(changed,before+'read_group<=0;'+after)
        self.assertEqual(changed.count('read_group<=0;'),original.count('read_group<=0;')+1)
        self.assertEqual(changed,original.replace('read_group<=host_group;','read_group<=0;'))
        self.assertEqual(original.count('read_group<=host_group;'),1)

    def test_ambiguous_or_absent_anchor(self):
        for source in ('', 'read_group<=host_group;'*2):
            with self.assertRaises(RuntimeError):mutation(source)

    def test_only_semantic_rejection(self):
        diagnostic='[0] %Fatal: genefer_square_core27_stream_rootpipe.sv:288: Assertion failed in TOP.genefer_square_core27_stream_rootpipe.unnamedblk3: residue mask skew'
        for code in (1,-6,134):self.assertTrue(expected_rejection(code,diagnostic))
        for code in (0,-9,137,-11):self.assertFalse(expected_rejection(code,diagnostic))
        self.assertFalse(expected_rejection(1,'timeout'))
        self.assertFalse(expected_rejection(-6,diagnostic+'\nPASS n=128'))
        for output in ('Error: residue mask skew',
                       "launcher failed before simulation; expected check would be 'residue mask skew'",
                       diagnostic.replace(':288:',':287:'),
                       diagnostic.replace('TOP.genefer','TOP.unrelated'),
                       diagnostic+'\n'+diagnostic):
            self.assertFalse(expected_rejection(1,output))


if __name__=='__main__':unittest.main()
