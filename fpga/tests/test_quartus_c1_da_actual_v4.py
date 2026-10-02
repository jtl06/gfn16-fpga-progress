"""Actual native C1 evidence plus tamper controls; no new vendor execution."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('c1_native_analysis', FPGA/'tools/analyze_c1_da_metadata_failure_v1.py')
q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)


class ActualTests(unittest.TestCase):
    def test_actual_wholecore_native_high_clearance_preserves_wrapper_failure(self):
        result = q.analyze()
        self.assertTrue(result['actual_native_design_assistant']['complete'])
        self.assertTrue(result['actual_native_design_assistant']['passed'])
        self.assertEqual(result['actual_native_design_assistant']['native_passed_rules'], 10)
        self.assertEqual(result['actual_native_design_assistant']['native_enabled_rules'], 13)
        self.assertEqual(result['actual_native_design_assistant']['high_severity_findings'], [])
        self.assertTrue(result['qsf_metadata_append_proof']['appended_during_native'])
        for name in ('original_gate_result_passed', 'native_gate_v3_executed', 'raw_settings_unchanged', 'fit_allowed', 'promotion_allowed', 'exhaustive_cross_block_coverage', 'whole_core_clock_claim'):
            self.assertFalse(result[name])

    def test_any_captured_native_context_setting_log_or_rule_tamper_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in q.REMOTE_RAW_PINS: shutil.copyfile(q.CAPTURE/name, root/name)
            for name in q.REMOTE_RAW_PINS:
                path = root/name; original = path.read_bytes(); path.write_bytes(original+b'\n')
                with self.subTest(name=name), self.assertRaises(ValueError): q.analyze(root)
                path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
