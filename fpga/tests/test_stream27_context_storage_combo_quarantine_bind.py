import copy
import re
import unittest

from fpga.reference import stream27_context_storage_combo_quarantine_bind as replicas


class QuarantineComboTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents = {n: replicas.prepare(n) for n in (256, 65536)}
        cls.candidates = {n: replicas.prepare(n, enabled=1) for n in cls.parents}

    def test_default_byte_exact_and_roster_guard(self):
        for n, parent in self.parents.items():
            self.assertEqual(replicas.bind(parent), parent)
            self.assertIsNot(replicas.bind(parent)['files'], parent['files'])
        for flag in (True, -1, 2):
            with self.assertRaises(ValueError):
                replicas.prepare(256, enabled=flag)
        changed = copy.deepcopy(self.parents[256])
        changed['files'][changed['top']+'.sv'] += '// mutation\n'
        with self.assertRaisesRegex(ValueError, 'EXACT_R2_ONLY'):
            replicas.bind(changed, enabled=1)

    def test_every_field_byte_reverses_and_inputs_declared(self):
        for n, b in self.candidates.items():
            p = self.parents[n]
            for field in range(3):
                old = f'genefer_stream27_shared_warm_aw{p["geometry"]["aw"]}_p16_f{field}_storage_combo_boundary_v1'
                new = old.replace('_boundary_v1', '_quarantine_v1')
                text = b['files'][new+'.sv']
                self.assertEqual(replicas.reverse_field(text, old, new), p['files'][old+'.sv'])
                instance = text.index(' fault_replicas (')
                for decl in ('logic [8:0] child_error,child_pending;',
                             'logic admission_bad,join_bad;', 'wire protocol_error,protocol_pending;',
                             'wire inverse_error,inverse_pending;'):
                    self.assertLess(text.index(decl), instance)
                self.assertEqual(text.count(replicas.fault.SETTER), 2)
                self.assertIn('transform_quarantine!={2{controller_error}}', text)

    def test_every_nonfield_byte_and_calendar_reverse(self):
        for n, b in self.candidates.items():
            p = self.parents[n]
            self.assertEqual(b['geometry'], p['geometry'])
            self.assertEqual(b['two_context_schedule'], p['two_context_schedule'])
            self.assertEqual(b['parameters'], dict(p['parameters'], QUARANTINE_REPLICAS=1))
            self.assertEqual(len(b['files']), 55)
            for name, original in p['files'].items():
                if name.startswith('genefer_stream27_shared_warm_'):
                    continue
                if name == p['top']+'.sv':
                    text = b['files'][b['top']+'.sv'].replace(b['top'], p['top'])
                    text = text.replace(',QUARANTINE_REPLICAS=1', '', 1)
                else:
                    text = b['files'][name].replace('_storage_combo_quarantine_v1', '_storage_combo_boundary_v1')
                self.assertEqual(text, original)
            self.assertNotIn('FINAL_GS_INPUTREG', b['parameters'])
            self.assertNotIn('TERM_SELECT_TOKEN', b['parameters'])

    def test_sticky_replicas_same_origin_edge_model(self):
        # Reset, back-to-back faults, and already-stopped arbitrary setters.
        # The exact RTL leaf contains the same asynchronous-reset update.
        for sequence in range(1 << 12):
            public, local = False, [False, False]
            for edge in range(6):
                rst_n = bool(sequence & (1 << (edge*2)))
                bad = bool(sequence & (1 << (edge*2+1)))
                setter = not public and bad
                public = False if not rst_n else public or setter
                local = [False if not rst_n else state or setter for state in local]
                self.assertEqual(local, [public, public])

    def test_reachable_closure_and_fixed_leaf(self):
        for n, b in self.candidates.items():
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
            self.assertIn('genefer_stream27_quarantine_replicas_v1', seen)
            self.assertEqual(replicas.sha(b['files']['genefer_stream27_quarantine_replicas_v1.sv']), replicas.LEAF_PIN)
            self.assertEqual(b['generated_sha256'], {k: replicas.sha(v) for k, v in b['files'].items()})


if __name__ == '__main__':
    unittest.main()
