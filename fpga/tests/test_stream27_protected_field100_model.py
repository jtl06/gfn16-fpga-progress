import unittest
from reference import stream27_protected_field100_model as candidate


class ProtectedField100Model(unittest.TestCase):
    def test_accepted_fault_is_not_revoked_by_stop(self):
        proof=candidate.prove_fields()
        self.assertEqual(proof['inductive_binary_cases'],2048)
        self.assertTrue(proof['report_never_rechecks_stop'])
        self.assertTrue(proof['next_stop_regating_negative_control_detected'])
        self.assertFalse(proof['arbitrary_inconsistent_copy_or_XZ_claim'])

    def test_fast_origin_mask_not_delayed_report(self):
        proof=candidate.prove_publication()
        self.assertEqual(proof['origin_publication_read_mask_cases'],32)
        self.assertEqual(proof['healthy_data_owner_calendar_edges_added'],0)
        self.assertFalse(candidate.SOURCE_READY)

    def test_protocol_sticky_is_the_same_accepted_origin(self):
        proof=candidate.prove_protocol_origin()
        self.assertEqual(proof['binary_origin_cases'],288)
        self.assertTrue(proof['field_controller_equals_protocol_sticky_by_induction'])
        self.assertFalse(proof['source_transform_ready'])

    def test_complete_fast_and_report_chain(self):
        proof=candidate.prove_report_chain()
        self.assertEqual(proof['public_FAST_origin_lag'],0)
        self.assertEqual(proof['field_report_origin_lag'],1)
        self.assertEqual(proof['arithmetic_report_origin_lag'],2)
        self.assertEqual(proof['host_report_origin_lag'],1)

    def test_private_quarantine_is_not_public_authority(self):
        proof=candidate.prove_private_quarantine()
        self.assertEqual(proof['new_healthy_edges'],0)
        self.assertTrue(proof['public_FAST_gate_required'])
        self.assertFalse(proof['numeric_pipeline_flush_within_one_edge_claim'])


if __name__=='__main__':unittest.main()
