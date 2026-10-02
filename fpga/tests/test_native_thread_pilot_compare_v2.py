"""Pure role/accounting boundary checks; no native or arithmetic execution."""
import copy
import json
import unittest

from fpga.tools import native_thread_pilot_compare_v2 as compare
from fpga.tools import native_threaded_class_v1 as runtime


class AccountingBoundaryTests(unittest.TestCase):
    def values(self):
        a = json.loads((compare.HERE.parent/'artifacts/t5b-p3-threads1-burst23-v4/manifest.json').read_text())
        b = copy.deepcopy(a)
        old = next(name for name in b['sources'] if compare.PROVIDER.fullmatch(name))
        b['sources'].pop(old)
        b['sources'][old.replace('inputs-v4', 'inputs-v5')] = '0'*64
        return a, b

    def test_only_closed_accounting_snapshot_can_change(self):
        a, b = self.values()
        self.assertTrue(compare.role_equal(a, b))
        self.assertTrue(compare.role_equal(a, a))

    def test_role_runtime_profile_or_extra_payload_changes_rejected(self):
        a, original = self.values()
        for name in ('rtl/tb/native_runtime_context_v1.h', runtime.SELF,
                     'cloud/azure-burst16-static-profiles-v1.json', 'reference/unrecognized.json'):
            b = copy.deepcopy(original)
            b['sources'][name] = '1'*64
            with self.assertRaises(ValueError):
                compare.role_equal(a, b)
        b = copy.deepcopy(original)
        b['budget_source_members'].pop(next(iter(b['budget_source_members'])))
        with self.assertRaisesRegex(ValueError, '59-member'):
            compare.role_equal(a, b)

    def test_compiled_payload_or_multiple_snapshots_rejected(self):
        a, b = self.values()
        b['build']['cpp_source'] = next(name for name in b['sources'] if compare.PROVIDER.fullmatch(name))
        with self.assertRaisesRegex(ValueError, 'compiled'):
            compare.role_equal(a, b)
        a, b = self.values()
        name = next(name for name in b['sources'] if compare.PROVIDER.fullmatch(name))
        b['sources'][name.replace('inputs-v5', 'inputs-v6')] = '2'*64
        with self.assertRaisesRegex(ValueError, 'one closed'):
            compare.role_equal(a, b)


if __name__ == '__main__':
    unittest.main()
