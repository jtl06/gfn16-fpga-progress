"""Pure/local fixture tests. No HDL, native vendor tools or cloud execution."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from synthesis.prepare import prepare as legacy_prepare
from synthesis.staged_fit import prepare, parse_reports, evaluate_policy, validate_policy, FIT_FLAGS


ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT/'synthesis/staged_policy_v1.json').read_text())


class StagedFitTests(unittest.TestCase):
    def test_area_heuristic_does_not_abort_known_broadcast(self):
        result = evaluate_policy({'alms_needed_packing_adjusted': 319502}, POLICY,
            'placement', design_class=POLICY['rules'][0]['design_class'])
        self.assertEqual(result['status'], 'continue')
        self.assertEqual(result['triggered'][0]['action'], 'advisory')
        self.assertFalse(result['route_failure'])

    def test_synthesis_estimate_is_not_placement_metric(self):
        result = evaluate_policy({'synthesis_alms_estimate': 392996}, POLICY,
            'placement', design_class=POLICY['rules'][0]['design_class'])
        self.assertEqual(result['triggered'], [])
        self.assertEqual(result['unknown_metrics'], ['alms_needed_packing_adjusted'])
        p = copy.deepcopy(POLICY); p['rules'][0]['metric'] = 'synthesis_alms_estimate'
        with self.assertRaisesRegex(ValueError, 'metric/phase'):
            validate_policy(p)

    def test_unknowns_and_wrong_class_never_abort(self):
        r = evaluate_policy({}, POLICY, 'placement', design_class='component')
        self.assertEqual(r['status'], 'continue')
        self.assertEqual(r['rules_not_applicable'], ['area-budget-heuristic'])

    def enforced(self):
        p = copy.deepcopy(POLICY); p['mode'] = 'enforce'
        p['approval'] = dict(reference='reviewed test fixture NOT execution authority', sha256='f'*64)
        r = p['rules'][0]; r['action'] = 'abort'; r['above'] = 330000
        r['calibration_evidence'] = [dict(path='fixture-'+outcome, sha256='1'*64,
            design_class=r['design_class'], outcome=outcome,
            metrics={r['metric']: value}) for outcome, value in
            [('routed', 319502), ('route_failed', 340000)]]
        return p

    def test_policy_abort_is_not_route_failure(self):
        p = self.enforced()
        r = evaluate_policy({'alms_needed_packing_adjusted': 340001}, p, 'placement',
                            design_class=p['rules'][0]['design_class'])
        self.assertEqual(r['status'], 'aborted_by_policy'); self.assertFalse(r['route_failure'])
        self.assertEqual(evaluate_policy({}, p, 'placement',
            design_class=p['rules'][0]['design_class'])['status'], 'continue')

    def test_enforcement_requires_approval_and_same_class_noncontradictory_evidence(self):
        for mutation in ('approval', 'passing', 'class', 'threshold', 'metric', 'failed'):
            with self.subTest(mutation=mutation):
                p = self.enforced(); rule = p['rules'][0]
                if mutation == 'approval': p['approval'] = {}
                if mutation == 'passing': rule['calibration_evidence'].pop(0)
                if mutation == 'class': rule['calibration_evidence'][0]['design_class'] = 'component'
                if mutation == 'threshold': rule['above'] = 280000
                if mutation == 'metric': rule['calibration_evidence'][0]['metrics'] = {}
                if mutation == 'failed': rule['above'] = 350000
                with self.assertRaises(ValueError): validate_policy(p)

    def test_invalid_numeric_data_refused(self):
        for v in (True, float('nan'), -1, '319502'):
            with self.subTest(value=v), self.assertRaises(ValueError):
                evaluate_policy({'alms_needed_packing_adjusted': v}, POLICY, 'placement',
                                design_class=POLICY['rules'][0]['design_class'])

    def test_fresh_clone_preserves_all_legacy_bytes_and_omits_database(self):
        with tempfile.TemporaryDirectory() as d:
            source, output = Path(d).resolve()/'old', Path(d).resolve()/'new'
            legacy_prepare(source, 'sdp_ram', aw=5, processors=4)
            (source/'db').mkdir(); (source/'db/ignored').write_text('not copied')
            before = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
            contract = prepare(source, output, POLICY)
            self.assertFalse(contract['driver_ready']); self.assertFalse(contract['execution_authorized'])
            self.assertFalse((output/'db').exists()); self.assertFalse((output/'staged-run.tcl').exists())
            for name in contract['input_sha256']:
                self.assertEqual((output/name).read_bytes(), before[Path(name)])
            self.assertEqual(before, {p.relative_to(source): p.read_bytes()
                                     for p in source.rglob('*') if p.is_file()})
            with self.assertRaises(FileExistsError): prepare(source, output, POLICY)
            with self.assertRaises(ValueError): prepare(source, source/'nested', POLICY)

    def test_capability_guard_no_early_place_or_unreviewed_tcl(self):
        cap = dict(tool_version='26.1.0 Build 110 Pro Edition',
                   execute_module_fit_args_reviewed=True, flow_help_sha256='a'*64,
                   fit_flags={s: dict(flag=f, help_sha256='b'*64) for s, f in FIT_FLAGS.items()})
        with tempfile.TemporaryDirectory() as d:
            d = str(Path(d).resolve())
            source = Path(d)/'source'; legacy_prepare(source, 'sdp_ram', aw=5)
            c = prepare(source, Path(d)/'new', POLICY, cap)
            self.assertTrue(c['driver_ready'])
            driver = (Path(d)/'new/staged-run.tcl').read_text()
            self.assertNotIn('early_place', driver); self.assertNotIn('asm', driver)
            self.assertIn('execute_module -tool fit -args "--$stage"', driver)
            bad = copy.deepcopy(cap); bad['execute_module_fit_args_reviewed'] = False
            with self.assertRaises(ValueError): prepare(source, Path(d)/'bad', POLICY, bad)
            bad = copy.deepcopy(cap); bad['fit_flags']['early_place'] = dict(flag='--early_place', help_sha256='c'*64)
            with self.assertRaises(ValueError): prepare(source, Path(d)/'bad2', POLICY, bad)
            self.assertFalse((Path(d)/'bad').exists())

    def test_stale_source_and_qsf_refused_before_output(self):
        with tempfile.TemporaryDirectory() as d:
            d = str(Path(d).resolve())
            source = Path(d)/'source'; legacy_prepare(source, 'sdp_ram', aw=5)
            qsf = source/'probe.qsf'; original = qsf.read_text()
            qsf.write_text(original.replace('NUM_PARALLEL_PROCESSORS 8', 'NUM_PARALLEL_PROCESSORS 9'))
            with self.assertRaises(ValueError): prepare(source, Path(d)/'bad', POLICY)
            qsf.write_text(original)
            next((source/'rtl').iterdir()).write_text('tampered')
            with self.assertRaises(ValueError): prepare(source, Path(d)/'bad2', POLICY)

    def test_archived_broadcast_metrics_keep_three_alm_counts_distinct(self):
        project = ROOT/'results/throughput-20260929/core27-r2-broadcast64-aws-fit-v1'
        self.assertTrue(project.exists(), 'source-backed calibration archive must exist')
        r = parse_reports(project); m = r['metrics']
        self.assertEqual(m['synthesis_alms_estimate'], 392996)
        self.assertEqual(m['alms_needed_packing_adjusted'], 319502)
        self.assertEqual(m['alms_placed_raw'], 365732)
        self.assertEqual((m['labs_used'], m['labs_available']), (41446, 42720))
        self.assertEqual((m['dsp_blocks_needed'], m['dsp_blocks_placed_raw']), (802, 819))
        self.assertEqual(m['m20k_used'], 1435)
        self.assertEqual((m['peak_short_demand_percent'], m['peak_long_demand_percent']), (110, 133))
        self.assertTrue(r['terminal_fit_success_observed']); self.assertTrue(r['place_report_observed'])

    def test_missing_reports_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as d:
            r = parse_reports(Path(d))
        self.assertIsNone(r['metrics']['lab_occupancy_percent'])
        self.assertIsNone(r['metrics']['peak_long_demand_percent'])
        self.assertFalse(r['terminal_fit_success_observed'])

    def test_outer_log_flat_archive_and_elapsed_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)/'project'; project.mkdir()
            (project/'probe.syn.summary').write_text('Synthesis Status : Successful\nLogic utilization estimate (in ALMs) : 10\n')
            log = Path(d)/'fit.log'
            log.write_text('Info (170192): Fitter placement operations ending: elapsed time is 00:00:10\n'
                'Info (16607): Fitter routing operations ending: elapsed time is 00:01:20\n'
                'Info (20215): Router estimated peak long high speed interconnect demand : 156% of right directional wire in region X0_Y1 to X2_Y3\n'
                'Error: An error occurred during routing\nError: Elapsed time: 00:01:40\n')
            r = parse_reports(project, [log]); m = r['metrics']
            self.assertEqual(m['synthesis_alms_estimate'], 10)
            self.assertEqual((m['route_seconds'], m['place_seconds'], m['route_to_place_time_ratio']), (80, 10, 8))
            self.assertEqual(m['peak_long_demand_percent'], 156)
            self.assertTrue(r['route_error_observed']); self.assertFalse(r['terminal_fit_success_observed'])
            self.assertTrue(any(x['kind'] == 'native_tool_elapsed_unassigned' and x['seconds'] == 100
                                for x in r['durations']))
            with log.open('a') as stream:
                stream.write('Info (16607): Fitter routing operations ending: elapsed time is 00:01:30\n')
            self.assertIsNone(parse_reports(project, [log])['metrics']['route_seconds'])

    def test_placement_failure_requested_labs_not_lab_occupancy(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d)/'fit.log'
            log.write_text('Error (25153): Fitter requires 44147 LABs to implement the design, but the device contains only 42720 LABs. Fitting has terminated due to high LAB utilization.\nError: An error occurred during placement\n')
            r = parse_reports(Path(d), [log])
            self.assertEqual(r['metrics']['placement_requested_labs_on_failure'], 44147)
            self.assertIsNone(r['metrics']['labs_used']); self.assertIsNone(r['metrics']['lab_occupancy_percent'])
            self.assertTrue(r['placement_error_observed']); self.assertFalse(r['route_error_observed'])

    def test_boundary_analysis_excludes_components_and_cancelled(self):
        from synthesis.staged_calibration import boundary_analysis, WHOLE64
        rows = [dict(design_class=cls, outcome=outcome, metrics={'peak_long_demand_percent': peak})
            for cls, outcome, peak in [(WHOLE64, 'routed', 133), (WHOLE64, 'route_failed', 148),
                                      (WHOLE64, 'aborted_by_policy', 200), ('component', 'routed', 156)]]
        result = boundary_analysis(rows)
        self.assertEqual((result['routed_count'], result['route_failed_count']), (1, 1))
        long = next(m for m in result['metrics'] if m['metric'] == 'peak_long_demand_percent')
        self.assertEqual(long['strict_above_threshold_empirical_interval'], [133, 148])
        self.assertFalse(long['threshold_enabled'])


if __name__ == '__main__':
    unittest.main()
