import unittest
from reference import stream27_canonical_fold_payload_model as model


class FoldPayloadModel(unittest.TestCase):
    def test_phase_payload_and_priority(self):
        proof=model.prove()
        self.assertGreater(proof['binary_integer_cases'],20000)
        self.assertTrue(proof['digit_before_internal_range_priority'])
        self.assertEqual(proof['new_external_edges'],0)
        self.assertTrue(proof['reset_stale_payload_ineligible'])

    def test_signed_extrema_are_not_narrowed(self):
        self.assertEqual(model.signed34((1<<33)-1),(1<<33)-1)
        self.assertEqual(model.signed34(1<<33),-(1<<33))
        self.assertEqual(model.process(model.fold(0,0,0),digit_bad=True,last=True,
            pass_index=2,all_zero=True,all_max=True,base=0)['code'],6)


if __name__=='__main__':unittest.main()
