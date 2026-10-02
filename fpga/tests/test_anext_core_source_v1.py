import random
import unittest
from fpga.reference import anext_core_source_v1 as source
from fpga.reference import anext_small_model_v1 as model
from fpga.reference import track_a4_blockcarry_model as carry


class Composite(unittest.TestCase):
    def test_exact_guarded_composition(self):
        self.assertEqual(len(source.verify()),4)
        seq=source.expected()['rtl/kernel/genefer_anext_ntt_sequencer_v1.sv']
        self.assertIn('rom_data[0]!=expected_header[0]',seq)
        self.assertNotIn('rom_data[0]>=P[0]',seq)
        self.assertIn('else if(step==2)',seq)
        self.assertIn('.block_external_conflict(1\'b0)',seq)
        self.assertNotIn('genefer_root_recurrence',seq)

    def test_small_chains_signed_schoolbook_and_whole_integer(self):
        rng=random.Random(202610011)
        for n in (32,256):
            for base in (carry.arithmetic.minimum_base(n,16),10**9):
                digits=[rng.randrange(base) for _ in range(n)]
                state=carry.arithmetic.load(digits,base,16)
                modulus=base**n+1;value=sum(d*base**i for i,d in enumerate(digits))
                for double in (0,1,1):
                    expected=carry.direct_square(state,double)
                    state,details=model.square(state,double)
                    self.assertEqual(details['coefficients'],expected)
                    value=value*value*(1<<double)%modulus
                    got=sum(d*base**i for i,d in enumerate(state.canonical()))%modulus
                    self.assertEqual(got,value)

    def test_signed_minus_one_and_numeric_limit(self):
        state=carry.arithmetic.load([-1]+[0]*31,300,16)
        for double in (0,1):
            result,_=model.square(state,double)
            self.assertEqual(result.canonical(),[1<<double]+[0]*31)
        class FullSize:
            digits=(0,)*65536
        with self.assertRaisesRegex(ValueError,'SMALL_NUMERIC_ONLY'):model.square(FullSize())


if __name__=='__main__':unittest.main()
