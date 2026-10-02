import copy
import unittest
from fpga.reference import stream27_host_chain_structural_v2 as candidate
from fpga.tools.prefit_structural_guard_v1 import source_inventory


class WholeSourceEndpoints(unittest.TestCase):
    def test_actual_source_and_companion_closure(self):
        spec, result, companions = candidate.inventory()
        self.assertEqual(result['findings'], [])
        self.assertEqual(len(spec['sources']), 49)
        self.assertEqual(len(spec['transfers']), 26)
        self.assertEqual(len(companions), 30)

    def test_field_source_and_CRT_sink_are_distinct(self):
        spec, _, _ = candidate.inventory()
        fields = [t for t in spec['transfers'] if '_to_CRT' in t['id']]
        self.assertEqual(len(fields), 6)
        for transfer in fields:
            stages = transfer['registered_stages']
            self.assertEqual([s['owner'] for s in stages], [transfer['producer'], 'CRT'])
            self.assertEqual([s['edge'] for s in stages], [0, 1])
            self.assertIn('CRT_input', stages[1]['id'])

    def test_missing_source_stage_is_not_source_guard_PASS(self):
        spec, _, _ = candidate.inventory()
        bad = copy.deepcopy(spec)
        transfer = next(t for t in bad['transfers'] if t['id'] == 'field0_upper_to_CRT')
        transfer['registered_stages'].pop(0)
        result = source_inventory(candidate.ROOT / candidate.parent.PROJECT, bad)
        self.assertEqual(result['findings'], [{'transfer': 'field0_upper_to_CRT',
            'reason': 'fewer_than_two_declared_registered_transfer_stages'}])


if __name__ == '__main__':
    unittest.main()
