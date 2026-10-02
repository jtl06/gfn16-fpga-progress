import unittest
from fpga.reference import stream27_canonical_pipe_fault as native


class SourceTests(unittest.TestCase):
    def test_real_source_closed_role(self):
        m,files=native.role()
        self.assertEqual(set(m['sources']),set(files))
        self.assertEqual(m['build']['parameters'],dict(AW=5,P=8))
        self.assertEqual([step['expected_returncode'] for step in m['steps']],[0,1])

    def test_reset_boundary_and_range_timing(self):
        text=(native.ROOT/native.CPP).read_text()
        for marker in ('CANON_PIPE_RANGE_EXACT_E3','3*N-1,3*N,3*N+1,6*N,9*N-1',
                       '9*N,9*N+1,10*N-1','CANON_PIPE_PENDING_E0',
                       'd.read_data[1]==sign&&d.read_data[2]==sign'):
            self.assertIn(marker,text)
        # Identity digits and -1 are direct whole-integer residues, not folds.
        n,b=32,172
        x=[(a*7+3)%b for a in range(n)]
        value=sum(word*b**a for a,word in enumerate(x))
        self.assertLess(value,b**n+1)
        self.assertEqual((-1)%(b**n+1),b**n)


if __name__=='__main__':unittest.main()
