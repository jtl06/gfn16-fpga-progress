"""Pure identity boundary for the final live-guard wide sample comparator."""
import copy
import json
import unittest

from fpga.reference import core27_t5b_thread_wide_pilot_v1 as recipe
from fpga.tools import native_threaded_wide_v3 as runner
from fpga.tools import native_thread_wide_compare_v3 as compare


class LiveGuardComparisonTests(unittest.TestCase):
    def test_only_final_live_runner_controls_can_form_matched_samples(self):
        self.assertEqual(compare.RUNTIME_SHA, runner.sha(runner.HERE / 'native_threaded_wide_v3.py'))
        role = json.loads((recipe.ROOT / compare.ROLE_SOURCE).read_text())['sources']
        manifests = []
        for count in (2, 4, 8):
            _, manifest = recipe.recipe(count)
            manifest['budget_source_members'] = role
            manifest['sources'].update(runner.PINS)
            manifest['sources'][runner.SELF] = compare.RUNTIME_SHA
            manifest['sources']['results/throughput-20260929/core27-t5b-thread-wide-source-v1/execution-inputs-v1/provider.json'] = '0' * 64
            manifests.append(manifest)
        self.assertTrue(compare.role_equal(manifests[0], manifests[1]))
        self.assertTrue(compare.role_equal(manifests[0], manifests[2]))
        for name in (runner.SELF, 'tools/native_threaded_wide_v2.py', 'tools/native_threaded_wide_v1.py', runner.PROFILE_SOURCE):
            changed = copy.deepcopy(manifests[2]); changed['sources'][name] = '0' * 64
            with self.subTest(name=name), self.assertRaises(ValueError): compare.role_equal(manifests[0], changed)


if __name__ == '__main__':
    unittest.main()
