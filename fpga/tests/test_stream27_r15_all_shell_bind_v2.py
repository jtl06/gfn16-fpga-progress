import copy
import unittest
from reference import stream27_r15_all_shell_bind_v2 as current


class RegisteredCreditShell(unittest.TestCase):
    def test_disabled_source_cohorts_remain_literal(self):
        for n in (256, 65536):
            self.assertEqual(current.prepare(n), current.previous.prepare(n))
            for direct in (0, 1):
                flags = dict(fixed_schedule=1, lean_build=1,
                             progress_watchdog=1, storage_to_ram=1,
                             direct_cold=direct)
                self.assertEqual(current.prepare(n, **flags),
                                 current.previous.prepare(n, **flags))

    def test_actual_project_identity_and_registered_credit_delta(self):
        flags = dict(fixed_schedule=1, lean_build=1, progress_watchdog=1,
                     storage_to_ram=1, direct_cold=1, pcie_shell=1)
        out = current.prepare(65536, **flags)
        old = current.previous.prepare(65536, **flags)
        changed = [n for n in out['files'] if out['files'][n] != old['files'][n]]
        self.assertEqual(changed, ['genefer_stream27_r15_dma_aperture_v1.sv'])
        self.assertEqual(out['geometry'], old['geometry'])
        self.assertEqual(out['parameters'], {})
        self.assertEqual(len(out['files']), 72)
        self.assertTrue(out['r15_all_shell']['predecessor_SCC_not_admissible'])
        self.assertFalse(out['r15_all_shell']['promotion_allowed'])
        guard = out['files'][changed[0]]
        self.assertIn('wire response_credit=(rd_expected!=0);', guard)
        self.assertNotIn('wire response_credit=(rd_expected!=0) || down_rd_fire;', guard)
        base = current.ROOT/'results/throughput-20260929/trackS-r15-real-pcie-shell-v2/physical-source-v4/project'
        import json
        manifest = json.loads((base/'manifest.json').read_bytes())
        self.assertEqual(manifest['source_sha256'], out['generated_sha256'])
        self.assertEqual(manifest['r15_real_shell']['effective_parameters'],
                         out['r15_real_shell']['effective_parameters'])
        self.assertFalse(out['r15_real_shell']['vendor_simulation_ready'])

    def test_uncaptured_geometry_flags_and_boolean_refused(self):
        flags = dict(fixed_schedule=1, lean_build=1, progress_watchdog=1,
                     storage_to_ram=1, direct_cold=1, pcie_shell=1)
        for n, changes in ((256, {}), (65536, {'lean_build': 0})):
            with self.assertRaisesRegex(ValueError, 'UNCAPTURED_PARAMETERS'):
                current.prepare(n, **dict(flags, **changes))
        with self.assertRaisesRegex(ValueError, 'BOOLEAN_SWITCHES'):
            current.prepare(65536, **dict(flags, pcie_shell=True))
        with self.assertRaisesRegex(ValueError, 'REQUIRES_DIRECT_COLD'):
            current.prepare(65536, **dict(flags, direct_cold=0))


if __name__ == '__main__':
    unittest.main()
