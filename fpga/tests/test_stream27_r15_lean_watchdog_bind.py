import re
import unittest
from fpga.reference import stream27_r15_lean_watchdog_bind as own


class R15LeanBindTests(unittest.TestCase):
    def test_all_off_literal_field100(self):
        for n in (256, 65536):
            parent = own.capture(n)
            self.assertEqual(own.bind(parent), parent)

    def test_all_flags_geometry_module_closure_and_reverse(self):
        for n in (256, 65536):
            parent = own.capture(n)
            for lean, watch in ((0, 1), (1, 0), (1, 1)):
                with self.subTest(n=n, lean=lean, watch=watch):
                    bundle = own.bind(parent, lean_build=lean, progress_watchdog=watch)
                    self.assertEqual(bundle['geometry'], parent['geometry'])
                    self.assertEqual(len(bundle['files']), 58 + watch)
                    roles = bundle['r15_lean_watchdog']
                    for name, delta in roles['modified'].items():
                        text = bundle['files'][name]
                        for old, new in delta['module_mapping'].items():
                            text = re.sub(r'\b' + re.escape(new) + r'\b', old, text)
                        for before, after in reversed(delta['edits']):
                            self.assertEqual(text.count(after), 1)
                            text = text.replace(after, before, 1)
                        self.assertEqual(text, parent['files'][delta['parent']])
                    definitions = set()
                    instances = set()
                    for text in bundle['files'].values():
                        definitions.update(re.findall(r'\bmodule\s+(\w+)', text))
                        instances.update(re.findall(r'\b(genefer\w+)\s*#\s*\(', text))
                    # Frozen FIELD100 retains an unused legacy term definition;
                    # compare the baseline and prove the selected top's closure.
                    baseline_definitions, baseline_instances = set(), set()
                    for text in parent['files'].values():
                        baseline_definitions.update(re.findall(r'\bmodule\s+(\w+)', text))
                        baseline_instances.update(re.findall(r'\b(genefer\w+)\s*#\s*\(', text))
                    self.assertEqual(instances - definitions, baseline_instances - baseline_definitions)
                    self.assertEqual(bundle['parameters']['MONT_FACTORED'], 1)
                    graph = {}
                    for text in bundle['files'].values():
                        for match in re.finditer(r'\bmodule\s+(\w+)(.*?)(?=\bendmodule\b)', text, re.S):
                            graph[match[1]] = set(re.findall(r'\b(genefer\w+)\s*#\s*\(', match[2]))
                    todo, visited, missing = [bundle['top']], set(), set()
                    while todo:
                        name = todo.pop()
                        if name in visited:
                            continue
                        visited.add(name)
                        if name not in graph:
                            missing.add(name)
                        else:
                            todo.extend(graph[name])
                    self.assertFalse(missing)
                    if watch:
                        self.assertIn('genefer_stream27_r15_progress_watchdog_v1', definitions)

    def test_functional_owner_and_watchdog_contexts_retained(self):
        bundle = own.prepare(256, lean_build=1, progress_watchdog=1)
        host = bundle['files'][bundle['top'] + '.sv']
        for marker in ('wire [111:0] live_owner=', 'wire ingress_bad=', 'wire capture_bad=',
                       'wire canonical_config_bad=', 'publish_owner<=live_owner',
                       'copy_committed', 'second_correction_sent', 'child_started[w*32+:32]>child_completed[w*32+:32]',
                       'runnable_next', 'levels[w]!=0'):
            self.assertIn(marker, host)
        comm = next(text for name, text in bundle['files'].items() if 'shared_packed_faultlocal' in name)
        self.assertIn('expected_generation=', comm)
        self.assertIn("owner_bad=1'b0", comm)
        self.assertIn('host GL assumed', bundle['r15_lean_watchdog']['label'])
        self.assertFalse(bundle['r15_lean_watchdog']['twin_fault_protection_inherited'])
        fields = [text for text in bundle['files'].values()
                  if ' assign out_error_fast=protocol_error;' in text]
        self.assertEqual(len(fields), 3)
        for field in fields:
            self.assertIn('fault_pending=out_error_fast || protocol_pending || (!stop && (admission_bad || join_bad));', field)
            self.assertIn('.external_fault_pending(admission_bad || join_bad)', field)
            self.assertIn('FIELD100_REPORT_COPY_ALIGNMENT_NOT_FAST_ORIGIN', field)
        arithmetic = next(text for text in bundle['files'].values()
                          if ' assign error_barrier=out_error || (|field_fast) || local_fault_q;' in text)
        self.assertIn('wire local_fault_now=setup_error || join_bad || carry_bad || admission_bad;', arithmetic)
        self.assertIn('if(local_fault_q)out_error<=1;', arithmetic)
        warm = next(text for text in bundle['files'].values()
                    if ' assign out_error=local_error || child_error;' in text)
        self.assertIn(' assign error_barrier=local_error || child_barrier;', warm)
        self.assertIn('if(child_barrier || collision || count_bad || command_bad || cold_request_bad)local_error<=1;', warm)

    def test_compatible_neutral_composition_and_strict_flags(self):
        parent = own.capture(256)
        # A prior neutral integration may add its own switch without rebasing.
        parent['parameters']['FIXED_SCHEDULE'] = 1
        result = own.bind(parent, lean_build=1, progress_watchdog=1)
        self.assertEqual(result['parameters']['FIXED_SCHEDULE'], 1)
        for value in (True, False, 2, -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                own.bind(parent, lean_build=value)


if __name__ == '__main__':
    unittest.main()
