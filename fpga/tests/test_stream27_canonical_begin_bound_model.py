import unittest
from fpga.reference import stream27_canonical_begin_bound_model as model


class CanonicalBeginBoundModelTests(unittest.TestCase):
    def test_full_width_boundaries_and_random_identity(self):
        value=model.prove()
        self.assertEqual(value['random_full_width_cases'],200000)
        self.assertTrue(value['no_signed33_overflow'])
        for q in (-(1<<31),-1,0,1,(1<<31)-1):
            self.assertEqual(model.predicates(0,q),(True,True))
        self.assertEqual(model.predicates(1<<31,-(1<<31)),(True,True))

    def test_actual_R7_canonical_enable_source_anchors(self):
        value=model.source()
        self.assertEqual(value['bound_width'],33)
        self.assertTrue(value['no_default_or_frozen_source_changed'])


if __name__=='__main__':
    unittest.main()
