from itertools import product
import random
import unittest
from fpga.reference import stream27_montgomery_fused_model as s
from fpga.reference import lazy28_butterfly_v1 as old

class FusedMontgomeryBounds(unittest.TestCase):
    def test_all_fields_boundaries_random_forms_and_residues(self):
        for p in s.FIELDS:
            values=[0,1,p-1,p,p+1,2*p-1,(1<<27)-1,1<<27]
            for u,v,w,gs in product(values,values,(0,1,p-1,(1<<32)%p),(0,1)):
                y=s.butterfly(u,v,w,p,gs);reference=old.butterfly(u,v,w,p,gs)
                self.assertEqual(tuple(x%p for x in y),tuple(x%p for x in reference))
                sign=s.butterfly_sign(u,v,w,p,gs)
                self.assertEqual(tuple(x%p for x in sign),tuple(x%p for x in reference))
            rng=random.Random(0x5035+p)
            for _ in range(4096):
                u=rng.randrange(2*p);v=rng.randrange(2*p);w=rng.randrange(p);gs=rng.randrange(2)
                self.assertTrue(all(0<=x<2*p for x in s.butterfly(u,v,w,p,gs)))
                self.assertTrue(all(0<=x<2*p for x in s.butterfly_sign(u,v,w,p,gs)))
    def test_noncanonical_zero_is_deliberate_not_unqualified_leaf_binding(self):
        for p in s.FIELDS:
            self.assertEqual(s.butterfly(0,0,0,p,1),(0,p))
            self.assertEqual(old.butterfly(0,0,0,p,1),(0,0))
            if p==max(s.FIELDS):self.assertGreater(3*p,(1<<28)-1)
            self.assertLess(3*p,1<<29)
            for args in ((2*p,0,p),(0,p,p),(0,1,17)):
                with self.assertRaises(ValueError):s.raw_montgomery(*args)

if __name__=='__main__':unittest.main()
