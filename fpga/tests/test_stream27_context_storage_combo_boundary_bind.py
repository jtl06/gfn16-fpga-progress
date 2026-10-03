import copy
import re
import unittest

from fpga.reference import stream27_context_storage_combo_boundary_bind as boundary


class BoundaryComboTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents = {n: boundary.prepare(n) for n in (256, 65536)}
        cls.candidates = {n: boundary.prepare(n, enabled=1) for n in (256, 65536)}

    def test_exact_default_and_parent_roster_guards(self):
        for n, parent in self.parents.items():
            self.assertEqual(boundary.bind(parent), parent)
            self.assertIsNot(boundary.bind(parent)['files'], parent['files'])
        for flag in (True, -1, 2):
            with self.assertRaises(ValueError):
                boundary.prepare(256, enabled=flag)
        changed = copy.deepcopy(self.parents[256])
        changed['files'][changed['top']+'.sv'] += '// mutation\n'
        with self.assertRaisesRegex(ValueError, 'EXACT_COMBO_ONLY'):
            boundary.bind(changed, enabled=1)

    def test_actual_calendar_no_forced_original_small_period(self):
        expected = {256: (213, 194, 213, 79, 152, 18, 1, 106),
                    65536: (8459, 8458, 12557, 4207, 8416, 0, 0, 8232)}
        for n, b in self.candidates.items():
            g = b['geometry']
            self.assertEqual(tuple(g[k] for k in ('warm_interval', 'first_digit', 'carry_done',
                'pointwise_accept', 'sink_accept', 'feedback_delay', 'boundary_frontend_added'))+
                (b['context_storage_combo_boundary']['second_cold_correction_accept'],), expected[n])
            self.assertEqual(g['correction_cache_latency'], 78)
            self.assertEqual(g['term_seed_first'], 71)
            self.assertEqual(g['term_seed_last'], 74)
            self.assertEqual(b['context_storage_combo_boundary']['roster'], ['BOUNDARY_INPUTREG'])
            self.assertNotIn('FINAL_GS_INPUTREG', b['parameters'])
            self.assertNotIn('QUARANTINE_REPLICAS', b['parameters'])

    def test_full_owner_field_sticky_and_publication_barriers_literal(self):
        for n, b in self.candidates.items():
            p = self.parents[n]
            for f in range(3):
                oldname = f'genefer_stream27_shared_warm_aw{p["geometry"]["aw"]}_p16_f{f}_storage_combo_v1.sv'
                newname = oldname.replace('_combo_v1', '_combo_boundary_v1')
                old, new = p['files'][oldname], b['files'][newname]
                self.assertIn('.PAYLOAD_W(27)) boundary (', new)
                self.assertIn('.clk,.rst_n,.quarantine(stop),.in_valid(boundary_slot),', new)
                for marker in (' always_comb begin\n  admission_bad=', ' always_comb begin\n  join_bad=',
                               ' always_ff @(posedge clk or negedge rst_n)begin\n  if(!rst_n)begin\n   input_remaining'):
                    start = old.index(marker)
                    end = old.index('\n end', start)+len('\n end')
                    self.assertIn(old[start:end], new)
                self.assertIn('assign out_error=controller_error;', new)
                self.assertIn('wire stop=controller_error;', new)
            host_parent = p['files'][p['top']+'.sv']
            host = b['files'][b['top']+'.sv']
            # The only host functional delta is the explicitly proved cold B
            # correction calendar. All publication FSM and owner checks stay.
            restored = host.replace('module '+b['top']+' #', 'module '+p['top']+' #', 1)
            restored = restored.replace(',BOUNDARY_INPUTREG=1', '', 1)
            old_control = re.search(r'CONTEXT_OFFSET=\d+,SECOND_CORRECTION=\d+', host_parent)[0]
            new_control = re.search(r'CONTEXT_OFFSET=\d+,SECOND_CORRECTION=\d+', restored)[0]
            self.assertEqual(restored.replace(new_control, old_control, 1), host_parent)

    def test_model_full_period_disjoint_ports_and_four_lease_lifetimes(self):
        for n, b in self.candidates.items():
            for counts in ((1, 1), (3, 14), (16, 16)):
                plan = boundary.schedule(b['geometry'], counts)
                self.assertLessEqual(plan['lease_peak'], 4)
                self.assertEqual(plan['launch_gaps'], [106, 107] if n == 256 else [4229, 4230])
                self.assertTrue(all(c['margin'] >= 0 for c in plan['correction']))
                self.assertEqual(plan['feedback_peak_rows'], [16, 16] if n == 256 and counts != (1, 1)
                                 else [0, 0])
                self.assertFalse(plan['full_N_numeric_performed'])

    def test_compiled_module_closure_and_unchanged_math(self):
        for n, b in self.candidates.items():
            p = self.parents[n]
            self.assertEqual(len(b['files']), 54)
            for name in p['files']:
                if not name.startswith('genefer_stream27_shared_warm_') and name != p['top']+'.sv':
                    restored = b['files'][name]
                    for f in range(3):
                        new = f'genefer_stream27_shared_warm_aw{b["geometry"]["aw"]}_p16_f{f}_storage_combo_boundary_v1'
                        restored = restored.replace(new, new.replace('_combo_boundary_v1', '_combo_v1'))
                    self.assertEqual(restored, p['files'][name])
            text = re.sub(r'//[^\n]*|/\*.*?\*/', '', '\n'.join(b['files'].values()), flags=re.S)
            definitions = dict(re.findall(r'\bmodule\s+(\w+)\b(.*?)\bendmodule\b', text, flags=re.S))
            pending, seen = [b['top']], set()
            while pending:
                name = pending.pop()
                if name in seen:
                    continue
                self.assertIn(name, definitions)
                seen.add(name)
                pending += re.findall(r'\b((?:genefer_|merged_stream27_)\w+)\s+(?:#\([^;]*?\)\s+)?\w+\s*\(', definitions[name])
            self.assertIn('genefer_stream27_signed_boundary_inputreg_v1', seen)
            self.assertEqual(b['generated_sha256'], {k: boundary.sha(v) for k, v in b['files'].items()})


if __name__ == '__main__':
    unittest.main()
