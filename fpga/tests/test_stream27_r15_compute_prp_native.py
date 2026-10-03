import unittest
from fpga.reference import stream27_r15_compute_prp_native as p


class PRP(unittest.TestCase):
    def test_own_two_graph_headers_and_frozen_oracle(self):
        for branch in p.CAPTURES:
            m,f,b,id=p.role(branch)
            self.assertEqual(m['build']['parameters']['LEAN_BUILD'],int(branch=='lean'))
            self.assertEqual(len(m['build']['sv_sources']),60)
            self.assertEqual(p.sha(f[p.CPP]),p.CPP_PIN)
            self.assertEqual(p.sha(f[p.ASSET]),p.ORACLE_PIN)
            self.assertIn('INTERVAL=215,CARRY_DONE=214',f[p.HEADER].decode())
            self.assertIn(p.LABELS[branch],f[p.HEADER].decode())
            self.assertEqual(m['steps'][0]['validator']['config'],p.config(branch))


if __name__=='__main__':unittest.main()
