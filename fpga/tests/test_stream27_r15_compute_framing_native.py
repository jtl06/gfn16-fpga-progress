import unittest
from fpga.reference import stream27_r15_compute_framing_native as p


class Framing(unittest.TestCase):
    def test_public_input_fixture_separate_graphs(self):
        for branch in p.CAPTURES:
            m,f,b,id=p.role(branch,True)
            self.assertEqual(len(m['build']['sv_sources']),60)
            self.assertEqual(m['build']['parameters']['LEAN_BUILD'],int(branch=='lean'))
            self.assertEqual(len(m['steps']),2)
            self.assertEqual(m['steps'][1]['expected_returncode'],1)
            cpp=f[p.CPP].decode()
            self.assertIn('d.command_generation=2',cpp)
            self.assertIn('R15_FRAMING_REQUIRED_TOKEN_TYPED_UNDERFLOW',cpp)
            self.assertNotIn('rootp()',cpp)
            self.assertFalse(m['r15_framing']['private_canceled_tail_flush_claim'])


if __name__=='__main__':unittest.main()
