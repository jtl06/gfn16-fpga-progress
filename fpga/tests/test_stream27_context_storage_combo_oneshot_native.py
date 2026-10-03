"""R6 source/normal contract; no HDL or full-N numerical local work."""
import json
import unittest
from fpga.reference import stream27_context_storage_combo_oneshot_native as n
from fpga.reference import stream27_context_storage_combo_oneshot_bind as b


class OneShotNativeTests(unittest.TestCase):
    def test_actual_toolchain_identity_emitter(self):
        source=(n.ROOT/n.SELF).read_text()
        self.assertIn("tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1'",source)
        self.assertNotIn('verilator6032',source)

    def test_captured_normal_oracle_and_full_source_closure(self):
        for stage in ('aw8', 'full'):
            old, files, captured = n.capture(stage)
            m, new, production = n.role(stage)
            self.assertEqual(m['steps'], old['steps'])
            self.assertEqual(m['probe'], old['probe'])
            self.assertEqual(new[old['build']['cpp_source']], files[old['build']['cpp_source']])
            self.assertEqual(production['geometry'], captured['geometry'])
            self.assertEqual(len(production['files']), 55)
            self.assertEqual(m['build']['parameters'], dict(old['build']['parameters'], COLD_SECOND_ONESHOT=1))
            self.assertEqual(len(m['build']['sv_sources']), 55 if stage == 'aw8' else 56)
            for name, digest in production['source_sha256'].items():
                self.assertEqual(n.sha(new['lineage/' + name]), digest)

    def test_default_and_literal_reverse(self):
        for stage in ('aw8', 'full'):
            _, _, captured = n.capture(stage)
            parent = b.loadlocal.prepare(captured['geometry']['n'], enabled=1)
            self.assertEqual(json.loads(json.dumps(parent)), captured)
            self.assertEqual(b.bind(parent, enabled=0), parent)
            new = b.bind(parent, enabled=1)
            self.assertEqual(b.reverse_host(new['files'][new['top'] + '.sv'], top=new['top'],
                             parent_top=parent['top']), parent['files'][parent['top'] + '.sv'])

    def test_native_observer_is_transparent(self):
        m, files, _ = n.role('full')
        text = files['rtl/' + m['build']['top'] + '.sv'].decode()
        self.assertNotRegex(text, r'\b(always|always_ff|always_comb|initial)\b')
        self.assertEqual(text.count('COLD_SECOND_ONESHOT=1'), 1)
        self.assertEqual(text.count('.COLD_SECOND_ONESHOT(COLD_SECOND_ONESHOT)'), 1)

    def test_accept_not_proposal_retires_and_three_aliases(self):
        proof = b.prove_wraps(8232)
        self.assertEqual(len(proof['old_alias_edges']), 4)
        self.assertEqual(len(proof['fixed_accepted_edges']), 1)
        self.assertTrue(proof['missed_accept_retained'])
        self.assertEqual(b.step(False, False, proposed=True, accepted=False), (False, True))


if __name__ == '__main__':
    unittest.main()
