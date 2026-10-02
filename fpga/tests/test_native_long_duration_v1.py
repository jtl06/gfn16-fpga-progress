"""Finite measured long-run shape: contracts, ancillary bounds and safe staging."""
import ast
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import types
import unittest
from fpga.tools import native_long_duration_v1 as duration
from fpga.tools import native_long_class_v1 as runtime
from fpga.tools import native_long_package_v1 as package
from fpga.tools import native_long_stage_v1 as stage

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'results/throughput-20260929/native-long-duration-v1'


class LongDurationTests(unittest.TestCase):
    def setUp(self):
        self.root = DATA / 't5b-bound-role/source/fpga'
        self.manifest = json.loads((DATA / 't5b-bound-role/manifest.json').read_text())
        evidence = self.manifest['runtime_duration']['evidence']
        self.values = {key: json.loads((self.root / item['path']).read_text()) for key, item in evidence.items()}
        self.pins = {key: item['sha256'] for key, item in evidence.items()}

    def test_actual_source_bound_measurement_fits_but_not_short_shape(self):
        result = duration.validate(self.manifest, self.root, 'gfn16-pilot-c4d')
        self.assertAlmostEqual(result['model_seconds_estimate'], 10229.42165832363)
        self.assertAlmostEqual(result['overall_seconds_estimate'], 10534.56909766163)
        self.assertGreater(result['model_seconds_estimate'], 1800)
        self.assertLess(result['overall_seconds_estimate'], 10700)

    def test_source_config_threads_steps_and_host_mismatches(self):
        for key, change in [('build', {'parameters': {'AW': 5}}), ('probe', {'expected_json': {'model_threads': 2}})]:
            m = copy.deepcopy(self.manifest); m[key].update(change)
            with self.assertRaises(ValueError): duration.assess(m, self.values, self.pins, 'gfn16-pilot-c4d')
        m = copy.deepcopy(self.manifest); m['steps'] *= 2
        with self.assertRaises(ValueError): duration.assess(m, self.values, self.pins, 'gfn16-pilot-c4d')
        m = copy.deepcopy(self.manifest); m['sources'][m['build']['cpp_source']] = '0' * 64
        with self.assertRaises(ValueError): duration.assess(m, self.values, self.pins, 'gfn16-pilot-c4d')
        with self.assertRaises(ValueError): duration.validate(self.manifest, self.root, 'gfn16-azure-sim-f32')

    def test_failed_gate_drift_bad_measurements_and_insufficient_margin(self):
        changes = [('pilot_gate', 'status', 'FAIL_expected_contracts'), ('pilot_report', 'status', 'running'),
                   ('pilot_gate', 'report_sha256', '0' * 64)]
        for evidence, key, value in changes:
            data = copy.deepcopy(self.values); data[evidence][key] = value
            with self.assertRaises(ValueError): duration.assess(self.manifest, data, self.pins, 'gfn16-pilot-c4d')
        for key, value in [('margin', 1.1), ('model_seconds_per_tick_upper_observed', float('nan')),
                           ('continuous_model_ticks', 999999999), ('continuous_operations', 1)]:
            data = copy.deepcopy(self.values); data['forecast']['forecast'][key] = value
            with self.assertRaises(ValueError): duration.assess(self.manifest, data, self.pins, 'gfn16-pilot-c4d')

    def test_shape_and_role_outcome_binding(self):
        m = copy.deepcopy(self.manifest); m['runtime_duration']['shape']['model_command_seconds'] += 1
        with self.assertRaises(ValueError): duration.validate(m, self.root, 'gfn16-pilot-c4d')
        m = copy.deepcopy(self.manifest); m['steps'][0]['validator']['config']['negative'] = 'boundary'
        with self.assertRaises(ValueError): duration.validate(m, self.root, 'gfn16-pilot-c4d')
        m = copy.deepcopy(self.manifest); m['runtime_duration']['evidence']['forecast']['sha256'] = '0' * 64
        with self.assertRaises(ValueError): duration.validate(m, self.root, 'gfn16-pilot-c4d')

    def test_actual_generated_timeout_expression_keeps_ancillary_short(self):
        policy = runtime.base.policy.policy
        raw = policy.host.static_module().pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
        text = runtime.adapted_source(raw, runtime.profile('gcp-c4d-static01-v1'))
        tree = ast.parse(text)
        tests = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == 'require' and len(n.args) > 1 and isinstance(n.args[1], ast.Constant)]
        def expression(label):
            return compile(ast.Expression(next(n.args[0] for n in tests if n.args[1].value == label)), '[actual generated guard]', 'eval')
        for name, elapsed, expected in [('soak-normal', 1801, True), ('soak-normal', 10449, True),
                                        ('soak-normal', 10450, False), ('build', 1801, False), ('lint', 1799, True)]:
            self.assertEqual(eval(expression('command timeout'), {'time': types.SimpleNamespace(monotonic=lambda: elapsed),
                'begin': 0, 'name': name, 'LONG_RECEIPT': {'model_step': 'soak-normal'}}), expected)
        self.assertFalse(eval(expression('overall timeout'), {'time': types.SimpleNamespace(monotonic=lambda:10700), 'started':0}))
        self.assertIn('deadline = time.monotonic() + 1800', text)
        self.assertIn('os.killpg(child.pid, signal.SIGKILL)', text)
        for name in runtime.SELECTIONS: runtime.parent(name)
        with self.assertRaises(ValueError): runtime.profile('azure-burst16-static01-v1')

    def test_actual_package_safe_stage_and_bound_ticket(self):
        p = DATA / 't5b-packet01'; result = json.loads((p / 'preparation.json').read_text())
        _, ticket, manifest, profile = stage.worker().inspect_archive(p / 'package.tar.gz', result['archive_sha256'], result['ticket_sha256'])
        self.assertEqual(ticket['max_seconds'], 10800)
        self.assertEqual(ticket['runtime_duration'], duration.SHAPE)
        self.assertEqual(profile['memory_bytes'], 8 << 30)
        self.assertEqual(manifest['steps'], self.manifest['steps'])
        self.assertEqual(manifest['build'], self.manifest['build'])

    def test_budget_covers_full_bound_not_legacy_3715(self):
        value = dict(provider='gcp', observed_at='2026-10-01T11:00:00+00:00', total_allowance_usd=100,
                     planning_usd_per_hour=1, remaining_after_reserves_usd=2, actual_billing=False, source_receipt_sha256='0'*64)
        now = datetime(2026,10,1,11,tzinfo=timezone.utc)
        with self.assertRaises(ValueError): package.long_budget_check(value, now)
        value['remaining_after_reserves_usd'] = 4; package.long_budget_check(value, now)
        value['provider'] = 'azure'
        with self.assertRaises(ValueError): package.long_budget_check(value, now)


if __name__ == '__main__': unittest.main()
