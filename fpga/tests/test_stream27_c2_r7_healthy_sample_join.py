import unittest
from fpga.reference import stream27_c2_r7_healthy_sample_join as own


class R7HealthyJoinTests(unittest.TestCase):
    def test_own_event_calendar_and_specials(self):
        for count,warm,done in ((2,[21221,25450],[680685,1340148]),
                               (100,[850203,854432],[1509667,2169130]),
                               (1000,[8463303,8467532],[9122767,9782230])):
            value = own.event_calendar(count)
            self.assertEqual(value['warm_edges'],warm)
            self.assertEqual(value['publication_edges'],done)
        self.assertEqual(own.event_calendar(1911814)['pair_completion_cycles'],16173357856)
        self.assertEqual(own.event_calendar(1911814,special=(True,True))['pair_completion_cycles'],
                         16173357856+131072)

    def test_actual_own55_index_native_wrap_join(self):
        value = own.close()
        self.assertEqual(len(value['native_references']),4)
        self.assertTrue(all('r7-' in row['id'] for row in value['native_references']))
        self.assertEqual(value['production']['sv_count'],55)
        self.assertEqual(value['sample']['pair_completion_cycles'],16173357856)
        self.assertTrue(value['mandatory_full_geometry_accelerated_wrap_native_pass'])
        self.assertIsNone(value['selected_period_ns'])
        self.assertIsNone(value['projected_pair_seconds'])
        self.assertFalse(value['promotion_allowed'])


if __name__ == '__main__':
    unittest.main()
