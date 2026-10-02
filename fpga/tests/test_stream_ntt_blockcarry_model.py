import unittest
from unittest.mock import patch
from fpga.reference import stream_ntt_blockcarry_model as m

class BlockcarryEvaluationTests(unittest.TestCase):
    def test_explicit_range_and_evaluation_only(self):
        self.assertEqual(m.minimum_base(32,8),172)
        with self.assertRaises(ValueError):m.proof(32,8,171)
        p=m.proof(65536,16,10**9)
        self.assertFalse(p['adopted_profile']);self.assertTrue(p['evaluation_authorized'])
        self.assertEqual(p['doubled_coefficient_bound'],131168016564584965062752)

    def test_optimized_twists_match_frozen_proposal(self):
        for n,lanes,b in ((32,8,172),(256,8,517),(256,16,10**9)):
            state=m.load([b-1]*n,b,lanes)
            for bit in (1,0,1):
                expected=m.proposal.square_coefficients(state,bit)
                self.assertEqual(m.square_coefficients(state,bit),expected)
                state,_=m.proposal.carry_split(expected,b,lanes)

    def test_repeated_chains_against_whole_integer(self):
        for b in (172,604832956,10**9):
            n=32;state=m.load([b-1]*n,b,8);modulus=b**n+1
            value=m.core._pack(state.digits,b)%modulus
            for bit in (1,1,0,1,0):
                a=m.square_coefficients(state,bit)
                state,stats=m.proposal.carry_split(a,b,8)
                serial,ends=m.proposal.carry_serial(a,b,8)
                self.assertEqual(state,serial);self.assertEqual(stats['block_carries'],ends)
                value=value*value*(1<<bit)%modulus
                self.assertEqual(m.core._pack(state.canonical(),b)%modulus,value)

    def test_minusone_and_signed_input_load(self):
        for digits in ([-1]+[0]*31,[-1,7,-1]+[0]*29):
            state=m.load(digits,1000,8)
            self.assertEqual(state.canonical(),m.core.canonicalize(digits,1000))
        with self.assertRaises(ValueError):m.load([-2]+[0]*31,1000,8)

    def test_full_transform_cannot_accidentally_run_off_aethia(self):
        state=m.load([0]*65536,10**9,8)
        with patch.object(m.socket,'gethostname',return_value='local-mac'):
            with self.assertRaisesRegex(RuntimeError,'aethia'):m.square_coefficients(state)

if __name__=='__main__':unittest.main()
