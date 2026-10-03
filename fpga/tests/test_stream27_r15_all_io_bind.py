import re
import unittest
from reference import stream27_r15_all_io_bind as bind


class IOIntegration(unittest.TestCase):
    def test_literal_off_and_frozen_compute(self):
        for n in (256,65536):
            parent=bind.compute.fixed.capture(n)
            self.assertEqual(bind.prepare(n),parent)
            self.assertEqual(bind.prepare(n,fixed_schedule=1),bind.compute.prepare(n,fixed_schedule=1))

    def test_direct_source_abi_containment(self):
        for n in (256,65536):
            for combo in (False,True):
                out=bind.prepare(n,direct_cold=1,fixed_schedule=int(combo),
                    lean_build=int(combo),progress_watchdog=int(combo),storage_to_ram=int(combo))
                self.assertEqual(len(out['files']),65 if combo else 63)
                self.assertEqual(out['parameters']['DIRECT_COLD'],1)
                self.assertEqual(out['parameters']['PCIE_SHELL'],0)
                text=out['files'][out['top']+'.sv']
                header=text[:text.index(');')]
                params=re.findall(r'\b([A-Z][A-Z0-9_]*)=\d+',header)
                self.assertEqual(len(params),len(set(params)))
                self.assertIn('command_valid',text)
                self.assertTrue(out['r15_host_link']['source_ready'])
                self.assertFalse(out['r15_host_link']['real_pcie_ip_ready'])
                self.assertFalse(out['r15_all_io']['field_flush_claim'])
                self.assertFalse(out['r15_all_io']['chip_final_materialization_removed'])
                self.assertEqual(out['r15_all_io']['internal_compute_geometry'],bind.compute.fixed.capture(n)['geometry'])

    def test_unready_real_shell_refused(self):
        with self.assertRaises((ValueError,ModuleNotFoundError)):
            bind.prepare(256,direct_cold=1,pcie_shell=1)


if __name__=='__main__':unittest.main()
