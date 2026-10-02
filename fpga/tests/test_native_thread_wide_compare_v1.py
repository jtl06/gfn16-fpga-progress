"""Pure matched-source/accounting/measurement negatives, no native replay."""
import copy
import json
import unittest
from unittest.mock import patch

from fpga.reference import core27_t5b_thread_wide_pilot_v1 as recipe
from fpga.tools import native_threaded_wide_v1 as runner
from fpga.tools import native_thread_wide_compare_v1 as compare


class WideComparisonTests(unittest.TestCase):
    def values(self):
        result = []
        selected = runner.profile(runner.PROFILE_ID)
        base_role = json.loads((recipe.ROOT / compare.ROLE_SOURCE).read_text())['sources']
        for count in (2, 4, 8):
            _, manifest = recipe.recipe(count)
            manifest.update(host=selected['host'], cpu_profile=runner.PROFILE_ID, budget_source_members=base_role)
            manifest['sources'].update(runner.PINS)
            manifest['sources'][runner.SELF] = compare.RUNTIME_SHA
            manifest['sources']['results/throughput-20260929/core27-t5b-thread-wide-source-v1/execution-inputs-v1/provider.json'] = '0' * 64
            result.append(manifest)
        return result, selected

    def test_only_pinned_control_and_one_accounting_snapshot_can_differ(self):
        manifests, _ = self.values()
        original, changed = manifests[:2]
        old = next(name for name in changed['sources'] if compare.PROVIDER.fullmatch(name))
        changed['sources'].pop(old)
        changed['sources'][old.replace('inputs-v1', 'inputs-v2')] = '1' * 64
        self.assertTrue(compare.role_equal(original, changed))
        for name in ('rtl/tb/native_runtime_context_v1.h', runner.SELF, runner.PROFILE_SOURCE, 'unknown.json'):
            bad = copy.deepcopy(changed); bad['sources'][name] = '2' * 64
            with self.subTest(name=name), self.assertRaises(ValueError): compare.role_equal(original, bad)
        bad = copy.deepcopy(changed)
        bad['sources'][old.replace('inputs-v1', 'inputs-v3')] = '2' * 64
        with self.assertRaisesRegex(ValueError, 'one closed'): compare.role_equal(original, bad)
        bad = copy.deepcopy(changed); bad['budget_source_members'].pop(next(iter(bad['budget_source_members'])))
        with self.assertRaisesRegex(ValueError, 'original61'): compare.role_equal(original, bad)

    def test_observed_ratios_require_same_allocation_tools_and_build(self):
        manifests, selected = self.values()
        samples = []
        for count, manifest, wall, cpu in zip((2, 4, 8), manifests, (50., 30., 25.), (95., 115., 160.)):
            report = dict(tool_sha256={'compiler': '0' * 64}, sources=manifest['sources'])
            measured = dict(threads=count, wall_seconds=wall, cpu_seconds=cpu, compile_wall_seconds=80., peak_rss_kib=30000)
            samples.append((manifest, copy.deepcopy(selected), report, measured))
        with patch.object(compare, 'sample', side_effect=samples):
            result = compare.compare(*range(6))
        self.assertEqual(result['two_over_four_model_wall_ratio'], 50/30)
        self.assertEqual(result['two_over_eight_model_wall_ratio'], 2)
        self.assertEqual(result['eight_over_two_model_cpu_ratio'], 160/95)
        self.assertFalse(result['four_core_profile_admission'])
        self.assertFalse(result['long_campaign_admission'])
        for kind in ('host', 'profile', 'allocation', 'tool', 'build', 'step'):
            bad = copy.deepcopy(samples)
            if kind == 'host': bad[1][0]['host'] = 'other'
            elif kind == 'profile': bad[1][0]['cpu_profile'] = 'azure-burst16-static23-v1'
            elif kind == 'allocation': bad[1][1]['runtime_allocation']['cpus'] = [0, 1]
            elif kind == 'tool': bad[1][2]['tool_sha256']['compiler'] = '1' * 64
            elif kind == 'build': bad[1][0]['build']['cflags'].append('-O0')
            elif kind == 'step': bad[1][0]['steps'][0]['expected_stdout'] += 'extra'
            with self.subTest(kind=kind), patch.object(compare, 'sample', side_effect=bad), self.assertRaises(ValueError): compare.compare(*range(6))


if __name__ == '__main__':
    unittest.main()
