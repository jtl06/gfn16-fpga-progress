import unittest
from fpga.reference import stream27_host_chain_canonpipe_native_v1 as candidate


class FullCanonPipe(unittest.TestCase):
    def test_counts_and_closed_normal(self):
        c=candidate.counts()
        self.assertEqual(c['candidate_cycles'],1477102)
        self.assertEqual(c['canonical_cycles'],1179648)
        self.assertEqual(c['paired_reads'],131072)
        stdout='S4_CANON_PIPE_HOST_PASS aw=16 p=8 '+' '.join(f'{k}={v}' for k,v in c.items())+' t5b_wait_edges=272282\n'
        config=dict(aw=16,p=8,base=604832956,canonical_pipe_stages=1,mode='normal')
        self.assertEqual(candidate.validate(stdout,'',0,config,{})['status'],'PASS_expected_contracts')
        with self.assertRaises(ValueError):candidate.validate(stdout,'',0,{**config,'canonical_pipe_stages':0},{})

    def test_same_arithmetic_and_explicit_cost(self):
        m,files=candidate.role()
        self.assertEqual(len(m['steps']),1)
        self.assertEqual(m['build']['parameters']['CANONICAL_PIPE_STAGES'],1)
        self.assertIn(b'BASE=604832956',files[candidate.old.HEADER])
        self.assertIn(b'(special?10u:9u)',files[candidate.old.CPP])
        self.assertEqual(len(m['build']['sv_sources']),60)
        before=candidate.old.role()[1]
        changed=[name for name in before if name.endswith('.sv') and before[name]!=files.get(name)]
        self.assertEqual(len(changed),4)


if __name__=='__main__':unittest.main()
