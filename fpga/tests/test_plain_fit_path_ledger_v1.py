"""Actual retained-report/tamper controls; no native tool or host actions."""
import sys
from pathlib import Path
import unittest

FPGA = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(FPGA/'tools'))
import plain_fit_path_ledger_v1 as ledger


class LedgerTests(unittest.TestCase):
    def text(self,name):
        return (FPGA/'results/throughput-20260929'/name/'project/output_files/probe.sta.rpt').read_text()

    def test_actual_a4b_control_feedback_not_endpoint_only(self):
        result = ledger.parse(self.text('track-a4b-aw16-aws-plain-v1'),'setup',10)
        self.assertEqual(result['endpoint_family_counts'],{'host digit-image RAM -> host digit-image RAM':10})
        first = result['paths'][0]
        self.assertEqual(first['slack_ns'],-.957)
        self.assertEqual(first['native_data_statistics']['IC']['total_delay_ns'],5.450)
        self.assertEqual(first['native_data_statistics']['Cell']['total_delay_ns'],2.831)
        self.assertEqual(first['native_data_statistics']['uTco']['total_delay_ns'],2.384)
        self.assertIn('cold-prefill admission/legality/fault',first['observed_data_cone_families'])
        self.assertTrue(any(value['element'].endswith('|ena1') for value in first['observed_data_cone']))

    def test_actual_a10_ram_normalizer_and_native_dsp_setup(self):
        result = ledger.parse(self.text('a10-aw16-registered-aws-plain-v1'),'setup',8)
        self.assertEqual(result['endpoint_family_counts'],{'NTT data RAM -> butterfly normalizer':10})
        self.assertEqual(result['paths'][0]['native_data_statistics']['IC']['total_delay_ns'],4.226)
        self.assertEqual(result['paths'][0]['native_required_constraints'][0]['incremental_ns'],-2.770)

    def test_actual_hold_missing_native_ic_row_not_inferred(self):
        result = ledger.parse(self.text('track-a4b-aw16-aws-plain-v1'),'hold',10)
        self.assertEqual(result['paths'][0]['slack_ns'],.014)
        self.assertIsNone(result['paths'][0]['native_data_statistics']['IC'])

    def test_wrong_snapshot_count_period_and_detail_refused(self):
        text = self.text('a10-aw16-registered-aws-plain-v1')
        for bad in (text.replace('    final','    placed',1),text.replace('Found 10 setup paths','Found 9 setup paths',1),
                    text.replace('Path #1: Setup slack is -3.706','Path #1: Setup slack is -3.705')):
            with self.assertRaises(ValueError): ledger.parse(bad,'setup',8)
        with self.assertRaises(ValueError): ledger.parse(text,'setup',9.5)


if __name__ == '__main__': unittest.main()
