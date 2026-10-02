"""Collected native timing/source metadata only, never numerical generation."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('_cross_chunk_duration', ROOT / 'tools/admit_core27_t5b_cross_chunks_v1.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CrossChunkDuration(unittest.TestCase):
    def test_actual_repaired_target_pass_admits100_not1000(self):
        result = MODULE.admission(ROOT / 'queue/done/soak-t5b-aw16-short-cross-burst16-q3-v2.json',
                                  ROOT / 'queue/done/soak-t5b-aw16-full-reference-q3-v1.json')
        self.assertEqual(result['compatible_hosts'], ['gfn16-azure-sim-f32'])
        self.assertLess(result['forecast']['chunk_command_seconds_estimate'], 1800)
        self.assertLess(result['forecast']['chunk_overall_seconds_estimate'], 3600)
        self.assertFalse(result['continuous_admitted'])
        self.assertFalse(result['forecast']['target_full_reference_replay_allowance_measured'])

    def test_failed_original_cannot_supply_duration(self):
        with self.assertRaisesRegex(ValueError, 'qualified repaired'):
            MODULE.admission(ROOT / 'queue/done/soak-t5b-aw16-short-cross-burst16-q3-v1.json',
                             ROOT / 'queue/done/soak-t5b-aw16-full-reference-q3-v1.json')

    def test_gcp_short_cannot_be_recast_as_target_measurement(self):
        with self.assertRaisesRegex(ValueError, 'qualified repaired'):
            MODULE.admission(ROOT / 'queue/done/soak-t5b-aw16-short-native-q3-v1.json',
                             ROOT / 'queue/done/soak-t5b-aw16-full-reference-q3-v1.json')


if __name__ == '__main__':
    unittest.main()
