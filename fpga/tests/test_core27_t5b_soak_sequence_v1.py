import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('_t5b_sequence', ROOT/'tools/prepare_core27_t5b_soak_sequence_v1.py')
SEQ = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SEQ)


class T5bSequence(unittest.TestCase):
    def test_lineage_and_distinct_cases(self):
        value = SEQ.plan()
        self.assertEqual(value['priority'], 'P1')
        self.assertEqual(value['lineage'], 'promoted-t5b')
        self.assertEqual(value['short_plan']['case_id'], '5f156dd8fc7c8530b5f9c697b2a4e9bb479ba7d919f74a855f47db93c97e9801')
        self.assertEqual(value['full_plan']['case_id'], '2730e05de298ecbf5d7125acb7d6859b581b21ed8c84fb1bbfd7d3aaccd007ba')
        self.assertTrue(value['frozen_crtmont_results_are_not_T5b_gates'])

    def test_fanout_and_continuous_are_separate(self):
        value = SEQ.plan()
        gates = {row['id']: row for row in value['gates']}
        self.assertEqual(len(gates), 17)
        self.assertEqual(len(gates['combine-chunks']['dependencies']), 10)
        for i in range(10):
            row = gates[f'chunk-{i:02d}']
            self.assertEqual(row['dependencies'], ['full-reference', 'chunk-runtime-admission'])
            self.assertEqual((row['start'], row['end']), (100*i, 100*(i+1)))
            self.assertTrue(row['independent'])
            self.assertEqual(row['controls'], [])
        continuous = gates['continuous-1000']
        self.assertNotIn('combine-chunks', continuous['dependencies'])
        self.assertEqual((continuous['reset_count'], continuous['reloads_between_operations']), (1, 0))
        self.assertEqual(continuous['state'], 'not_run_separate_required_gate')
        self.assertFalse(value['promotion_allowed'])

    def test_batch_prepares_all_eleven_but_dispatches_none(self):
        wanted = SEQ.plan()['full_plan']
        calls = []
        def stage(references, name, output, runtime_file, host, remote_root, controls):
            calls.append((name, host, controls))
            output.mkdir()
            (output/'serial-manifest.json').write_text('{}\n')
            return {'source_root': str(output/'source/fpga')}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'refs').mkdir()
            (root/'refs/generation.json').write_text(json.dumps({'case_id': wanted['case_id']}))
            (root/'runtime.json').write_text(json.dumps({'host': 'gfn16-azure-sim-f32'}))
            with mock.patch.object(SEQ, 'adapter', return_value=mock.Mock(stage=stage)), \
                 mock.patch.object(SEQ, 'plan', return_value={'full_plan': wanted}):
                result = SEQ.prepare_segments(root/'refs', root/'runtime.json', root/'output')
        self.assertEqual(len(result['segments']), 11)
        self.assertEqual([x[0] for x in calls], [f'chunk-{i:02d}' for i in range(10)]+['continuous'])
        self.assertTrue(all(x[1:] == ('gfn16-azure-sim-f32', False) for x in calls))
        self.assertTrue(all(x['ready_for_packaging'] and not x['ready_for_dispatch'] for x in result['segments']))

    def test_wrong_case_fails_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'refs').mkdir()
            (root/'refs/generation.json').write_text(json.dumps({'case_id': 'old-crtmont-case'}))
            (root/'runtime.json').write_text(json.dumps({'host': 'gfn16-pilot-c4d'}))
            with self.assertRaisesRegex(ValueError, 'EXACT_CASE'):
                SEQ.prepare_segments(root/'refs', root/'runtime.json', root/'output')
            self.assertFalse((root/'output').exists())


if __name__ == '__main__':
    unittest.main()
