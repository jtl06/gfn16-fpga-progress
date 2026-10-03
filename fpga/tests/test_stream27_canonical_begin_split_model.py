import unittest
from fpga.reference import stream27_canonical_begin_split_model as m


class BeginSplitModel(unittest.TestCase):
    def test_actual_frozen_source_consumers(self):
        self.assertEqual(len(m.source()['base_register_references']), 5)

    def test_control_payload_inductive_cases(self):
        result = m.prove()
        self.assertEqual(result['exhaustive_priority_state_cases'], 24576)
        self.assertEqual(result['rejected_dead_payload_differences'], 504)
        self.assertEqual(result['extra_edges'], 0)

    def test_prior_cycle_static_base_is_not_equivalent(self):
        inputs = (False, True, False, False, True, True, False, True, False, False)
        live = m.step('IDLE', False, 131077, 999999937, True, inputs, True)
        cached = m.step('IDLE', False, 131077, 131077, True, inputs, True)
        self.assertNotEqual(live[2], cached[2])
        self.assertEqual(live[2], 999999937)


if __name__ == '__main__':
    unittest.main()
