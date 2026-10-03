import unittest
from fpga.reference.stream27_r15_all_io_bind import prepare
from fpga.reference.stream27_r15_pcie_application_bind_v2 import application


class Application(unittest.TestCase):
    def test_literal_core_domain_resets_and_endpoint_v6(self):
        p=prepare(n=256,p=16,contexts=2,fixed_schedule=1,lean_build=1,
            progress_watchdog=1,storage_to_ram=1,direct_cold=1,pcie_shell=0)
        b=application(p)
        self.assertEqual(len(b['rtl_sources']),70)
        for k,v in p['files'].items():self.assertEqual(b['files'][k],v)
        s=b['files'][b['top']+'.sv']
        self.assertEqual(s.count('.rst_n(core_reset_n)'),2)
        self.assertEqual(s.count('.rst_n(common_reset_n)'),2) # FIFO own release gating
        self.assertIn('.reset(!pcie_reset_n)',s)
        self.assertIn('PCIE_SHELL=1',s.split(') (',1)[0])
        self.assertIn('.PCIE_SHELL(0)',s)
        self.assertEqual(b['r15_shell_application']['endpoint_version'],6)
        e=b['files']['genefer_stream27_r15_pcie_avmm_v1.sv']
        self.assertIn('(resp_data[15:8]==0 && resp_data[152])',e)
        self.assertIn('fault();waiting<=0;',e)
        self.assertIn('!held_violation && !resp_valid',e)
        self.assertNotIn('genefer_stream27_r15_link_reset_v1.sv',b['rtl_sources'])
        self.assertFalse(b['r15_host_link']['real_pcie_ip_ready'])


if __name__=='__main__':unittest.main()
