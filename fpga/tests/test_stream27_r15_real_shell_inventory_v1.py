import copy
import unittest
from reference import stream27_r15_real_shell_inventory_v1 as inventory


class SourceInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = inventory.source.prepare(65536, fixed_schedule=1,
            lean_build=1, progress_watchdog=1, storage_to_ram=1,
            direct_cold=1, pcie_shell=1)
        cls.project = inventory.ROOT/inventory.PROJECT
        cls.spec = inventory.build(cls.bundle, cls.project)

    def test_declared_source_scope_and_retained_compute(self):
        s = self.spec
        self.assertEqual(s['schema'], 'prefit-structural-inventory-v1')
        self.assertEqual(len(s['transfers']), 38)
        self.assertEqual(s['source_owner_binding']['retained_compute_transfers'], 26)
        self.assertEqual(s['identity']['parameters'], {})
        self.assertFalse(any(x['kind']=='external_virtual_io' for x in s['exclusions']))
        self.assertFalse(s['source_owner_binding']['old_single_clock_source_inventory_checker_applicable'])
        self.assertEqual(s['clock_domains']['hip_period_ns'], 4)
        self.assertEqual(s['clock_domains']['core_period_ns'], 12)
        self.assertFalse(inventory.check_anchors(s, self.project)['fit_allowed'])

    def test_anchor_and_project_identity_tampering_refused(self):
        s = copy.deepcopy(self.spec)
        s['transfers'][-1]['exception']['contract_anchors'][0]['text'] += ' bad'
        with self.assertRaisesRegex(ValueError, 'CONTRACT_ANCHOR'):
            inventory.check_anchors(s, self.project)
        b = copy.deepcopy(self.bundle)
        b['generated_sha256'][b['top']+'.sv'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'EXACT_CORRECTED_PROJECT'):
            inventory.build(b, self.project)


if __name__ == '__main__':
    unittest.main()
