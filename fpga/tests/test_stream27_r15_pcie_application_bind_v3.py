import unittest
from fpga.reference.stream27_r15_all_io_bind import prepare
from fpga.reference.stream27_r15_pcie_application_bind_v2 import application as previous
from fpga.reference.stream27_r15_pcie_application_bind_v3 import application
from fpga.reference.stream27_r15_qsys_application_v2 import component


class Application(unittest.TestCase):
    def test_external_fault_only_new_boundary_no_compute_mutation(self):
        p=prepare(n=256,p=16,contexts=2,fixed_schedule=1,lean_build=1,
            progress_watchdog=1,storage_to_ram=1,direct_cold=1,pcie_shell=0)
        old=previous(p);new=application(p)
        self.assertEqual(len(new['rtl_sources']),70)
        for k,v in p['files'].items():self.assertEqual(new['files'][k],v)
        changed={k for k in old['files'] if old['files'][k]!=new['files'].get(k)}
        self.assertEqual(changed,{old['top']+'.sv','genefer_stream27_r15_pcie_avmm_v1.sv'})
        top=new['files'][new['top']+'.sv']
        self.assertIn('input logic external_fault_valid,output logic external_fault_ready',top)
        self.assertIn('.external_fault_valid,.external_fault_ready',top)
        self.assertEqual(top.count('.rst_n(core_reset_n)'),2)
        self.assertEqual(top.count('.rst_n(common_reset_n)'),2)
        self.assertIn('add_interface_port aperture_fault external_fault_valid valid Input 1',component(new))
        self.assertIn('add_interface_port aperture_fault external_fault_ready ready Output 1',component(new))
        self.assertFalse(new['r15_host_link']['real_pcie_ip_ready'])
