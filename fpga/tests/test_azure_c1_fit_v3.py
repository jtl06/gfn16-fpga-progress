import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1]/'cloud/azure_c1_fit_v3.py'
spec = importlib.util.spec_from_file_location('c1_fit', PATH)
fit = importlib.util.module_from_spec(spec); spec.loader.exec_module(fit)
PARENT = PATH.parents[1]/'results/throughput-20260929/core27-rootfused-crtmont64-aws-fit-v1/run.tcl'


class C1(unittest.TestCase):
    def text(self):
        return PARENT.read_text().replace('    execute_module -tool syn\n', '    execute_module -tool syn\n'+fit.GATE_INSERT)

    def test_exact_insertion(self):
        fit.exact_tcl(self.text())

    def test_gate_cannot_be_removed(self):
        with self.assertRaises(ValueError): fit.exact_tcl(PARENT.read_text())

    def test_second_gate_refused(self):
        with self.assertRaises(ValueError): fit.exact_tcl(self.text()+fit.GATE_INSERT)

    def test_native_sequence_edit_refused(self):
        with self.assertRaises(ValueError): fit.exact_tcl(self.text().replace('execute_module -tool fit', 'execute_module -tool asm'))

    def test_late_gate_refused(self):
        text = PARENT.read_text().replace('        execute_module -tool fit\n', '        execute_module -tool fit\n'+fit.GATE_INSERT)
        with self.assertRaises(ValueError): fit.exact_tcl(text)


if __name__ == '__main__': unittest.main()
