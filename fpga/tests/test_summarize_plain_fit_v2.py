"""Actual LAB rows and unavailable/duplicate/range controls, no native work."""
import importlib.util
from pathlib import Path
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('plain_summary2',FPGA/'tools/summarize_plain_fit_v2.py')
q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
ROOT = FPGA/'results/throughput-20260929'


class LabsTests(unittest.TestCase):
    def test_actual_probe_lab_counts_come_from_native_row(self):
        for name, pin, used, percent in (
            ('stream27-p8b-aw16-aws-plain-v1','3394cb7ffd28361826995090900612e67e3a3e931544b8592d31e97ad04a850b',8956,'21 %'),
            ('stream27-p16c-aw16-f16-plain-v1','73def9342052abb150e81f247959d6ee803b6223c0267b67771c97b13d3d52cf',16200,'38 %')):
            result = q.summarize(ROOT/name,pin); labs = result['resources']['labs']
            self.assertTrue(labs['available'])
            self.assertEqual(labs['partially_or_completely_used'],used)
            self.assertEqual(labs['device_total'],42720)
            self.assertEqual(labs['native_reported_occupancy_percent'],percent)
            self.assertFalse(result['whole_core_clock_claim'])

    def test_absent_row_not_inferred_from_alms(self):
        raw = '; ALMs used in final placement ; 123,764 ;\n'
        value = q.labs(raw)
        self.assertFalse(value['available'])
        self.assertIsNone(value['partially_or_completely_used'])

    def test_duplicate_or_impossible_usage_rejected(self):
        row = '; Total LABs: partially or completely used ; 16,200 / 42,720 ; 38 % ;\n'
        for bad in (row+row,row.replace('16,200','43,000'),row.replace('42,720','0')):
            with self.assertRaises(ValueError): q.labs(bad)


if __name__ == '__main__': unittest.main()
