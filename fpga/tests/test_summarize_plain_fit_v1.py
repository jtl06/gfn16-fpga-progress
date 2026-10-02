"""Actual collected probes and semantic tamper controls; no native rerun."""
import importlib.util
from pathlib import Path
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('plain_summary', FPGA/'tools/summarize_plain_fit_v1.py')
q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
P8 = FPGA/'results/throughput-20260929/stream27-p8b-aw16-aws-plain-v1'
P16 = FPGA/'results/throughput-20260929/stream27-p16c-aw16-f16-plain-v1'
PINS = {P8:'3394cb7ffd28361826995090900612e67e3a3e931544b8592d31e97ad04a850b',
        P16:'73def9342052abb150e81f247959d6ee803b6223c0267b67771c97b13d3d52cf'}


class ActualTests(unittest.TestCase):
    def test_actual_native_resource_counts_and_scoped_clock(self):
        for root, counts, slacks in ((P8,(54089,71848,523,140),(.691,.017)),
            (P16,(99094,123764,548,280),(.953,.016))):
            with self.subTest(root=root.name):
                result = q.summarize(root,PINS[root])
                resource = result['resources']; timing = result['timing']
                self.assertEqual(tuple(resource[name] for name in ('alms_needed','alms_placed','m20k','dsp_placed')), counts)
                self.assertEqual((timing['setup_slack_ns'],timing['hold_slack_ns']), slacks)
                self.assertEqual(timing['setup_sample_count'],10)
                self.assertEqual(timing['setup_sample_snapshot'],'final')
                self.assertEqual(result['scope'],'component_probe')
                self.assertEqual(timing['unconstrained_panel_status'],'Fail')
                self.assertGreater(timing['unconstrained_input_ports']['setup'],0)
                self.assertFalse(result['whole_core_clock_claim'])
                self.assertFalse(result['promotion_allowed'])
                self.assertFalse(timing['audited_clock'])
                self.assertFalse(timing['registered_stage_count_proof'])

    def test_native_cpu_memory_and_critical_path_identity(self):
        p8 = q.summarize(P8,PINS[P8]); p16 = q.summarize(P16,PINS[P16])
        self.assertEqual(p8['runtime']['allocation']['quartus_workers'],6)
        self.assertEqual(p16['runtime']['allocation']['quartus_workers'],4)
        self.assertEqual(p8['runtime']['wall_seconds'],590.34)
        self.assertEqual(p16['runtime']['wall_seconds'],1718.18)
        self.assertEqual(p8['timing']['setup_first_path']['source'],'controller_error')
        self.assertIn('stage15.shuffle4',p16['timing']['setup_first_path']['source'])
        self.assertGreater(p8['runtime']['cgroup_memory_peak_bytes'],0)
        self.assertEqual(p16['runtime']['cgroup_memory_swap_peak_bytes'],0)

    def test_wrong_receipt_or_native_resource_equation_rejected(self):
        with self.assertRaises(ValueError): q.summarize(P8,'0'*64)
        raw = (P8/'project/output_files/probe.fit.place.rpt').read_text()
        with self.assertRaises(ValueError): q.resources(raw.replace('; 54,089 ', '; 54,090 '))

    def test_missing_duplicate_or_inconsistent_native_timing_rejected(self):
        raw = (P8/'project/output_files/probe.sta.rpt').read_text()
        for bad in (raw.replace('Multicorner Timing Analysis Summary','removed'),
            raw.replace('; Setup Summary', '; Removed Setup Summary'),
            raw.replace('Report Timing: Found 10 setup paths','Report Timing: Found XX setup paths'),
            raw.replace('; 0.691 ; controller_error', '; 0.681 ; controller_error')):
            with self.subTest(tail=bad[:20]), self.assertRaises(ValueError): q.timing(bad)


if __name__ == '__main__': unittest.main()
