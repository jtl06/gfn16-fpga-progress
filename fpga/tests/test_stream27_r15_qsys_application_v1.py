import unittest
from fpga.reference.stream27_r15_all_io_bind import prepare
from fpga.reference.stream27_r15_pcie_application_bind_v1 import application
from fpga.reference.stream27_r15_qsys_application_v1 import component


class Component(unittest.TestCase):
    def test_byte_address_burst_and_exact_flags(self):
        p=prepare(n=256,p=16,contexts=2,fixed_schedule=1,lean_build=1,
            progress_watchdog=1,storage_to_ram=1,direct_cold=1,pcie_shell=0)
        b=application(p);t=component(b)
        for bus in ('control','cold','export'):
            self.assertIn(f'{bus} addressUnits SYMBOLS',t)
            self.assertIn(f'{bus} constantBurstBehavior false',t)
        for k,v in b['parameters'].items():
            self.assertIn(f'add_parameter {k} INTEGER {v}',t)
            self.assertIn(f'{k} ALLOWED_RANGES {{{v}}}',t)
        self.assertEqual(t.count(' SYSTEM_VERILOG PATH '),70)
        self.assertNotIn('BLACKBOX',t)

    def test_reject_nonapplication(self):
        with self.assertRaisesRegex(ValueError,'REQUIRES_APPLICATION'):
            component({'parameters':{'PCIE_SHELL':0}})


if __name__=='__main__':unittest.main()
