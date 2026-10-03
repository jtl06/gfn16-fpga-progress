import copy
import unittest
from reference import stream27_r15_all_shell_bind as shell


class ShellIntegrationPreparation(unittest.TestCase):
    def test_disabled_literal_field100_and_existing_modes(self):
        for n in (256, 65536):
            parent = shell.io.compute.fixed.capture(n)
            self.assertEqual(shell.prepare(n), parent)
            flags = dict(fixed_schedule=1, lean_build=1,
                         progress_watchdog=1, storage_to_ram=1)
            for direct in (0, 1):
                self.assertEqual(shell.prepare(n, direct_cold=direct, **flags),
                                 shell.io.prepare(n, direct_cold=direct, **flags))

    def test_no_silent_direct_enable_or_premature_shell(self):
        with self.assertRaisesRegex(ValueError, 'REQUIRES_DIRECT_COLD'):
            shell.prepare(256, pcie_shell=1)
        if not shell.SOURCE_FROZEN:
            with self.assertRaisesRegex(ValueError, 'REAL_SHELL_NOT_FROZEN'):
                shell.prepare(256, direct_cold=1, pcie_shell=1)

    def test_actual_source_locked_system_is_distinct_from_native_application(self):
        if not shell.SOURCE_FROZEN:
            self.skipTest('Real source not frozen')
        flags = dict(fixed_schedule=1, lean_build=1, progress_watchdog=1,
                     storage_to_ram=1, direct_cold=1, pcie_shell=1)
        out = shell.prepare(65536, **flags)
        direct = shell.io.prepare(65536, **dict(flags, pcie_shell=0))
        self.assertEqual(len(out['files']), 72)
        self.assertEqual(out['parameters'], {})
        self.assertEqual(out['geometry'], direct['geometry'])
        for name, text in direct['files'].items():
            self.assertEqual(out['files'][name], text)
        real = out['r15_real_shell']
        self.assertEqual(len(real['vendor_sources']), 345)
        self.assertEqual(len(real['qip_roots']), 5)
        self.assertEqual(len(real['generated_custom_copies']), 71)
        self.assertEqual(real['effective_parameters']['EPOCH_SEED0'], 0)
        self.assertEqual(real['effective_parameters']['EPOCH_SEED1'], 0)
        self.assertTrue(real['aperture_wiring']['full64_before_guard'])
        self.assertEqual(real['clock_proof']['core_period_ns'], 12)
        self.assertFalse(real['vendor_simulation_ready'])
        self.assertFalse(real['fit_qualified'])
        self.assertFalse(out['r15_all_shell']['promotion_allowed'])
        for name, text in out['files'].items():
            self.assertEqual(out['generated_sha256'][name], shell.sha(text))
        for path, pin in out['source_sha256'].items():
            self.assertEqual(pin, shell.sha((shell.ROOT/path).read_bytes()))
        with self.assertRaisesRegex(ValueError, 'UNCAPTURED_PARAMETERS'):
            shell.prepare(256, **flags)
        with self.assertRaisesRegex(ValueError, 'UNCAPTURED_PARAMETERS'):
            shell.prepare(65536, **dict(flags, lean_build=0))

    def test_fixed_qsys_parameter_contract_and_identity_refusals(self):
        # Metadata-only contract fixture. This is NOT generated vendor IP,
        # a runnable shell, source readiness or hardware qualification.
        core = shell.io.prepare(65536, fixed_schedule=1, lean_build=1,
                                progress_watchdog=1, storage_to_ram=1,
                                direct_cold=1)
        chosen = dict(zip(shell.io.compute.FLAGS, (1, 1, 1, 1, 1, 1)))
        out = copy.deepcopy(core)
        out.update(top='metadata_contract_fixture_only', parameters={})
        out['r15_host_link']['real_pcie_ip_ready'] = True
        effective = dict(core['parameters'], PCIE_SHELL=1,
                         EPOCH_SEED0=0, EPOCH_SEED1=0)
        out['r15_real_shell'] = dict(parameter_binding='source-locked-qsys',
                                     effective_parameters=effective)
        real, actual = shell._validate_shell(core, out, chosen)
        self.assertEqual(real['parameter_binding'], 'source-locked-qsys')
        self.assertEqual(actual, effective)
        mutants = []
        bad = copy.deepcopy(out)
        bad['parameters'] = {'AW': 16}
        mutants.append((bad, 'NO_HDL_OVERRIDES'))
        for key, value, why in [('LEAN_BUILD', 0, 'FLAG_FORWARDING'),
                                ('AW', 8, 'PARAMETER_IDENTITY'),
                                ('EPOCH_SEED0', 65534, 'EPOCH_IDENTITY')]:
            bad = copy.deepcopy(out)
            bad['r15_real_shell']['effective_parameters'][key] = value
            mutants.append((bad, why))
        bad = copy.deepcopy(out)
        first = next(iter(core['files']))
        bad['files'][first] += '\n// identity drift\n'
        mutants.append((bad, 'LITERAL_DIRECT_COMPONENT'))
        bad = copy.deepcopy(out)
        bad['geometry']['warm_interval'] += 1
        mutants.append((bad, 'INTERNAL_CALENDAR'))
        bad = copy.deepcopy(out)
        bad['r15_host_link']['real_pcie_ip_ready'] = False
        mutants.append((bad, 'IP_CDC_IO_CONSTRAINTS'))
        for bad, why in mutants:
            with self.subTest(why=why), self.assertRaisesRegex(ValueError, why):
                shell._validate_shell(core, bad, chosen)


if __name__ == '__main__':
    unittest.main()
