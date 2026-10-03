"""R5 normal graph/observer contract; source-only, no HDL/full-N math."""
import json
import subprocess
import sys
import unittest
from fpga.reference import stream27_context_storage_combo_loadlocal_native as n
from fpga.reference import stream27_context_storage_combo_loadlocal_bind as b


class LoadLocalNativeTests(unittest.TestCase):
    def test_same_normal_oracle_calendar_and_complete_production_graph(self):
        for stage in ('aw8', 'full'):
            old, originals, bundle = n.capture(stage)
            m, files, production = n.role(stage)
            self.assertEqual(m['steps'], old['steps'])
            self.assertEqual(m['probe'], old['probe'])
            self.assertEqual(files[old['build']['cpp_source']], originals[old['build']['cpp_source']])
            self.assertEqual(production['geometry'], bundle['geometry'])
            self.assertEqual(len(production['files']), 55)
            self.assertEqual(len(m['build']['sv_sources']), 55 if stage == 'aw8' else 56)
            self.assertEqual(m['build']['parameters'], dict(old['build']['parameters'], CANONICAL_LOAD_LOCAL=1))
            self.assertTrue(all(n.sha(files['rtl/' + name]) == pin
                                for name, pin in production['generated_sha256'].items()))
            self.assertTrue(all(n.sha(files['lineage/' + name]) == pin
                                for name, pin in production['source_sha256'].items()))

    def test_default_exact_and_one_leaf_predicate_reverse(self):
        for stage in ('aw8', 'full'):
            _, _, captured = n.capture(stage)
            parent = b.readlocal.prepare(captured['geometry']['n'], enabled=1)
            self.assertEqual(json.loads(json.dumps(parent)), captured)
            self.assertEqual(b.bind(parent, enabled=0), parent)
            production = b.bind(parent, enabled=1)
            self.assertEqual(b.reverse_leaf(production['files'][b.NEW + '.sv']), parent['files'][b.OLD + '.sv'])
            c = production['context_storage_combo_loadlocal']
            self.assertEqual(c['model']['cases'], 8192)
            self.assertEqual(c['calendar_delta'], 0)
            self.assertTrue(c['authoritative_fault_priority_unchanged'])

    def test_stateless_observer_passes_only_new_flag(self):
        m, files, _ = n.role('full')
        text = files['rtl/' + m['build']['top'] + '.sv'].decode()
        self.assertNotRegex(text, r'\b(always|always_ff|always_comb|initial)\b')
        self.assertEqual(text.count('CANONICAL_LOAD_LOCAL=1'), 1)
        self.assertEqual(text.count('.CANONICAL_LOAD_LOCAL(CANONICAL_LOAD_LOCAL)'), 1)
        self.assertEqual(text.count('.CANONICAL_READ_LOCAL(CANONICAL_READ_LOCAL)'), 1)

    def test_direct_cli_and_ambiguous_seams(self):
        result = subprocess.run([sys.executable, '-B', str(n.ROOT / n.SELF), '--help'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--stage', result.stdout)
        with self.assertRaises(ValueError):
            n.capture('aw5')
        with self.assertRaises(ValueError):
            n.once('same same', 'same', 'new')


if __name__ == '__main__':
    unittest.main()
