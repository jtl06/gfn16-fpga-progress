import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('search', Path(__file__).resolve().parents[1]/'tools/audit_period_search.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def phase(period, setup, hold=.014):
    corner = {}
    for kind, slack in dict(setup=setup, hold=hold, recovery=1, removal=1, mpw=4).items():
        corner[kind] = dict(status='measured', slack_ns=slack, tns_ns=min(0, slack),
                            failing_endpoints=int(slack < 0), closes=slack >= 0)
    return dict(period_ns=period, timing_closes=all(x['closes'] for x in corner.values()),
                corners={str(i):corner for i in range(4)})


def receipt(selected=None, baseline_slack=-1.155, selected_slack=.005):
    timing = dict(baseline=phase(10, baseline_slack))
    if selected is not None:
        timing['selected'] = phase(selected, selected_slack)
    return dict(project='fixed', original_invocation='original', fit_commands=0,
                original_unchanged=True, compiled_input_unchanged=True, terminal_proven=True,
                original_tree_sha256='a'*64, qdb_inventory_sha256='b'*64, timing=timing)


class SearchTests(unittest.TestCase):
    def test_baseline_then_explicit_margin_then_adjacent_bracket(self):
        self.assertIsNone(s.choose([], 'fixed', 'original')['selected_period_ns'])
        first = receipt()
        self.assertEqual(s.choose([first], 'fixed', 'original')['selected_period_ns'], '11.166')
        passed = receipt(11.16, selected_slack=.005)
        self.assertEqual(s.choose([first, passed], 'fixed', 'original')['selected_period_ns'], '11.152')
        failed = receipt(11.152, selected_slack=-.003)
        self.assertEqual(s.choose([first, passed, failed], 'fixed', 'original')['selected_period_ns'], '11.156')
        adjacent = receipt(11.158, selected_slack=-.001)
        self.assertEqual(s.choose([first, passed, failed, adjacent], 'fixed', 'original')['action'], 'complete')

    def test_source_drift_typed_inconsistency_and_duplicate_drift_rejected(self):
        a = receipt(11.16)
        b = receipt(11.158, selected_slack=-.001)
        b['qdb_inventory_sha256'] = 'c'*64
        with self.assertRaisesRegex(ValueError, 'layout changed'):
            s.choose([a, b], 'fixed', 'original')
        a['timing']['selected']['timing_closes'] = False
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            s.choose([a], 'fixed', 'original')
        with self.assertRaisesRegex(ValueError, 'period changed'):
            s.choose([receipt(), receipt(baseline_slack=-1.154)], 'fixed', 'original')

    def test_runtime_step_bound_and_hold_do_not_make_clock_claim(self):
        decision = s.choose([receipt(11.16)], 'fixed', 'original', max_selected=1)
        self.assertEqual(decision['action'], 'bounded_stop')
        self.assertEqual(decision['best_passing_period_ns'], 11.16)
        a = receipt()
        a['timing']['baseline'] = phase(10, 1, hold=-.001)
        decision = s.choose([a], 'fixed', 'original')
        self.assertEqual(decision['action'], 'bounded_stop')
        self.assertIsNone(decision['best_passing_period_ns'])

    def test_zero_margin_prediction_is_only_untried_interior_test(self):
        passed=receipt(15.740,selected_slack=.258)
        failed=receipt(15.480,selected_slack=-.002)
        decision=s.choose([passed,failed],'fixed','original')
        self.assertEqual(decision['action'],'audit')
        self.assertEqual(decision['selected_period_ns'],'15.482')
        self.assertEqual(decision['best_passing_period_ns'],15.740)
        actual=receipt(15.482,selected_slack=0)
        final=s.choose([passed,failed,actual],'fixed','original')
        self.assertEqual(final['action'],'complete')
        self.assertEqual(final['best_passing_period_ns'],15.482)
        self.assertEqual(final['failing_lower_period_ns'],15.480)

    def test_prediction_rounding_duplicate_and_outside_bracket_fall_back(self):
        passed=receipt(15.740,selected_slack=.257)
        failed=receipt(15.482,selected_slack=-.001)
        self.assertEqual(s.choose([passed,failed],'fixed','original')['selected_period_ns'],'15.484')
        # If that prediction itself fails, do not retry it or assert monotonic
        # closure: choose a new interior midpoint and require actual evidence.
        failed_prediction=receipt(15.484,selected_slack=-.001)
        self.assertEqual(s.choose([passed,failed,failed_prediction],'fixed','original')['selected_period_ns'],'15.612')
        high_lower=receipt(15.600,selected_slack=-.001)
        self.assertEqual(s.choose([passed,high_lower],'fixed','original')['selected_period_ns'],'15.670')
        corrupt=receipt(15.484,selected_slack=0)
        corrupt['timing']['selected']['corners']['0']=phase(15.484,0,hold=-.001)['corners']['0']
        with self.assertRaisesRegex(ValueError,'inconsistent'):
            s.choose([passed,failed,corrupt],'fixed','original')


if __name__ == '__main__':
    unittest.main()
