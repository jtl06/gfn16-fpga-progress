"""Pure retained-report parsing and area-gate rejection tests."""
import unittest
from fpga.reference import radix22_selector_physical_replay_v1 as r


class SelectorPhysicalReplayTests(unittest.TestCase):
    def test_measured_gate_and_conditional_successor(self):
        p = r.planning([8908.4, 22744.7, 13441.4])
        self.assertEqual(p['three_source_whole_calibrated_heuristic'], 327719.9)
        self.assertFalse(p['three_source_gate_PASS'])
        self.assertEqual(p['additional_whole_saving_needed'], 7719.9)
        self.assertEqual(p['additional_per_field_saving_needed'], 2573.3)
        self.assertEqual(p['two_source_same_residual_heuristic'], 323831.9)
        self.assertFalse(p['two_source_area_measured'])

    def test_planning_invalid_inputs_reject(self):
        for values in ([1, 2], [True, 2, 3], [1, 2, float('inf')], [1, 2, float('nan')], [1, -2, 3]):
            with self.assertRaises(ValueError):
                r.planning(values)

    def test_numeric_hierarchy_pair_and_malformed(self):
        self.assertEqual(r.scalar('13,441.4 (13441.4)'), (13441.4, 13441.4))
        self.assertEqual(r.scalar('31247.5 (17799.4)'), (31247.5, 17799.4))
        for value in ('unavailable', '13.4 extra', '13.4 (unavailable)', '13.4 (12) (11)'):
            with self.assertRaises(ValueError):
                r.scalar(value)

    def test_actual_child_not_wrapper_and_ambiguous_reject(self):
        path = r.h.FPGA / 'queue/fit-r54-controller-v8/terminal/n1-selector-mode2/evidence/project/output_files/probe.fit.rpt'
        text = path.read_text()
        self.assertEqual(r.entity(text, 'network')['needed_ALMs']['inclusive'], 13441.4)
        self.assertEqual(r.entity(text, 'network')['registers']['own'], 0)
        self.assertEqual(r.entity(text, '|')['registers']['own'], 19921)
        with self.assertRaises(ValueError):
            r.entity(text, 'absent_network')
        duplicate = next(x for x in text.splitlines() if x.startswith(';    |network|'))
        with self.assertRaises(ValueError):
            r.entity(text + '\n' + duplicate, 'network')

    def test_inconsistent_total_reject(self):
        self.assertEqual(r.number('; Total registers ; 19,921 ;\n', 'Total registers'), 19921)
        with self.assertRaises(ValueError):
            r.number('; Total registers ; 19,921 ;\n; Total registers ; 1 ;\n', 'Total registers')

    def test_existing_frontier_remains_conditional_and_fails(self):
        f = r.recalibrated_frontier(r.planning([8908.4, 22744.7, 13441.4]))
        self.assertEqual(f['passing_all_declared_heuristics'], 0)
        self.assertEqual(f['best_area_memory_safe']['conditional_ALMs'], 323831.9)
        self.assertEqual(f['best_area_memory_safe']['M20K_proxy'], 1539)
        self.assertEqual(f['best_area_without_memory_gate']['conditional_ALMs'], 319943.9)
        self.assertEqual(f['best_area_without_memory_gate']['M20K_proxy'], 2331)
        self.assertFalse(f['next_fit_requested'])


if __name__ == '__main__':
    unittest.main()
