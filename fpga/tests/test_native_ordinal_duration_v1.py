"""Source-only exact ordinal3300 timeout/contract/closed-package regressions."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch

from fpga.tools import native_ordinal_class_v1 as runtime
from fpga.tools import native_ordinal_duration_v1 as duration
from fpga.tools import native_ordinal_package_v1 as package
from fpga.tools import native_ordinal_stage_v1 as stage

FPGA = Path(__file__).resolve().parents[1]
RESULTS = FPGA / 'results/throughput-20260929'
ROLES = ('s4-aw5-p16-ordinal-positive-native-v1',
         's4-aw5-p16-ordinal-negative-native-v1',
         's4-aw5-p8-ordinal-negative-native-v1')
PACKET = RESULTS / 'native-ordinal-duration-v1/packet-positive01'


def role(name):
    directory = RESULTS / name
    return json.loads((directory / 'manifest.json').read_text()), directory / 'inputs/fpga'


class OrdinalDurationTests(unittest.TestCase):
    def test_three_actual_frozen_full_count_contracts(self):
        for name in ROLES:
            manifest, root = role(name)
            receipt = duration.validate(manifest, root, require_policy=False)
            self.assertEqual(receipt['shape'], duration.SHAPE)
            self.assertEqual(len(manifest['steps']), 1)
            manifest['runtime_duration'] = duration.descriptor(manifest)
            duration.validate(manifest, root)

    def test_exact_source_argv_output_count_and_single_model(self):
        manifest, _ = role(ROLES[0])
        manifest['runtime_duration'] = duration.descriptor(manifest)
        mutations = [lambda m: m['steps'].append(copy.deepcopy(m['steps'][0])),
                     lambda m: m['steps'][0]['argv'].append('--short'),
                     lambda m: m['steps'][0].update(expected_returncode=1),
                     lambda m: m['steps'][0].update(expected_stdout='shortened\n'),
                     lambda m: m['build']['parameters'].update(P=8),
                     lambda m: m['build']['parameters'].update(CONTEXTS=2),
                     lambda m: m['sources'].update({m['build']['cpp_source']: '0' * 64}),
                     lambda m: m['runtime_duration']['shape'].update(model_command_seconds=3301),
                     lambda m: m['probe']['expected_json'].update(model_threads=2)]
        for mutate in mutations:
            modified = copy.deepcopy(manifest)
            mutate(modified)
            with self.assertRaises((ValueError, KeyError)):
                duration.validate(modified)
        with self.assertRaises(ValueError):
            duration.validate(manifest, host='gfn16-azure-sim-f32')

    def test_only_exact_declared_model_gets3300(self):
        manifest, _ = role(ROLES[0])
        receipt = duration.validate(manifest, require_policy=False)
        step = manifest['steps'][0]
        self.assertEqual(duration.command_seconds(step['name'], ['/built/model', '--ordinal'], 0, receipt), 3300)
        for name in ('lint', 'build', 'probe', 'verilator-version', 'compiler-version', 'other-model'):
            self.assertEqual(duration.command_seconds(name, ['anything'], 0, receipt), 1800)
        for argv, expected in [(['/built/model', '--ordinal-negative'], 0),
                               (['/built/model', '--ordinal'], 1),
                               (['/built/model', '--ordinal'], False)]:
            with self.assertRaises(ValueError):
                duration.command_seconds(step['name'], argv, expected, receipt)

    def test_typed_negative_is_not_raw_nonzero(self):
        for name in ROLES[1:]:
            manifest, _ = role(name)
            step = manifest['steps'][0]
            self.assertEqual(step['expected_returncode'], 1)
            self.assertEqual(step['expected_stdout'], '')
            self.assertEqual(step['expected_stderr'], 'S4_LONG_ORDINAL_TYPED expected=65541 actual=65540\n')
            receipt = duration.validate(manifest, require_policy=False)
            self.assertEqual(duration.command_seconds(step['name'], ['/built/model', '--ordinal-negative'], 1, receipt), 3300)
            modified = copy.deepcopy(manifest)
            modified['steps'][0]['expected_stderr'] += 'ignored failure\n'
            with self.assertRaises(ValueError):
                duration.validate(modified, require_policy=False)

    def test_actual_generated_overall_timer_wins_aggregate(self):
        raw = runtime.base.host.static_module().pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
        text = runtime.adapted_source(raw, runtime.profile('gcp-c4d-static01-v1'))
        tree = ast.parse(text)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'require'
                 and len(node.args) > 1 and isinstance(node.args[1], ast.Constant)]
        def predicate(label, elapsed, **values):
            expression = next(node.args[0] for node in calls if node.args[1].value == label)
            namespace = dict(time=types.SimpleNamespace(monotonic=lambda: elapsed), begin=0, started=0, **values)
            return eval(compile(ast.Expression(expression), '[actual ordinal guard]', 'eval'), namespace)
        self.assertTrue(predicate('command timeout', 3299, command_limit=3300))
        self.assertFalse(predicate('command timeout', 3300, command_limit=3300))
        self.assertFalse(predicate('command timeout', 1800, command_limit=1800))
        self.assertTrue(predicate('overall timeout', 3599))
        self.assertFalse(predicate('overall timeout', 3600))
        # A model still within its3300 timer cannot escape the accumulated
        # compilation+model3600 bound. Kill-group/compile lock remain exact.
        self.assertFalse(predicate('overall timeout', 2000 + 1600))
        self.assertIn('deadline = time.monotonic() + 1800', text)
        self.assertIn('os.killpg(child.pid, signal.SIGKILL)', text)
        self.assertIn('check_sources(root, manifest[\'sources\'])', text)
        self.assertIn('command_seconds=1800, model_command_seconds=3300, overall_seconds=3600', text)

    def test_namespace_profile_and_live_lease_visibility(self):
        for name in runtime.SELECTIONS:
            module = runtime.parent(name)
            self.assertIs(module.execute.__globals__, module.__dict__)
            self.assertIs(module.load_manifest.__globals__, module.__dict__)
            module.LEASE_FDS = (42,)
            self.assertEqual(module.execute.__globals__['LEASE_FDS'], (42,))
            self.assertEqual(module.SELF, runtime.SELF)
            self.assertEqual(set(module.PROFILES), {'gfn16-pilot-c4d'})
        for name in ('azure-burst16-static01-v1', 'gcp-c4d-static24g01-v1'):
            with self.assertRaises(ValueError):
                runtime.profile(name)

    def test_actual_archive_safe_inspection_and_unchanged_source_contract(self):
        preparation = json.loads((PACKET / 'preparation.json').read_text())
        _, ticket, manifest, selected = stage.worker().inspect_archive(
            PACKET / 'package.tar.gz', preparation['archive_sha256'], preparation['ticket_sha256'])
        original, _ = role(ROLES[0])
        self.assertEqual(ticket['max_seconds'], 3700)
        self.assertEqual(ticket['runtime_duration'], duration.SHAPE)
        self.assertEqual(selected['memory_bytes'], 8 << 30)
        for name in ('build', 'probe', 'steps'):
            self.assertEqual(manifest[name], original[name])
        duration.validate(manifest, PACKET / 'capture/source/fpga')

    def test_actual_unpacked_runtime_source_identity_before_any_native_work(self):
        root = PACKET / 'capture/source/fpga'
        path = root / 'tools/native_ordinal_class_v1.py'
        spec = importlib.util.spec_from_file_location('_unpacked_ordinal', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        parent = module.parent('gcp-c4d-static01-v1')
        manifest = json.loads((PACKET / 'manifest.json').read_text())
        parent.check_sources(root, manifest['sources'])
        self.assertEqual(Path(parent.__file__).resolve(), path.resolve())
        self.assertIs(parent.execute.__globals__, parent.__dict__)
        manifest['sources']['rtl/tb/stream27_host_chain_v1.cpp'] = '0' * 64
        with self.assertRaises(ValueError):
            parent.check_sources(root, manifest['sources'])

    def test_package_run_shape_guard_and_3715_budget_unchanged(self):
        worker = package.worker()
        budget = json.loads((RESULTS / 'gcp-host-hours-1518-v1/budget-v2.json').read_text())
        worker.budget_check(budget)
        self.assertEqual(stage.SHAPE['outer_seconds'] + stage.SHAPE['stop_grace_seconds'], 3715)
        self.assertEqual(stage.SHAPE, duration.SHAPE)
        text = package.ordinal_source(package.load('native_static_package_v1.py', package.STATIC_SHA).adapted_source(
            (FPGA / 'tools/native_package_v1.py').read_bytes()))
        self.assertIn("ticket['runtime_duration']==duration_policy.SHAPE", text)
        self.assertIn('duration_policy.validate(m,source,profile[\'host\'])', text)
        with self.assertRaises(ValueError):
            package.prepare(None, None, 'gcp-c4d-static01-v1', 'unused', 'lint', None, None)


if __name__ == '__main__':
    unittest.main()
