"""Own receipt/source/calendar metadata closure, without native arithmetic replay."""
from pathlib import Path
import unittest
from fpga.reference import stream27_c2_r12_feedback_healthy_join_v3 as join
from fpga.reference.stream27_context_storage_combo_oneshot_numerical_index import load,sha


class EvidenceMetadataTests(unittest.TestCase):
    def test_own_long_source_and_all_actual_launches_join(self):
        value=join.close()
        self.assertFalse(value['native1000_join_pending'])
        self.assertEqual(value['sample']['pair_completion_cycles'],16182916927)
        self.assertIsNone(value['selected_period_ns'])
        actual=value['native1000']['measurements']
        self.assertEqual(actual['launches'][0][0],204)
        self.assertEqual(actual['launches'][1][0],4436)
        self.assertEqual([len(v) for v in actual['launches']],[1000,1000])
        self.assertEqual(actual['done_edges'],[9127767,9787231])
        self.assertEqual(actual['joint_cycles'],9852767)

    def test_index_scope_retains_failed_unexecuted_queue_fixture(self):
        path=join.ROOT/'results/throughput-20260929/trackS-c2-feedback12-ownlong-v1/numerical-index-v1.json'
        value=load(path)
        self.assertEqual(len(value['jobs']),8)
        self.assertTrue(value['production']['lean_production'])
        self.assertFalse(value['queued_descriptor_fixture']['native_fault_execution_in_this_index'])
        self.assertFalse(value['queued_descriptor_fixture']['protection_pass_claim'])
        self.assertFalse(value['protected_mode']['execution_in_this_lean_index'])
        self.assertEqual(value['own_healthy_source_native_ledger']['sha256'],
            sha(Path(value['own_healthy_source_native_ledger']['path'])))


if __name__=='__main__':unittest.main()
