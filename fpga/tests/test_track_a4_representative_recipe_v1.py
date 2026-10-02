import unittest
from fpga.reference.track_a4_representative_recipe_v1 import geometry,materialize,small_cases
from fpga.reference.track_a4_core_vectors_v1 import canonical,integer


class RepresentativeRecipeTests(unittest.TestCase):
    def test_small_direct_integer(self):
        for aw in (5,8):
            n=1<<aw
            for base,initial,states in small_cases(aw):
                value=integer(initial,base)
                for double,words in zip((0,1,0,1),states):
                    value=(value*value*(1<<double))%(base**n+1)
                    self.assertEqual(words,canonical(value,base,n))

    def test_full_geometry_is_scalar_only(self):
        g=geometry(16)
        self.assertEqual((g['commands'],g['squares'],g['readbacks']),(786452,16,524288))
        self.assertEqual(g['minimum'],131077)
        self.assertEqual(len({r['index'] for r in g['identities']}),16)
        with self.assertRaises(ValueError):materialize(1,0,131077,65536)
        with self.assertRaises(ValueError):list(small_cases(16))


if __name__=='__main__':unittest.main()
