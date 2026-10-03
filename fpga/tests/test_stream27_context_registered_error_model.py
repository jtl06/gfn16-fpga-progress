import unittest
from fpga.reference import stream27_context_registered_error_model as model


class RegisteredErrorFenceTests(unittest.TestCase):
    def test_all_binary_predicate_and_fence_cases(self):
        p=model.prove()
        self.assertEqual(p['field_pending_to_registered_controller_cases'],512)
        self.assertEqual(p['sticky_two_edge_sequences'],256)
        self.assertEqual(p['publication_owner_reset_priority_cases'],128)
        self.assertEqual(p['global_report_max_added_edges'],1)
        self.assertEqual(p['healthy_equal_pair_extra_edges'],2)

    def test_full_owner_count_and_ack_fail_closed(self):
        for kwargs in (dict(owner_match=False),dict(counts_complete=False),dict(extra_ack=True)):
            _,publish,bad=model.publication_step(True,False,safe=True,**kwargs)
            self.assertFalse(publish)
            self.assertTrue(bad)
        self.assertEqual(model.publication_step(True,False,safe=True,reset=True),(False,False,False))


if __name__=='__main__':
    unittest.main()
