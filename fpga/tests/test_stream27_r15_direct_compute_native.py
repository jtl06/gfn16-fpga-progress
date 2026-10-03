import unittest
from fpga.reference import stream27_r15_direct_compute_native as own


class R15DirectComputeNativeTests(unittest.TestCase):
    def test_own_combined65_and_real_transaction_driver(self):
        manifest,files,bundle=own.role()
        self.assertEqual(len(bundle['files']),65)
        self.assertEqual(len(manifest['build']['sv_sources']),65)
        self.assertEqual(manifest['build']['parameters']['DIRECT_COLD'],1)
        self.assertEqual(manifest['build']['parameters']['PCIE_SHELL'],0)
        cpp=files[own.CPP].decode()
        self.assertNotIn('d.load_we=1',cpp)
        self.assertIn('d.dc_lease=d.dc_next_lease',cpp)
        self.assertIn('R15_DIRECT_CORE_ISSUED_OWNER_LEASE',cpp)
        self.assertIn('R15_DIRECT_ACK_DRAIN',cpp)
        self.assertIn('R15_DIRECT_COMMIT_LOADED_AUTHORITY',cpp)
        self.assertIn('S4_HOST_CONTEXT_ACTUAL_FULL_CHAINS',cpp)
        self.assertIn('S4_HOST_CONTEXT_SIGNED96_VALUE',cpp)
        self.assertFalse(manifest['r15_direct_compute']['real_PCIe_CDC'])
        self.assertEqual(manifest['sources'],{n:own.sha(raw) for n,raw in files.items()})


if __name__=='__main__':unittest.main()
