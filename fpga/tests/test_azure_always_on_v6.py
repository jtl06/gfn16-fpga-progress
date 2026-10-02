"""Idle is suppressed, while actual original financial/deadline states persist."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AlwaysOn(unittest.TestCase):
    def test_real_parent_transitions(self):
        base = load('financial', ROOT/'cloud/azure-sim-burst-guard-v4.py')
        child = load('always', ROOT/'cloud/azure-sim-burst-always-on-v6.py')
        cfg = json.loads((ROOT/'results/throughput-20260929/azure-sim-resize-r49-v1/guard-config-v4.json').read_text())
        initial = cfg['prior_running_seconds'] + 3000
        ordinary_now = cfg['rate_phase_epoch'] + 6000
        for case in ('idle', 'busy', 'deadline', 'running_budget'):
            with self.subTest(case=case):
                now = cfg['deadline_epoch'] if case == 'deadline' else ordinary_now
                running = cfg['max_running_seconds'] if case == 'running_budget' else initial
                old = dict(boot_id='same', uptime_seconds=2000, running_seconds=running,
                           idle_since_epoch=now-1900)
                args = (old, cfg, now, 2001, 'same', case == 'busy', 0)
                expected = base.transition(*args)
                actual = child.wrap_transition(base.transition)(*args)
                if case == 'idle':
                    self.assertEqual(expected['deallocate_reason'], 'idle_30m')
                    expected['deallocate_reason'] = None
                elif case in ('deadline', 'running_budget'):
                    self.assertEqual(actual['deallocate_reason'], 'wall_deadline' if case == 'deadline' else 'running_budget')
                expected['idle_deallocation_disabled_by_user'] = True
                self.assertEqual(actual, expected)

    def test_unknown_reason_is_not_suppressed(self):
        child = load('always_unknown', ROOT/'cloud/azure-sim-burst-always-on-v6.py')
        out = child.wrap_transition(lambda: {'deallocate_reason': 'unknown_hard_guard'})()
        self.assertEqual(out['deallocate_reason'], 'unknown_hard_guard')


if __name__ == '__main__':
    unittest.main()
