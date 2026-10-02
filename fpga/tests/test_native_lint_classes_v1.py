import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from fpga.tools.native_lint_classes_v1 import classify, LintClassError, STYLE, FATAL


def warning(name, text=b'fixture.sv:1:2: diagnostic'):
    return b'%Warning-' + name.encode() + b': ' + text + b'\n'


class LintClasses(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.manifest = {'sources': {}, 'build': {'top': 'fixture'}}

    def result(self, stderr=b'', stdout=b'', code=0, manifest=None):
        return classify(code, stdout, stderr, self.manifest if manifest is None else manifest, self.root)

    def rejection(self, raw, *, stdout=b'', code=0, manifest=None):
        with self.assertRaises(LintClassError) as caught:
            self.result(raw, stdout, code, manifest)
        return caught.exception.receipt

    def test_all_style_classes_count_exact_bytes_without_perline_baseline(self):
        raw = b''.join(warning(name) for name in sorted(STYLE)) + warning('UNUSEDSIGNAL')
        result = self.result(raw, b'ordinary successful tool information\n')
        self.assertEqual(result['status'], 'admitted_lint_classes_exploration_ONLY')
        self.assertEqual(result['warning_count'], 8)
        self.assertEqual(result['class_counts']['UNUSEDSIGNAL'], 2)
        self.assertEqual(result['stderr_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result['stdout_sha256'], hashlib.sha256(b'ordinary successful tool information\n').hexdigest())
        self.assertTrue(result['exploration_only'])
        self.assertFalse(result['promotion_admission'])
        json.dumps(result, allow_nan=False)

    def test_clean_success_nonempty_stdout_allowed(self):
        self.assertEqual(self.result(stdout=b'- V e r i l a t i o n report\n')['classification'], 'no_warnings')

    def test_every_listed_defect_and_all_width_prefixes_fatal(self):
        for name in sorted(FATAL | {'WIDTH', 'WIDTHEXPAND', 'WIDTHTRUNC', 'WIDTHCONCAT', 'WIDTHNEW'}):
            with self.subTest(name=name):
                result = self.rejection(warning(name))
                self.assertEqual(result['fatal_class_counts'], {name: 1})

    def test_stdout_warning_cannot_hide_fatal(self):
        self.assertEqual(self.rejection(b'', stdout=warning('LATCH'))['fatal_class_counts'], {'LATCH': 1})

    def test_every_error_including_old_warning_trailer_is_fatal(self):
        for raw in (b'%Error: syntax error\n', warning('UNUSEDSIGNAL') + b'%Error: Exiting due to 1 warning(s)\n'):
            with self.subTest(raw=raw):
                result = self.rejection(raw)
                self.assertEqual(result['error_streams'], ['stderr'])
        self.assertEqual(self.rejection(b'', stdout=b'%Error: failure\n')['error_streams'], ['stdout'])

    def test_nonzero_signal_and_bool_exit_are_not_style_passes(self):
        for code in (1, 2, -9):
            with self.subTest(code=code):
                self.assertEqual(self.rejection(warning('UNUSEDSIGNAL'), code=code)['returncode'], code)
        with self.assertRaises(LintClassError):
            self.result(code=False)

    def test_unknown_class_is_not_allowlisted_by_manifest(self):
        result = self.rejection(warning('NEWFUTURE'), manifest={'allow_warnings': ['NEWFUTURE']})
        self.assertEqual(result['unknown_class_counts'], {'NEWFUTURE': 1})

    def test_pinmissing_and_undriven_unproven_claims_do_not_waive(self):
        for name in ('PINMISSING', 'UNDRIVEN'):
            with self.subTest(name=name):
                result = self.rejection(warning(name), manifest={'intentionally_open_outputs': ['fixture.port'],
                    'unused_signals': ['fixture.signal'], 'lint_baseline': {'review': 'PASS_claim'}})
                self.assertEqual(result['fatal_class_counts'], {name: 1})

    def test_malformed_and_hidden_headers_fail(self):
        for raw in (b'%Warning: no class\n', b'%Warning-: empty class\n', b'%Warning-width: lowercase\n',
                    b'%Warning-UNUSEDSIGNAL:\n', b'wrapper %Warning-WIDTH: hidden\n',
                    warning('UNUSEDSIGNAL', b'fixture: warning %Warning-WIDTH: hidden')):
            with self.subTest(raw=raw):
                self.assertTrue(self.rejection(raw)['malformed_diagnostics'])

    def test_continuation_source_excerpts_and_indented_headers(self):
        raw = b'  ' + warning('UNUSEDSIGNAL') + b'  42 | logic value; // %Warning-WIDTH: quoted source text\n      | ^~~~~\n ... For warning description see https://verilator.org/warn/UNUSEDSIGNAL\n'
        result = self.result(raw)
        self.assertEqual(result['class_counts'], {'UNUSEDSIGNAL': 1})

    def test_invalid_utf8_nul_ansi_fail_with_exact_sha(self):
        for raw in (b'\xff', b'\0', b'\x1b[31m' + warning('UNUSEDSIGNAL')):
            with self.subTest(raw=raw):
                self.assertEqual(self.rejection(raw)['stderr_sha256'], hashlib.sha256(raw).hexdigest())

    def test_logs_and_manifest_remain_unchanged(self):
        raw = warning('VARHIDDEN')
        before = json.dumps(self.manifest, sort_keys=True)
        self.result(raw)
        self.assertEqual(raw, warning('VARHIDDEN'))
        self.assertEqual(json.dumps(self.manifest, sort_keys=True), before)

    def test_nonfinite_manifest_and_nonbytes_logs_reject(self):
        with self.assertRaises(LintClassError):
            self.result(manifest={'number': float('nan')})
        with self.assertRaises(LintClassError):
            self.result('not bytes')


if __name__ == '__main__':
    unittest.main()
