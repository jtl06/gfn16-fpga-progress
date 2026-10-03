"""Own R11 scalar/closed metadata tests; no HDL or full-N arithmetic."""
import copy
import json
import unittest
from fpga.reference import stream27_c2_r11_transport_healthy_join as own


class R11HealthyJoinTests(unittest.TestCase):
    def test_source_owned_service_and_equal_k_projection(self):
        b=own.source();g=b['geometry']
        self.assertEqual(g['warm_interval'],8463)
        self.assertEqual(g['carry_done'],12561)
        self.assertEqual(own.calendar(g,100)['publication_edges'],[1510068,2169532])
        self.assertEqual(own.calendar(g,1000)['full_read_completion_cycles'],9851768)
        sample=own.calendar(g,own.SAMPLE_K)
        self.assertEqual(sample['pair_completion_cycles'],16181005114)
        self.assertEqual(sample['full_read_completion_cycles']-sample['pair_completion_cycles'],65536)
        for mask,delta in [((True,False),65536),((False,True),65536),((True,True),131072)]:
            self.assertEqual(own.calendar(g,own.SAMPLE_K,mask)['pair_completion_cycles'],16181005114+delta)

    def test_closed_native2_metadata_not_parent_clock_credit(self):
        path=own.ROOT/'results/throughput-20260929/trackS-c2-transport11-ledger-v1/publication-ledger-native2-joined-v1.json'
        result=json.loads(path.read_bytes());g=own.source()['geometry']
        self.assertIsNone(result['selected_period_ns'])
        self.assertIsNone(result['projected_pair_seconds'])
        self.assertTrue(result['native1000_join_pending'])
        footer=result['native2']['measurements']
        self.assertEqual(own.validate_footer(footer,g)['publication_edges'],[680694,1340158])
        bad=copy.deepcopy(footer);bad['done_edges'][1]-=1
        with self.assertRaisesRegex(ValueError,'ACTUAL_EVENT_EDGES'):own.validate_footer(bad,g)
        bad=copy.deepcopy(footer);bad['launches'][1][0]-=1
        with self.assertRaisesRegex(ValueError,'EVERY_OWN_ACTUAL_LAUNCH'):own.validate_footer(bad,g)


if __name__=='__main__':unittest.main()
