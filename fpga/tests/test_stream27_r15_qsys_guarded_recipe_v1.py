import unittest
from fpga.reference.stream27_r15_qsys_guarded_recipe_v1 import recipe


class GuardedRecipe(unittest.TestCase):
    def test_every_dma_application_path_passes_guard(self):
        text=recipe()
        self.assertIn('DEVICE 10AX115N4F40E3SG',text)
        self.assertIn('gui_output_clock_frequency0 83.333333',text)
        self.assertIn('pcie.dma_rd_master aperture.write_in',text)
        self.assertIn('pcie.dma_wr_master aperture.read_in',text)
        self.assertNotIn('{pcie.dma_rd_master app.cold',text)
        self.assertNotIn('{pcie.dma_wr_master app.export',text)
        for name,address in [('rd_dts_slave','0x01000000'),('wr_dts_slave','0x01002000')]:
            self.assertIn('{aperture.write_out pcie.'+name+' '+address+'}',text)
        self.assertIn('add_connection aperture.fault app.aperture_fault',text)
