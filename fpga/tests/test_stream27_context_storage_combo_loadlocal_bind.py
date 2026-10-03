import copy
import re
import unittest

from fpga.reference import stream27_context_storage_combo_loadlocal_bind as loadlocal


class CanonicalLoadLocalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents = {n: loadlocal.prepare(n) for n in (256, 65536)}
        cls.candidates = {n: loadlocal.prepare(n, enabled=1) for n in cls.parents}

    def test_exhaustive_priority_model(self):
        self.assertEqual(loadlocal.prove_loads(), dict(cases=8192, eligible_load_cases=8,
            no_unknown_input_equivalence_claim=True))
        # Dirty unrelated correction/raw-ready must not reject a valid LOAD.
        self.assertEqual(loadlocal.load_model(1, 1, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0),
                         (True, True, False))
        for pending, begin, read in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            self.assertEqual(loadlocal.load_model(1, 1, 0, 1, pending, 1, begin, read, 1, 0, 0, 1, 0),
                             (False, False, True))

    def test_default_roster_and_mutation_guards(self):
        for p in self.parents.values():
            self.assertEqual(loadlocal.bind(p), p)
            self.assertIsNot(loadlocal.bind(p)['files'], p['files'])
        for flag in (True, -1, 2):
            with self.assertRaises(ValueError):
                loadlocal.prepare(256, enabled=flag)
        changed = copy.deepcopy(self.parents[256])
        changed['files'][changed['top']+'.sv'] += '// mutation\n'
        with self.assertRaisesRegex(ValueError, 'EXACT_R4_ONLY'):
            loadlocal.bind(changed, enabled=1)

    def test_typed_order_predicate_including_malformed_counts(self):
        for rows in (16, 4096):
            counts = range(2*rows) if rows == 16 else (0, 1, rows-1, rows, rows+1, 2*rows-1)
            row_values = range(rows) if rows == 16 else (0, 1, rows-2, rows-1)
            for count in counts:
                for row in row_values:
                    rejected = (count == rows and row != 0) or (count != rows and row != count)
                    order_ok = row == 0 if count == rows else row == count
                    self.assertEqual(not rejected, order_ok)

    def test_every_leaf_host_and_other_byte_reverse(self):
        for n, b in self.candidates.items():
            p = self.parents[n]
            candidate = b['files'][loadlocal.NEW+'.sv']
            self.assertEqual(loadlocal.reverse_leaf(candidate), p['files'][loadlocal.OLD+'.sv'])
            self.assertEqual(candidate.count('always_ff'), p['files'][loadlocal.OLD+'.sv'].count('always_ff'))
            self.assertEqual(b['geometry'], p['geometry'])
            self.assertEqual(b['two_context_schedule'], p['two_context_schedule'])
            self.assertEqual(b['parameters'], dict(p['parameters'], CANONICAL_LOAD_LOCAL=1))
            self.assertEqual(len(b['files']), 55)
            for name, original in p['files'].items():
                if name == loadlocal.OLD+'.sv':
                    continue
                if name == p['top']+'.sv':
                    text = b['files'][b['top']+'.sv'].replace(b['top'], p['top'], 1)
                    text = text.replace(' '+loadlocal.NEW+' #', ' '+loadlocal.OLD+' #', 1)
                    text = text.replace(',CANONICAL_LOAD_LOCAL=1', '', 1)
                else:
                    text = b['files'][name]
                self.assertEqual(text, original)
            self.assertIn(loadlocal.readlocal.READ_AFTER, candidate)

    def test_reachable_module_and_source_closure(self):
        for b in self.candidates.values():
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
            self.assertIn(loadlocal.NEW, seen)
            self.assertNotIn(loadlocal.OLD, seen)
            self.assertEqual(b['generated_sha256'], {k: loadlocal.sha(v) for k, v in b['files'].items()})


if __name__ == '__main__':
    unittest.main()
