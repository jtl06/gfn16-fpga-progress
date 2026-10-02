import ast
from pathlib import Path
import unittest
from fpga.cloud import aws_fit_a4_provisional_v1 as adapter


class A4FitPreparationTests(unittest.TestCase):
    def test_exact_helper_reuse(self):
        raw=adapter.helper_path.read_bytes()
        tree=ast.parse(adapter.launch_helper_source(raw))
        self.assertEqual([n.name for n in tree.body],['final_inputs','launch_inner'])
        self.assertNotIn('T5b',adapter.launch_helper_source(raw))
        self.assertIn('A4_correctness_complete=False',adapter.launch_helper_source(raw))
        with self.assertRaises(ValueError):adapter.launch_helper_source(raw+b'\n')

    def test_qsf_geometry(self):
        qsf=adapter.expected_qsf(['one.sv','two.sv']).decode()
        for value in ('NUM_PARALLEL_PROCESSORS 6','SEED 1','set_parameter -name AW 16','DEVICE 10AX115N4F40E3SG'):
            self.assertIn(value,qsf)
        self.assertNotIn('set_parameter -name NTT_LANES',qsf)
        self.assertEqual(qsf.count('VIRTUAL_PIN'),28)
        self.assertNotIn('-to {clk}',qsf)


if __name__=='__main__':unittest.main()
