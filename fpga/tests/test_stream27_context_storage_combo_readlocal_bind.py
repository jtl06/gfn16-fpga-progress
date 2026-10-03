import copy
import re
import unittest

from fpga.reference import stream27_context_storage_combo_readlocal_bind as readlocal


class CanonicalReadLocalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents = {n: readlocal.prepare(n) for n in (256, 65536)}
        cls.candidates = {n: readlocal.prepare(n, enabled=1) for n in cls.parents}

    def test_exhaustive_priority_model_first(self):
        self.assertEqual(readlocal.prove_reads(), dict(cases=8192, eligible_read_cases=64,
            eligible_response_cases=64, no_unknown_input_equivalence_claim=True))
        # A pending token permits another read, but either load/begin blocks
        # both the old and new read/response on that exact conflict edge.
        for load, begin in ((0, 0), (1, 0), (0, 1), (1, 1)):
            a, b, c, d, rejected = readlocal.read_model(1, 1, 0, 1, 1, load, begin, 1,
                                                       0, 1, 1, 0, 1)
            self.assertEqual((a, b, c, d), (not(load or begin),)*4)
            self.assertEqual(rejected, bool(load or begin))

    def test_default_and_exact_roster_guard(self):
        for p in self.parents.values():
            self.assertEqual(readlocal.bind(p), p)
            self.assertIsNot(readlocal.bind(p)['files'], p['files'])
        for flag in (True, -1, 2):
            with self.assertRaises(ValueError):
                readlocal.prepare(256, enabled=flag)
        changed = copy.deepcopy(self.parents[256])
        changed['files'][changed['top']+'.sv'] += '// mutation\n'
        with self.assertRaisesRegex(ValueError, 'EXACT_R3_ONLY'):
            readlocal.bind(changed, enabled=1)

    def test_canonical_leaf_every_byte_reverse(self):
        for n, b in self.candidates.items():
            original = self.parents[n]['files'][readlocal.OLD+'.sv']
            candidate = b['files'][readlocal.NEW+'.sv']
            self.assertEqual(readlocal.reverse_leaf(candidate), original)
            for marker in ('    always_comb begin\n        load_bad=',
                           '    always_ff @(posedge clk or negedge rst_n)begin'):
                start = original.index(marker)
                end = original.index('\n    end', start)+len('\n    end')
                section = original[start:end]
                if marker.endswith('rst_n)begin'):
                    section = section.replace(readlocal.RESPONSE_BEFORE, 'legal_response')
                self.assertIn(section, candidate)
            # RAM port arbitration, all numeric state, range checks, and
            # malformed-command priority are unchanged; no new FF declared.
            self.assertEqual(candidate.count('always_ff'), original.count('always_ff'))
            self.assertIn('read_pending<=legal_read;', candidate)
            self.assertIn('if(idle_reject)begin', candidate)

    def test_host_owner_and_every_other_file_literal(self):
        for n, b in self.candidates.items():
            p = self.parents[n]
            self.assertEqual(b['geometry'], p['geometry'])
            self.assertEqual(b['two_context_schedule'], p['two_context_schedule'])
            self.assertEqual(b['parameters'], dict(p['parameters'], CANONICAL_READ_LOCAL=1))
            self.assertEqual(len(b['files']), 55)
            for name, original in p['files'].items():
                if name == readlocal.OLD+'.sv':
                    continue
                if name == p['top']+'.sv':
                    text = b['files'][b['top']+'.sv'].replace(b['top'], p['top'], 1)
                    text = text.replace(' '+readlocal.NEW+' #', ' '+readlocal.OLD+' #', 1)
                    text = text.replace(',CANONICAL_READ_LOCAL=1', '', 1)
                else:
                    text = b['files'][name]
                self.assertEqual(text, original)

    def test_reachable_module_source_closure(self):
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
            self.assertIn(readlocal.NEW, seen)
            self.assertNotIn(readlocal.OLD, seen)
            self.assertEqual(b['generated_sha256'], {k: readlocal.sha(v) for k, v in b['files'].items()})


if __name__ == '__main__':
    unittest.main()
