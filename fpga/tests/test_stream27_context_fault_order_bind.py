import copy
import re
import unittest

from fpga.reference import stream27_context_fault_order_bind as order


class FaultOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents = {n: order.prepare(n) for n in order.CAPTURES}
        cls.candidates = {n: order.bind(parent, enabled=1) for n, parent in cls.parents.items()}

    def test_default_exact_deep_copy_and_flag_legality(self):
        for parent in self.parents.values():
            result = order.bind(parent)
            self.assertEqual(result, parent)
            self.assertIsNot(result['files'], parent['files'])
            for flag in (True, -1, 2, '1'):
                with self.assertRaisesRegex(ValueError, 'BOOLEAN_FLAG'):
                    order.bind(parent, enabled=flag)

    def test_three_moves_literal_reverse_and_no_behavior_rewrite(self):
        for n, parent in self.parents.items():
            candidate = self.candidates[n]
            changed = candidate['fault_source_order']['changed']
            self.assertEqual(len(changed), 3)
            self.assertEqual(set(candidate['files']), set(parent['files']))
            self.assertEqual(candidate['top'], parent['top'])
            self.assertEqual(candidate['parameters'], parent['parameters'])
            self.assertEqual(candidate['geometry'], parent['geometry'])
            self.assertEqual(candidate['rtl_sources'], parent['rtl_sources'])
            for change in changed:
                name = change['name']
                before, after = parent['files'][name], candidate['files'][name]
                self.assertEqual(order.reverse_root(after), before)
                self.assertEqual(before.replace(order.INSTANCE, ''), after.replace(order.INSTANCE, ''))
                self.assertEqual(before.count(order.INSTANCE), 1)
                self.assertEqual(after.count(order.INSTANCE), 1)
                self.assertEqual(re.findall(r'always_(?:ff|comb).*?end', before, flags=re.S),
                                 re.findall(r'always_(?:ff|comb).*?end', after, flags=re.S))
            self.assertEqual(sum(candidate['files'][name] != text for name, text in parent['files'].items()), 3)

    def test_all_fault_inputs_declared_before_instance_nine_bits_retained(self):
        for candidate in self.candidates.values():
            for change in candidate['fault_source_order']['changed']:
                text = candidate['files'][change['name']]
                for declaration in order.DECLARATIONS:
                    self.assertLess(text.index(declaration), text.index(order.INSTANCE))
                self.assertIn('logic [8:0] child_error,child_pending;', text)
                for index in range(9):
                    self.assertRegex(text, rf'(?:\.out_error\(child_error\[{index}\]\)|assign child_error\[{index}\]=)')
                self.assertIn('if(' + order.SETTER + ')', text)
                self.assertIn('.fault_set(' + order.SETTER + ')', text)

    def test_mutation_mixture_and_double_apply_rejected(self):
        parent = self.parents[256]
        bad = copy.deepcopy(parent)
        bad['files'][bad['top'] + '.sv'] += '// not captured\n'
        with self.assertRaisesRegex(ValueError, 'EXACT_SELECTED58'):
            order.bind(bad, enabled=1)
        with self.assertRaisesRegex(ValueError, 'EXACT_SELECTED58'):
            order.bind(self.candidates[256], enabled=1)
        bad = copy.deepcopy(parent)
        bad['storage_contract']['compact_GEN_MLAB'] = True
        with self.assertRaisesRegex(ValueError, 'UNMIXED_STORAGE_PARENT'):
            order.bind(bad, enabled=1)
        text = next(parent['files'][c['name']] for c in self.candidates[256]['fault_source_order']['changed'])
        with self.assertRaisesRegex(ValueError, 'EXACT_PARENT_INSTANCE'):
            order.reorder(text.replace(order.INSTANCE, order.INSTANCE.replace('(|child_error)', 'child_error[0]')))


if __name__ == '__main__':
    unittest.main()
