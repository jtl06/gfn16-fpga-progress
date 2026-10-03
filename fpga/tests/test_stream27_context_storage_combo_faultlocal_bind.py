import copy
import unittest

from fpga.reference import stream27_context_storage_combo_faultlocal_bind as local


class CompareBeforePhaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents = {n: local.prepare(n) for n in (256, 65536)}
        cls.candidates = {n: local.prepare(n, enabled=1) for n in cls.parents}

    def test_default_exact_deepcopy_and_source_guards(self):
        for parent in self.parents.values():
            self.assertEqual(local.bind(parent), parent)
            self.assertIsNot(local.bind(parent)['files'], parent['files'])
        for flag in (True, -1, 2):
            with self.assertRaises(ValueError):
                local.prepare(256, enabled=flag)
        bad = copy.deepcopy(self.parents[256])
        bad['files'][local.OLD+'.sv'] += '// drift\n'
        with self.assertRaisesRegex(ValueError, 'EXACT_R6_ONLY'):
            local.bind(bad, enabled=1)

    def test_full_leaf_host_and_six_identifier_callers_reverse(self):
        for n, candidate in self.candidates.items():
            parent = self.parents[n]
            self.assertEqual(len(candidate['files']), 55)
            self.assertEqual(local.reverse_leaf(candidate['files'][local.NEW+'.sv']),
                             parent['files'][local.OLD+'.sv'])
            self.assertEqual(local.reverse_host(candidate['files'][candidate['top']+'.sv'],
                top=candidate['top'], parent_top=parent['top']), parent['files'][parent['top']+'.sv'])
            callers = candidate['context_storage_combo_faultlocal']['caller_identifier_only']
            self.assertEqual(len(callers), 6)
            for name, text in parent['files'].items():
                if name in (local.OLD+'.sv', parent['top']+'.sv'):
                    continue
                restored = candidate['files'][name].replace(local.NEW+' #', local.OLD+' #')
                self.assertEqual(restored, text)
            self.assertEqual(candidate['geometry'], parent['geometry'])
            self.assertEqual(candidate['two_context_schedule'], parent['two_context_schedule'])
            self.assertEqual(candidate['parameters'], dict(parent['parameters'], COMM_OWNER_COMPARE_LOCAL=1))
            self.assertEqual(candidate['generated_sha256'], {name: local.sha(text)
                for name, text in candidate['files'].items()})
            self.assertEqual(candidate['context_storage_combo_faultlocal']['stage_instances'],
                             6*(candidate['geometry']['aw']-4))

    def test_no_selected_wide_tag_in_comparison_and_all_routing_literal(self):
        for n, candidate in self.candidates.items():
            leaf = candidate['files'][local.NEW+'.sv']
            self.assertNotIn('result_lower_tag', local.COMPARE_AFTER)
            for anchor in ('write_upper_tag=phase?head_lower_tag:input_tag;',
                           'result_lower_tag=phase?input_tag:head_lower_tag;',
                           'result_lower_word=phase?input_upper_word:head_lower_word;',
                           'fault_pending=out_error || (!quarantine && (malformed||owner_bad));',
                           'if(!quarantine && (malformed||owner_bad))out_error<=1;'):
                self.assertEqual(leaf.count(anchor), 1)
            self.assertTrue(candidate['context_storage_combo_faultlocal']['no_new_registers_or_delayed_faults'])
            self.assertEqual(candidate['context_storage_combo_faultlocal']['calendar_delta'], 0)


if __name__ == '__main__':
    unittest.main()
