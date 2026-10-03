import unittest
from fpga.reference.stream27_r15_bar2_offset_proof_v1 import proof


class BAR2(unittest.TestCase):
    def test_bar_base_projection_is_not_dma_aperture_authority(self):
        p=proof()
        self.assertEqual(p['aperture_bytes'],4096)
        self.assertFalse(p['native_HIP_execution_claim'])
        self.assertEqual(len(p['sources']),3)
