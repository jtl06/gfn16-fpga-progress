import unittest
from pathlib import Path

from synthesis.staged_calibration_v2 import build, V1_SHA
from synthesis.staged_calibration import WHOLE64, boundary_analysis
from synthesis.staged_fit import digest, regular


class CalibrationV2Tests(unittest.TestCase):
    def test_new_success_invalidates_long148_abort(self):
        rows=[dict(design_class=WHOLE64,outcome=o,metrics={'peak_long_demand_percent':v})
              for o,v in [('routed',133),('routed',150),('route_failed',148),('route_failed',200)]]
        long=next(r for r in boundary_analysis(rows)['metrics'] if r['metric']=='peak_long_demand_percent')
        self.assertEqual(long['maximum_known_routed_value'],150)
        self.assertEqual(long['minimum_known_failed_value'],148)
        self.assertFalse(long['empirical_separator_exists'])
        self.assertIsNone(long['strict_above_threshold_empirical_interval'])
        self.assertFalse(long['threshold_enabled'])

    def test_source_backed_successor_preserves_v1_and_stage_classes(self):
        root=Path(__file__).resolve().parents[1]/'results/throughput-20260929'
        old=root/'staged-fit-calibration-v1.json';before=regular(old)
        result=build(root)
        self.assertEqual(digest(before),V1_SHA);self.assertEqual(regular(old),before)
        self.assertEqual(len(result['rows']),11)
        self.assertEqual((result['threshold_analysis']['routed_count'],result['threshold_analysis']['route_failed_count']),(3,3))
        rootfused=next(r for r in result['rows'] if r['id']=='core27-r2-rootfused64-aws-fit-v1')
        self.assertEqual(rootfused['metrics']['peak_long_demand_percent'],150)
        self.assertEqual(rootfused['metrics']['peak_short_demand_percent'],118)
        self.assertEqual(rootfused['metrics']['route_through_aluts'],110589)
        self.assertEqual(rootfused['final_route_through_aluts'],83505)
        self.assertFalse(rootfused['timing_observations']['internal_timing_met'])
        self.assertTrue(rootfused['source_and_control_review_rechecked'])
        self.assertTrue(all(r['threshold_enabled'] is False for r in result['threshold_analysis']['metrics']))
        long=next(r for r in result['threshold_analysis']['metrics'] if r['metric']=='peak_long_demand_percent')
        self.assertIn('No standalone',long['interpretation'])
        self.assertFalse(any('crt27' in r['id'] for r in result['rows']))


if __name__=='__main__':unittest.main()
