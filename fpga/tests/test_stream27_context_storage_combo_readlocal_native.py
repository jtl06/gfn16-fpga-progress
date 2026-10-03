"""Source-only R4 native-role checks; no HDL or full-N numerical execution."""
import unittest
from fpga.reference import stream27_context_storage_combo_readlocal_native as n
from fpga.reference import stream27_context_storage_combo_readlocal_bind as b


class NativeRoles(unittest.TestCase):
    def test_both_roles_preserve_original_normal_contract_and_complete_graph(self):
        for stage in ('aw8', 'full'):
            old, originals, bundle = n.capture(stage)
            manifest, files, production = n.role(stage)
            self.assertEqual(manifest['steps'], old['steps'])
            self.assertEqual(manifest['probe'], old['probe'])
            self.assertEqual(files[old['build']['cpp_source']], originals[old['build']['cpp_source']])
            self.assertEqual(len(production['files']), 55)
            self.assertEqual(len(manifest['build']['sv_sources']), 55 if stage == 'aw8' else 56)
            self.assertEqual(manifest['build']['parameters'], dict(old['build']['parameters'], CANONICAL_READ_LOCAL=1))
            self.assertEqual(production['geometry'], bundle['geometry'])
            self.assertTrue(all(n.sha(files['rtl/' + name]) == pin for name, pin in production['generated_sha256'].items()))
            for name, data in originals.items():
                if name.endswith(('.cpp', '.json')) or 'reference' in name and not name.startswith('lineage/'):
                    self.assertEqual(files[name], data)

    def test_default_parent_exact_and_readlocal_leaf_reverse(self):
        for stage in ('aw8', 'full'):
            _, _, bundle = n.capture(stage)
            self.assertEqual(b.bind(bundle, enabled=0), bundle)
            import json
            parent = b.quarantine.prepare(bundle['geometry']['n'], enabled=1)
            self.assertEqual(json.loads(json.dumps(parent)), bundle)
            production = b.bind(parent, enabled=1)
            self.assertEqual(b.reverse_leaf(production['files'][b.NEW + '.sv']), bundle['files'][b.OLD + '.sv'])
            self.assertEqual(production['context_storage_combo_readlocal']['model']['cases'], 8192)
            self.assertEqual(production['context_storage_combo_readlocal']['read_latency_delta'], 0)

    def test_actual_observer_passes_new_parameter_and_adds_no_state(self):
        manifest, files, _ = n.role('full')
        text = files['rtl/' + manifest['build']['top'] + '.sv'].decode()
        self.assertNotRegex(text, r'\b(always|always_ff|always_comb|initial)\b')
        self.assertEqual(text.count('CANONICAL_READ_LOCAL=1'), 1)
        self.assertEqual(text.count('.CANONICAL_READ_LOCAL(CANONICAL_READ_LOCAL)'), 1)

    def test_unsupported_and_ambiguous_seams_refuse(self):
        with self.assertRaises(ValueError):
            n.capture('aw5')
        with self.assertRaises(ValueError):
            n.once('same same', 'same', 'new')


if __name__ == '__main__':
    unittest.main()
