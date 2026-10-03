"""Read-only passive-delta checks, never native execution or oracle generation."""
import json
import unittest
from fpga.reference import stream27_r15_application_full_diagnostic_v8 as own


class FullDiagnosticTests(unittest.TestCase):
    def test_only_error_message_changes_and_strict_expression_survives(self):
        m = json.loads((own.PARENT / 'manifest.json').read_bytes())
        cpp = (own.PARENT / 'source/fpga' / m['build']['cpp_source']).read_bytes()
        self.assertEqual(own.sha(cpp), own.CPP_PIN)
        after = own.diagnostic_cpp(cpp.decode())
        self.assertEqual(after.replace(own.NEW, own.OLD, 1), cpp.decode())
        self.assertIn('done_edges[0]<done_edges[1]&&waiting_b&&capture_copy==EXPECT_CAPTURE_COPY&&canonical_peer', after)
        self.assertIn('i<432ull*N', after)
        self.assertLess(after.index(own.NEW), after.index('read_word(d,c,a);'))
        self.assertLess(after.index('load(d,0);load(d,1);'), after.index('wr(d,0x40,4);'))

    def test_all_production70_parameters_reference_and_positive_validator_literal(self):
        before = json.loads((own.PARENT / 'manifest.json').read_bytes())
        after, files, bundle = own.role()
        self.assertEqual(after['build'], before['build'])
        self.assertEqual(after['steps'][0]['validator'], before['steps'][0]['validator'])
        self.assertEqual(len(bundle['files']), 70)
        for name, text in bundle['files'].items():
            self.assertEqual(files['rtl/' + name], text.encode())
        changes = {name for name in before['sources'] if own.sha(files[name]) != before['sources'][name]}
        self.assertEqual(changes, {before['build']['cpp_source']})
        self.assertEqual(after['build']['parameters']['EPOCH_SEED0'], 0)
        self.assertEqual(after['build']['parameters']['EPOCH_SEED1'], 0)


if __name__ == '__main__':
    unittest.main()
