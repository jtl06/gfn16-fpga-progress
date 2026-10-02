"""Host-only successor checks: no full-N numeric work or HDL on this host."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fpga.reference import root_lookahead_field_v2 as frozen
from fpga.reference import root_lookahead_field_host_v3 as host
from fpga.reference import root_lookahead_field_data_v3 as data


class FieldHost(unittest.TestCase):
    def tearDown(self):
        host._profile_id = None
        host._last_limits = None

    def test_arithmetic_code_and_defaults_are_identical_not_reimplemented(self):
        for name in host.ARITHMETIC:
            original, copy = getattr(frozen, name), host._arithmetic[name]
            self.assertIs(copy.__code__, original.__code__)
            self.assertEqual(copy.__defaults__, original.__defaults__)
            self.assertEqual(copy.__kwdefaults__, original.__kwdefaults__)
            self.assertIs(copy.__closure__, original.__closure__)
        self.assertIs(host._arithmetic['powers'], frozen.powers)
        self.assertIs(host._arithmetic['profile_word'], frozen.profile_word)
        self.assertIs(host._arithmetic['field_math'], frozen.field_math)

    def test_scalar_vector_bytes_equal_frozen_for_all_fields(self):
        for aw in (1, 5, 8):
            for index in range(3):
                with self.subTest(aw=aw, field=index):
                    old, _ = frozen.corpus(aw, index)
                    new, meta = host.corpus(aw, index)
                    self.assertEqual(new, old)
                    self.assertEqual(meta['frozen_arithmetic_parent_sha256'], host.PARENT_SHA)
                    self.assertEqual(meta['arithmetic_code_objects_unchanged'], list(host.ARITHMETIC))
                    self.assertIsNone(meta['full_numeric_limits'])

    def test_mac_and_unconfigured_full_numeric_gate_fail_before_work(self):
        with patch.object(host.platform, 'system', return_value='Darwin'):
            host.configure('gcp-c4d-static23-v1')
            with self.assertRaisesRegex(ValueError, 'admitted Linux'):
                host.numeric_gate(65536)
        host._profile_id = None
        with patch.object(host.platform, 'system', return_value='Linux'):
            with self.assertRaisesRegex(ValueError, 'admitted Linux'):
                host.numeric_gate(65536)

    def test_unknown_profile_host_and_actual_runtime_guard_reject(self):
        for profile in ('azure-f32-static01-v1', 'unknown', False):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                host.configure(profile)
        host.configure('gcp-c4d-static23-v1')
        with patch.object(host.platform, 'system', return_value='Linux'), \
             patch.object(host.platform, 'node', return_value='unrecognized'):
            with self.assertRaisesRegex(ValueError, 'actual numeric host'):
                host.numeric_gate(65536)
        with patch.object(host.platform, 'system', return_value='Linux'), \
             patch.object(host.platform, 'node', return_value='gfn16-pilot-c4d'), \
             patch.object(host.static, 'execution_limits', side_effect=ValueError('wrong cgroup')):
            with self.assertRaisesRegex(ValueError, 'wrong cgroup'):
                host.numeric_gate(65536)

    def test_recognized_profile_delegates_exact_runtime_guard_symbolically(self):
        for profile in sorted(host.ALLOWED):
            host.configure(profile)
            selected = host.static.profile(profile)
            marker = {'guard': profile}
            with patch.object(host.platform, 'system', return_value='Linux'), \
                 patch.object(host.platform, 'node', return_value=selected['host']), \
                 patch.object(host.static, 'execution_limits', return_value=marker) as guard:
                host.numeric_gate(65536)  # geometry/admission only, not a transform
                guard.assert_called_once_with(selected)
                self.assertIs(host._last_limits, marker)

    def test_scalar_cli_artifacts_are_fresh_pinned_and_not_native(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output, receipt = root / 'vectors.txt', root / 'receipt.json'
            value = data.generate(5, 0, 'gcp-c4d-static23-v1', output, receipt)
            self.assertEqual(output.read_text(), frozen.corpus(5, 0)[0])
            self.assertEqual(value['vector_sha256'], host.sha(output))
            self.assertFalse(value['numeric_full_N'])
            self.assertFalse(value['native_RTL_executed'])
            with self.assertRaisesRegex(ValueError, 'fresh'):
                data.generate(5, 0, 'gcp-c4d-static23-v1', output, receipt)


if __name__ == '__main__':
    unittest.main()
