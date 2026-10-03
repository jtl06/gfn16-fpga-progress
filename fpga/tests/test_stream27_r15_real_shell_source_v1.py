import copy
import unittest
from fpga.reference.stream27_r15_all_io_bind import prepare
from fpga.reference.stream27_r15_pcie_shell_bind_v1 import bind


class Shell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent=prepare(65536,p=16,contexts=2,fixed_schedule=1,lean_build=1,
          progress_watchdog=1,storage_to_ram=1,direct_cold=1,pcie_shell=0)
        cls.shell=bind(cls.parent,pcie_shell=1)

    def test_off_literal_and_enabled_source_partition(self):
        self.assertEqual(bind(self.parent),self.parent)
        b=self.shell;s=b['r15_real_shell']
        for name,text in self.parent['files'].items():self.assertEqual(b['files'][name],text)
        self.assertEqual(b['parameters'],{})
        self.assertEqual(s['effective_parameters']['PCIE_SHELL'],1)
        self.assertEqual(s['effective_parameters']['EPOCH_SEED0'],0)
        self.assertEqual(s['effective_parameters']['EPOCH_SEED1'],0)
        self.assertEqual((len(s['application_sources']),len(s['guard_sources']),len(s['board_sources'])),(70,1,1))
        self.assertEqual(len(s['vendor_sources']),345)
        self.assertEqual(len(s['qip_roots']),5)
        self.assertEqual(len(s['generated_custom_copies']),71)
        self.assertFalse(s['vendor_simulation_ready'])
        self.assertFalse(s['fit_qualified'])

    def test_clocks_and_actual_aperture_wiring_are_distinct_scopes(self):
        s=self.shell['r15_real_shell']
        self.assertTrue(s['aperture_wiring']['full64_before_guard'])
        self.assertEqual(s['clock_proof']['core_period_ns'],12)
        self.assertEqual(s['base_sdc'].count('create_clock'),2)
        self.assertNotIn('VIRTUAL_PIN ON',s['pin_qsf'])
        self.assertEqual(len(s['generation_diagnostics']['warnings']),41)
        self.assertFalse(s['automatic_link_retrain_or_FLR_recovery'])

    def test_uncaptured_parameter_and_application_source_refused(self):
        p=copy.deepcopy(self.parent);p['parameters']['EPOCH_SEED0']=1
        with self.assertRaisesRegex(ValueError,'UNCAPTURED_PARAMETERS'):bind(p,pcie_shell=1)
        p=copy.deepcopy(self.parent);p['files'][p['top']+'.sv']+='\n// drift\n'
        with self.assertRaisesRegex(ValueError,'LITERAL_CAPTURED_APPLICATION'):bind(p,pcie_shell=1)
        with self.assertRaisesRegex(ValueError,'PCIE_FLAG'):bind(self.parent,pcie_shell=True)
