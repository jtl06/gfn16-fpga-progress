import hashlib
import unittest
from fpga.reference.track_a4_post_ntt_vectors_v1 import corpus
from fpga.reference.track_a4_blockcarry_model import arithmetic


class PostNttVectorsTests(unittest.TestCase):
    def test_crt_inputs_and_all_prefill_outputs(self):
        for aw in (5,8):
            text,meta=corpus(aw)
            rows=text.splitlines()[1:]
            n,t=1<<aw,(1<<aw)//16
            for case in range(0,len(rows),12):
                base,double,clocks,limit,reciprocal=rows[case].split()
                base,double=int(base),int(double)
                self.assertEqual(int(clocks),t+58)
                self.assertEqual(int(reciprocal,16),(1<<96)//base)
                residues=[list(map(int,rows[case+i].split())) for i in range(1,4)]
                coefficients=[arithmetic.core.centered_crt(x)*(1<<double) for x in zip(*residues)]
                self.assertLessEqual(max(map(abs,coefficients)),int(limit,16))
                state,_=arithmetic.proposal.carry_serial(coefficients,base,16)
                self.assertEqual(list(map(int,rows[case+4].split())),[v&((1<<33)-1) for v in state.effective()])
                for field,(p,_) in enumerate(arithmetic.core.FIELDS):
                    self.assertEqual(list(map(int,rows[case+5+field].split())),[v%p for v in state.effective()])
                self.assertEqual(list(map(int,rows[case+8].split())),[v&0xffffffff for v in state.c0])
                self.assertEqual(list(map(int,rows[case+9].split())),[v&0xffffffff for v in state.c1])
                self.assertEqual(list(map(int,rows[case+10].split())),[state.digits[k*t] for k in range(16)])
                self.assertEqual(list(map(int,rows[case+11].split())),[state.digits[k*t+1] for k in range(16)])
            self.assertEqual(meta['cases'],20)
            self.assertEqual(meta['sha256'],hashlib.sha256(text.encode()).hexdigest())

    def test_scope(self):
        with self.assertRaises(ValueError):corpus(16)


if __name__=='__main__':unittest.main()
