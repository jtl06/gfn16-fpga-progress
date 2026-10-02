"""Exercise final guard allocation/tool calls and class binding, no HDL/math."""
import ast
from pathlib import Path
import sys
import unittest

from fpga.tools import native_threaded_wide_v2 as previous
from fpga.tools import native_threaded_wide_v3 as runner


class LiveWideGuardTests(unittest.TestCase):
    def test_actual_generated_poll_invokes_live_caps_and_tools_fail_closed(self):
        selected = runner.profile(runner.PROFILE_ID)
        static = runner.base().source_policy().host.static_module()
        raw = static.pinned('tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()
        text = runner.adapted_source(raw, selected)
        tree = ast.parse(text)
        execute = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'execute')
        guard = next(node for node in execute.body if isinstance(node, ast.FunctionDef) and node.name == 'guard')
        self.assertEqual([ast.unparse(node) for node in guard.body[:3]],
            ["execution_limits(profile['cpus'])", 'tools_for(profile)', 'guard_protected(profile)'])
        actual_poll_start = compile(ast.fix_missing_locations(ast.Module(body=guard.body[:3], type_ignores=[])), '<actual-wide-guard-prefix>', 'exec')
        calls = []
        def resources(cpus): calls.append(('resources', cpus)); return {}
        def tools(profile): calls.append(('tools', profile['profile_id'])); return {}
        namespace = dict(profile=selected, execution_limits=resources, tools_for=tools,
            guard_protected=lambda profile: calls.append(('protected', profile['profile_id'])))
        exec(actual_poll_start, namespace)
        self.assertEqual([value[0] for value in calls], ['resources', 'tools', 'protected'])
        for failure in ('execution_limits', 'tools_for'):
            calls.clear()
            def drift(value): raise ValueError('actual resource/tool drift')
            bad = dict(namespace, **{failure: drift})
            with self.subTest(failure=failure), self.assertRaisesRegex(ValueError, 'actual resource/tool drift'): exec(actual_poll_start, bad)
            self.assertFalse(any(value[0] == 'protected' for value in calls))
        expected_old = previous.adapted_source(raw, selected)
        normalized = text.replace(runner.SELF, previous.SELF).replace("        execution_limits(profile['cpus'])\n        tools_for(profile)\n", '')
        self.assertEqual(normalized, expected_old)

    def test_final_live_namespace_class_and_dependency_identity(self):
        module = runner.parent(runner.PROFILE_ID)
        self.assertEqual(module.SELF, runner.SELF)
        self.assertEqual(Path(module.__file__).name, 'native_threaded_wide_v3.py')
        for name in ('execute', 'load_manifest', 'check_sources', 'tools_for'):
            self.assertIs(getattr(module, name).__globals__, module.__dict__)
        module.LEASE_FDS = (7, 11)
        self.assertEqual(module.execute.__globals__['LEASE_FDS'], (7, 11))
        calls = []
        module.execution_limits = lambda cpus: calls.append(cpus)
        self.assertIs(module.execute.__globals__['execution_limits'], module.execution_limits)
        self.assertTrue(callable(module.MeasuredPopen))
        child = module.MeasuredPopen([sys.executable, '-B', '-c', 'pass'])
        self.assertEqual(child.wait(timeout=10), 0)
        self.assertIsNotNone(child.native_usage)
        self.assertEqual(runner.PINS, dict(previous.PINS, **{previous.SELF: runner.PRESERVED_WIDE_V2_SHA}))
        self.assertEqual(runner.profile(runner.PROFILE_ID), previous.profile(previous.PROFILE_ID))


if __name__ == '__main__':
    unittest.main()
