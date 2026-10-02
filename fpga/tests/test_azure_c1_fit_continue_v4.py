import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('continue_c1',ROOT/'cloud/azure_c1_fit_continue_v4.py')
fit=importlib.util.module_from_spec(spec);spec.loader.exec_module(fit)

class Continuation(unittest.TestCase):
    def test_no_synthesis(self):
        fit.exact_tcl(fit.RESUME_TCL)
        self.assertNotIn('execute_module -tool syn',fit.RESUME_TCL)
    def test_extra_command_refused(self):
        with self.assertRaises(ValueError):fit.exact_tcl(fit.RESUME_TCL+'execute_module -tool syn\n')
    def test_fixed_derivative(self):
        raw=(ROOT/'cloud/azure_c1_fit_v3.py').read_bytes()
        source=fit.derive_source(raw,'a'*64)
        compile(source,'test-derivative','exec')
        self.assertIn('_VERIFY_CONTINUATION(path, approved)',source)
        self.assertIn('host_hours_azure_v3.py',source)
    def test_parent_source_tamper(self):
        with self.assertRaises(ValueError):fit.derive_source((ROOT/'cloud/azure_c1_fit_v3.py').read_bytes()+b'\n','a'*64)

if __name__=='__main__':unittest.main()
