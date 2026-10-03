import unittest
from pathlib import Path
from fpga.reference.stream27_r15_generated_clock_proof_v1 import proof


class Clock(unittest.TestCase):
    def test_actual_generated_pll_ratio_and_hip_rate(self):
        root=Path(__file__).resolve().parents[1]
        p=proof(root/'results/throughput-20260929/r15-pcie-system-generation-v1-artifacts',
                'r15_pcie_system_v1')
        self.assertEqual((p['pll_m'],p['pll_n'],p['pll_c']),(10,1,12))
        self.assertEqual(p['core_period_ns'],12)
        self.assertFalse(p['fitted_clock_claim'])
