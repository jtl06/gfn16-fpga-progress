import unittest
from reference import stream27_c2_r9_healthy_sample_join as dut


class R9Healthy(unittest.TestCase):
    def test_own_calendar(self):
        ledger=dut.source_ledger()
        self.assertEqual(ledger['sample']['pair_completion_cycles'],16173357858)
        self.assertIsNone(ledger['selected_period_ns'])
        self.assertFalse(ledger['promotion_allowed'])
        self.assertEqual(ledger['calendars']['2']['publication_edges'],[680686,1340150])

    def test_specials_and_count_domain(self):
        original=dut.event_calendar(1911814)
        for mask in ((True,False),(False,True),(True,True)):
            changed=dut.event_calendar(1911814,special=mask)
            self.assertEqual(changed['pair_completion_cycles']-original['pair_completion_cycles'],sum(mask)*65536)
        with self.assertRaises(ValueError):dut.event_calendar(0)
        with self.assertRaises(ValueError):dut.event_calendar(0x100000000)
        with self.assertRaises(ValueError):dut.close(index_sha256=None)


if __name__=='__main__':unittest.main()
