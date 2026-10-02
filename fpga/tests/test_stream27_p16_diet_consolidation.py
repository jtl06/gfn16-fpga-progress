"""Metadata/scalar only, no native/HDL or numerical reference execution."""
import unittest
from unittest.mock import patch
from fpga.reference import stream27_p16_diet_consolidation as c


class P16Consolidation(unittest.TestCase):
    def test_own_sample_and_null_clock(self):
        d = c.sample_ledger()
        self.assertEqual(d['cold_primary_cycles'], 16172694192)
        self.assertEqual(d['cached_alternate_cycles'], 16172694093)
        self.assertEqual(d['cold_ordinary_completion'], 668025)
        self.assertEqual(d['warm_interval'], 8459)
        self.assertIsNone(d['selected_period_ns'])
        self.assertIsNone(d['projected_seconds'])
        self.assertEqual(d['canonical_and_copy_occurrences'], 1)

    def test_finite_and_special_calendars(self):
        g = dict(warm_interval=8459, carry_done=12557)
        for count, expected in ((1, 668025), (100, 1505466), (1000, 9118566)):
            with self.subTest(count=count):
                cold = c.source_cycles(65536, g, count)['host_done']
                self.assertEqual(cold, expected)
                self.assertEqual(cold-c.source_cycles(65536, g, count, True)['host_done'], 99)
                self.assertEqual(c.source_cycles(65536, g, count, False, True)['host_done']-cold, 65536)

    def test_no_p8_or_timing7_calendar_inheritance(self):
        self.assertNotEqual(c.source_cycles(65536, dict(warm_interval=16653, carry_done=24847), 1000)['host_done'], 9118566)
        self.assertEqual(c.source_cycles(65536, dict(warm_interval=8460, carry_done=12558), 1000)['host_done'], 9119566)
        self.assertEqual(c.PARAMETERS['P'], 16)
        self.assertNotIn('TERM_SELECT_TOKEN', c.PARAMETERS)

    def test_exact_snapshot_and_long_trace(self):
        d = c.consolidate()
        self.assertTrue(d['source_binding']['exact58_subset_of69'])
        self.assertEqual(d['direct_long_trace']['cold_completion_from_trace'], 668025)
        self.assertEqual(d['direct_long_trace']['accepted_pop_rows'], 999)
        self.assertEqual(d['direct_long_trace']['directly_observed_interval'], 8459)
        self.assertFalse(d['promotion_allowed'])
        self.assertIsNone(d['selected_passing_period_ns'])

    def test_changed_full_source_join_rejects(self):
        original = c.native
        def altered(job, root=c.ROOT):
            entry, manifest, report, rtl = original(job, root)
            if job == c.JOBS['thread8_continuous1000']:
                rtl[c.TOP] = '0'*64
            return entry, manifest, report, rtl
        with patch.object(c, 'native', altered), self.assertRaisesRegex(ValueError, 'FULL69_JOIN'):
            c.consolidate()

    def test_changed_long_probe_rejects(self):
        original = c.native
        def altered(job, root=c.ROOT):
            entry, manifest, report, rtl = original(job, root)
            if job == c.JOBS['thread8_continuous1000']:
                report['probe']['model_threads'] = 1
            return entry, manifest, report, rtl
        with patch.object(c, 'native', altered), self.assertRaisesRegex(ValueError, 'PROBE8'):
            c.consolidate()


if __name__ == '__main__':
    unittest.main()
