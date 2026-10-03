"""Application source checks only; neither HDL nor vendor simulation."""
import unittest
from fpga.reference.stream27_r15_all_io_bind import prepare
from fpga.reference.stream27_r15_pcie_shell_bind_v1 import application,bind


class Source(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent=prepare(n=256,p=16,contexts=2,fixed_schedule=1,lean_build=1,
          progress_watchdog=1,storage_to_ram=1,direct_cold=1,pcie_shell=0)

    def test_off_literal_and_real_not_ready(self):
        self.assertEqual(bind(self.parent),self.parent)
        with self.assertRaisesRegex(ValueError,'REAL_SHELL_NOT_READY'):
            bind(self.parent,pcie_shell=1)

    def test_literal_component_and_distinct_application(self):
        b=application(self.parent)
        self.assertEqual(len(b['rtl_sources']),70)
        for name,source in self.parent['files'].items():
            self.assertEqual(b['files'][name],source)
        sv=b['files'][b['top']+'.sv']
        self.assertIn('PCIE_SHELL=1',sv.split(') (',1)[0])
        self.assertIn('.PCIE_SHELL(0)',sv)
        self.assertEqual(b['parameters']['PCIE_SHELL'],1)
        self.assertEqual(b['r15_shell_application']['component_parameters']['PCIE_SHELL'],0)
        self.assertFalse(b['r15_shell_application']['vendor_simulation_ready'])
        self.assertFalse(b['r15_host_link']['real_pcie_ip_ready'])

    def test_no_implicit_direct_enable(self):
        b=dict(self.parent,parameters=dict(self.parent['parameters'],DIRECT_COLD=0))
        with self.assertRaisesRegex(ValueError,'REQUIRES_LITERAL_DIRECT1'):
            application(b)


if __name__=='__main__':unittest.main()
