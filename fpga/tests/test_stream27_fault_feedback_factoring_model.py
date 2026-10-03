import unittest

from fpga.reference import stream27_fault_feedback_factoring_model as model


class FaultFeedbackFactoringTests(unittest.TestCase):
    def test_known_boolean_and_full25_owner_equivalence(self):
        proof=model.prove()
        self.assertEqual(proof['boolean_owner_cases'],2048)
        self.assertEqual(proof['full25_tuple_cases'],100000)
        self.assertEqual(proof['protocol_absorption_cases'],32)
        self.assertFalse(proof['rtl_implemented'])

    def test_deliberate_generation_owner_and_valid_corruptions(self):
        upper=model.Tag(True,False,0x1fffffe)
        for bit in range(25):
            bad=model.Tag(True,False,upper.generation^(1<<bit))
            for phase in (False,True):
                lower,current=(upper,bad) if phase else (bad,upper)
                self.assertTrue(model.original(phase,upper,lower,current,0,False,upper.generation))
                self.assertTrue(model.compare_before_select(phase,upper,lower,current,0,False,upper.generation))
        for bad in (model.Tag(False,False,upper.generation),model.Tag(True,True,upper.generation)):
            self.assertTrue(model.compare_before_select(True,upper,upper,bad,0,False,upper.generation))

    def test_exact_frozen_source_anchors(self):
        value=model.source()
        self.assertEqual(value['production_files'],55)
        self.assertTrue(value['source_anchor_checks'])


if __name__=='__main__':
    unittest.main()
