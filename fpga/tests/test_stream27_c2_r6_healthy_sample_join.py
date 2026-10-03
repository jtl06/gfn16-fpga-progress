import copy
import unittest

from fpga.reference import stream27_c2_r6_healthy_sample_join as join


class HealthyR6SampleJoinTests(unittest.TestCase):
    def test_own_finite_and_sample_arithmetic(self):
        expected = {2:([21221,25450],[680685,1340148],1405684),
                    100:([850203,854432],[1509667,2169130],2234666),
                    1000:([8463303,8467532],[9122767,9782230],9847766)}
        for count,(warm,done,joint) in expected.items():
            value=join.event_calendar(count)
            self.assertEqual(value['warm_edges'],warm)
            self.assertEqual(value['publication_edges'],done)
            self.assertEqual(value['pair_completion_cycles']+65536,joint)
        value=join.event_calendar(1911814)
        self.assertEqual(value['pair_completion_cycles'],16173357856)
        self.assertEqual(join.event_calendar(1911814,special=(True,True))['pair_completion_cycles'],
                         16173357856+2*65536)
        self.assertNotIn('period_ns',value)

    def test_wrong_accepted_calendar_is_rejected(self):
        value=join.event_calendar(2)
        footer=dict(interval=8459,warm_edges=value['warm_edges'],done_edges=value['publication_edges'],
            joint_cycles=value['pair_completion_cycles']+65536,setup_edges=[99,199],
            bases=[604832956,999999937],signed96=True,independent_reference=True,
            launches=[[204,8663],[4433,12892]],context_alone_bit_identical=True,
            squares=8,reads=393216,peer_live_reads=65536)
        join.validate_footer(footer,2)
        bad=copy.deepcopy(footer);bad['launches'][1][1]+=1
        with self.assertRaisesRegex(ValueError,'EVERY_NATIVE_ACCEPTED_LAUNCH'):
            join.validate_footer(bad,2)
        bad=copy.deepcopy(footer);bad['done_edges'][0]+=1
        with self.assertRaisesRegex(ValueError,'NATIVE_CALENDAR_REFERENCE'):
            join.validate_footer(bad,2)

    def test_actual_own_source_native_join_has_no_clock_or_promotion(self):
        value=join.close()
        self.assertEqual(value['production']['sv_count'],55)
        self.assertEqual(len(value['native_references']),4)
        self.assertEqual(value['native_calendars']['2']['native_total_squares'],8)
        self.assertEqual(value['aw8_reset_newjob_reference']['id'],join.AW8_WRAP_ID)
        self.assertEqual(value['sample']['pair_completion_cycles'],16173357856)
        self.assertTrue(value['mandatory_full_geometry_accelerated_wrap_native_pass'])
        self.assertIsNone(value['selected_period_ns'])
        self.assertIsNone(value['projected_pair_seconds'])
        self.assertFalse(value['promotion_allowed'])


if __name__ == '__main__':
    unittest.main()
