import random
import unittest
from fpga.reference import stream27_l3_factored_model_v1 as s
class FactoredMontgomery(unittest.TestCase):
    def test_legal_boundary_random_and_montgomery_domains(self):
        for p in s.FIELDS:
            inv=pow(1<<32,-1,p);r=(1<<32)%p;rng=random.Random(0x4c330001+p)
            edges=[0,1,p-1,p,p+1,(1<<27)-1,1<<27,2*p-1]
            for a in edges:
                for b in (0,1,p-1,r):
                    self.assertEqual(s.multiply(a,b,p,lazy=True),a*b*inv%p)
            for _ in range(4096):
                a=rng.randrange(2*p);b=rng.randrange(p)
                self.assertEqual(s.multiply(a,b,p,lazy=True),a*b*inv%p)
                self.assertEqual(s.multiply(a%p,b,p),a*b*inv%p)
            for a,b in ((0,0),(1,p-1),(p-1,p-1),(12345,67890)):
                self.assertEqual(s.multiply(a*r%p,b*r%p,p),a*b*r%p)
                self.assertEqual(s.multiply(a,b*r%p,p),a*b%p)
                self.assertEqual(s.multiply(a*inv%p,b*r*r%p,p),a*b%p)
    def test_source_one_variable_product_and_width_ledger(self):
        text=(s.ROOT/s.RTL).read_text()
        self.assertEqual(text.count('lhs[26:0]*rhs'),1)
        self.assertIn('low_term[LB-1:D]',text);self.assertIn('carry_s2<=lo[31:K]<m_high;',text)
        l=s.ledger();self.assertEqual(l['latency'],3);self.assertEqual(l['additional_DSP_by_source'],0)
        self.assertEqual([r['quotient_low_product_bits'] for r in l['fields'].values()],[15,17,25])
if __name__=='__main__':unittest.main()
