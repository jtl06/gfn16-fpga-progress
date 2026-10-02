"""Exact narrow callable-runtime comparison delta; no numeric/native replay."""
import copy
import json
import unittest

from fpga.reference import core27_t5b_thread_wide_pilot_v1 as recipe
from fpga.tools import native_threaded_wide_v2 as runner
from fpga.tools import native_thread_wide_compare_v2 as compare


class CallableWideComparisonTests(unittest.TestCase):
    def test_exact_successor_role_and_preserved_source_identity(self):
        self.assertEqual(compare.RUNTIME_SHA, runner.sha(runner.HERE / 'native_threaded_wide_v2.py'))
        self.assertEqual(compare.sha(compare.HERE / 'native_thread_wide_compare_v1.py'), compare.PRESERVED_COMPARISON_SHA)
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
        for member in (runner.SELF, 'tools/native_threaded_wide_v1.py', runner.PROFILE_SOURCE):
            bad = copy.deepcopy(manifests[1]); bad['sources'][member] = '0' * 64
            with self.subTest(member=member), self.assertRaises(ValueError): compare.role_equal(manifests[0], bad)


if __name__ == '__main__':
    unittest.main()
