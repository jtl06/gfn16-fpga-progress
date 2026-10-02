"""Pure report-fixture tests: no HDL or Quartus execution."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('setup_classes', Path(__file__).parents[1] / 'tools/summarize_setup_classes.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
CORNER = 'Slow 900mV 0C Model'
PATH = f'''Delay Model:
{CORNER}
Path #1: Setup slack is -0.125
; From Node ; feed_index|q ;
; To Node ; engine|arithmetic|out_error ;
; Clock Skew ; 0.000 ;
; Data Delay ; 1.000 ;
; Number of Logic Levels ; ; 3 ;
; SDC Exception ; None ;
;   Data Arrival Path
; Cell ; x ; x ; 0.400 ; x ; x ; x ;
; uTco ; x ; x ; 0.100 ; x ; x ; x ;
; IC ; x ; x ; 0.500 ; x ; x ; x ;
;  Required Path
Report Timing: Found 1 setup paths
'''


class SetupClassesTest(unittest.TestCase):
    def test_actual_verified_fit_retained_sample_is_not_global1000(self):
        root=Path(__file__).resolve().parents[1]/'queue/standing-fit-state/terminal/s4-p8-canonical-pipe-whole-10000-v1'
        value=MOD.analyze_verified_fit(root/'receipt.json',root/'evidence')
        self.assertEqual(value['period_ns'],10)
        self.assertEqual(value['design_scope'],'whole_core')
        self.assertEqual(value['coverage']['observations'],10)
        self.assertFalse(value['coverage']['exhaustive'])
        self.assertEqual(len(value['top5_classes']),1)
        self.assertEqual(value['top5_classes'][0]['worst']['slack_ns'],-2.813)
        self.assertLessEqual(len(value['top5_table'].encode()),1024)
        self.assertIn('retained setup sample',value['top5_table'])

    def test_fault_replica_and_unclassified_are_not_fake_distinct_classes(self):
        self.assertEqual(MOD.architecture(dict(from_node='fault_replicas|destination[0].fault_q',to_node='core|out_error')),'field_fault -> field_error')
        self.assertEqual(MOD.architecture(dict(from_node='unknown[0]',to_node='other[3]')),'other_unclassified -> other_unclassified')

    def fixture(self, root, text=PATH, phase='selected', period=9.0, name=None):
        archive = root / 'reports.tar.gz'
        with tarfile.open(archive, 'w:gz') as tf:
            body = text.encode()
            info = tarfile.TarInfo(name or f'audit/timing/{phase}-0-setup-paths.rpt')
            info.size = len(body)
            tf.addfile(info, io.BytesIO(body))
        receipt = root / 'receipt.json'
        data = dict(archive={'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()},
                    terminal_proven=True, original_unchanged=True, compiled_input_unchanged=True,
                    fit_commands=0, scope='component', original_tree_sha256='source', qdb_inventory_sha256='qdb',
                    timing={phase: {'corners': {CORNER: {'clock': {'period_ns': period}}}}})
        receipt.write_text(json.dumps(data))
        return receipt, archive

    def test_selected_period_scope_and_finite_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = MOD.analyze(*self.fixture(Path(tmp)), phase='selected')
        self.assertEqual(result['period_ns'], 9.0)
        self.assertEqual(result['design_scope'], 'component')
        self.assertEqual(result['coverage']['observations'], 1)
        self.assertNotIn('global4000_classes', result)
        self.assertEqual(result['top5_classes'][0]['worst']['slack_ns'], -.125)

    def test_zero_paths_explicit_not_timing_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = MOD.analyze(*self.fixture(Path(tmp), 'Report Timing: Found 0 setup paths'), phase='selected')
        self.assertEqual(result['coverage']['observations'], 0)
        self.assertFalse(result['coverage']['complete_nonempty_corner_coverage'])
        self.assertEqual(result['top5_classes'], [])
        self.assertNotIn('timing_closes', result)

    def test_missing_report_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'No matching'):
                MOD.analyze(*self.fixture(Path(tmp), name='unrelated.txt'), phase='selected')

    def test_invalid_period_rejected(self):
        for value in (None, 0, -1, True, float('nan')):
            with self.subTest(period=value), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(ValueError, 'Invalid audited'):
                    MOD.analyze(*self.fixture(Path(tmp), period=value), phase='selected')

    def test_hash_and_provenance_guards(self):
        for field, value in [('original_unchanged', False), ('fit_commands', 1), ('archive', {'sha256': 'wrong'})]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                receipt, archive = self.fixture(Path(tmp))
                data = json.loads(receipt.read_text())
                data[field] = value
                receipt.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    MOD.analyze(receipt, archive, phase='selected')

    def test_truncated_and_bad_delay_rejected(self):
        for text in (PATH.replace('Found 1', 'Found 2'), PATH.replace('0.500', '0.600')):
            with self.assertRaises(ValueError):
                MOD.parse(text)

    def test_partial_corner_coverage_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt, archive = self.fixture(Path(tmp))
            data = json.loads(receipt.read_text())
            data['timing']['selected']['corners']['Fast 900mV 0C Model'] = {'clock': {'period_ns': 9.0}}
            receipt.write_text(json.dumps(data))
            result = MOD.analyze(receipt, archive, phase='selected')
        self.assertFalse(result['coverage']['complete_nonempty_corner_coverage'])

    def test_mixed_period_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt, archive = self.fixture(Path(tmp))
            data = json.loads(receipt.read_text())
            data['timing']['selected']['corners']['Fast 900mV 0C Model'] = {'clock': {'period_ns': 10.0}}
            receipt.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'inconsistent'):
                MOD.analyze(receipt, archive, phase='selected')


if __name__ == '__main__':
    unittest.main()
