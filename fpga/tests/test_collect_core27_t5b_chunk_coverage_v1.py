"""Scalar metadata/hash combination controls; no oracle arithmetic."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('_ten_chunk_gate', ROOT / 'tools/collect_core27_t5b_chunk_coverage_v1.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture():
    lineage = MODULE.load(MODULE.REFERENCE, MODULE.REFERENCE_SHA)
    plan = lineage.reference().make_plan(16, 1000, 100, 100, 20261001, 604832956)
    result = []
    for index in range(10):
        result.append(dict(status='passed_soak_segment_boundary_replay', segment=f'chunk-{index:02d}',
            case_id=plan['case_id'], evidence_class='checkpoint_chunk_arithmetic_coverage',
            independent_gmpy2_boundary_replay=True, uninterrupted_1000_square_rtl=False,
            native_qualification_allowed=True, parent_manifest_sha256=lineage.FIT_SHA, operations=100,
            checkpoint_residue_sha256={str(k): f'{k:064x}' for k in (index * 100, (index + 1) * 100)}))
    return plan, result


class TenChunkMetadata(unittest.TestCase):
    def test_no_chunk_to_continuous_upgrade(self):
        result = MODULE.combine(*fixture())
        self.assertEqual(result['operations'], 1000)
        self.assertEqual(len(result['boundary_residue_sha256']), 11)
        self.assertFalse(result['uninterrupted_1000_square_rtl'])
        self.assertEqual(result['continuous_gate'], 'still_required')

    def test_missing_duplicate_or_wrong_case_reject(self):
        plan, rows = fixture()
        for altered in (rows[:-1], rows[:-1] + [rows[0]]):
            with self.assertRaises(ValueError):
                MODULE.combine(plan, altered)
        rows[1]['case_id'] = 'other'
        with self.assertRaises(ValueError):
            MODULE.combine(plan, rows)

    def test_adjacent_state_and_boundary_shape_reject(self):
        for mode in ('changed', 'missing', 'extra'):
            plan, rows = fixture()
            states = rows[1]['checkpoint_residue_sha256']
            if mode == 'changed':
                states['100'] = 'f' * 64
            elif mode == 'missing':
                states.pop('100')
            else:
                states['101'] = '0' * 64
            with self.assertRaises(ValueError):
                MODULE.combine(plan, rows)

    def test_unqualified_or_continuous_claim_reject(self):
        for key, value in [('independent_gmpy2_boundary_replay', False), ('uninterrupted_1000_square_rtl', True),
                           ('native_qualification_allowed', False), ('parent_manifest_sha256', 'other'),
                           ('operations', 99)]:
            plan, rows = fixture()
            rows[1][key] = value
            with self.assertRaises(ValueError):
                MODULE.combine(plan, rows)

    def test_incomplete_sequence_cannot_pass(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaisesRegex(ValueError, 'missing completed chunk'):
                MODULE.collect(empty, ROOT / 'queue/done/soak-t5b-aw16-full-reference-q3-v1.json')

    def test_preclaim_config_and_closed_runtime_mapping(self):
        config = json.loads((ROOT / 'results/throughput-20260929/soak-t5b-dependent-sequence-v1/chunk-preclaim-config-v1.json').read_text())
        with patch.object(MODULE, 'collect', return_value={'status': 'PASS_chunk_continuity_not_continuous_soak'}) as mocked:
            result = MODULE.validate_queue_chunks(config, {})
            self.assertEqual(result['status'], 'PASS_chunk_continuity_not_continuous_soak')
            mocked.assert_called_once()

    def test_preclaim_malformed_scope_rejects_before_artifacts(self):
        original = json.loads((ROOT / 'results/throughput-20260929/soak-t5b-dependent-sequence-v1/chunk-preclaim-config-v1.json').read_text())
        changed = []
        for key, value in [('schema', 'unknown'), ('case_id', 'other'), ('extra', 'unbound')]:
            config = deepcopy(original); config[key] = value; changed.append(config)
        config = deepcopy(original); config['chunk_identities'].pop(MODULE.IDS[0]); changed.append(config)
        config = deepcopy(original); config['runtime_by_id'][MODULE.IDS[7]] = MODULE.GCP_RUNTIME; changed.append(config)
        config = deepcopy(original); config['source_model_pins'].pop(MODULE.CPP); changed.append(config)
        config = deepcopy(original); config['source_model_build']['parameters']['AW'] = 5; changed.append(config)
        config = deepcopy(original); config['reference_ticket']['sha256'] = '0' * 64; changed.append(config)
        with patch.object(MODULE, 'collect', side_effect=AssertionError('must stop before artifact traversal')):
            for config in changed:
                with self.assertRaises(ValueError):
                    MODULE.validate_queue_chunks(config, {})


if __name__ == '__main__':
    unittest.main()
