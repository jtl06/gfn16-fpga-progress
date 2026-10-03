import unittest
from fpga.reference.stream27_r15_all_io_bind import prepare
from fpga.reference.stream27_r15_pcie_application_bind_v3 import application as previous
from fpga.reference.stream27_r15_pcie_application_bind_v4 import application


class Application(unittest.TestCase):
    def test_same_boundary_only_width_repair(self):
        p=prepare(n=256,p=16,contexts=2,fixed_schedule=1,lean_build=1,
            progress_watchdog=1,storage_to_ram=1,direct_cold=1,pcie_shell=0)
        old=previous(p);new=application(p)
        self.assertEqual(len(new['rtl_sources']),70)
        for name,text in p['files'].items():self.assertEqual(new['files'][name],text)
        self.assertEqual(old['files'][old['top']+'.sv'].replace(old['top'],new['top']),new['files'][new['top']+'.sv'])
        e=new['files']['genefer_stream27_r15_pcie_avmm_v1.sv']
        self.assertIn("{15'b0,export_address[21:5]}",e)
        self.assertIn("{27'b0,export_burstcount}",e)
        self.assertIn('external_fault_valid',e)
        self.assertFalse(new['r15_host_link']['real_pcie_ip_ready'])
