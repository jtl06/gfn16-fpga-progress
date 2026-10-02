import importlib.util
from pathlib import Path
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('azure_diag', FPGA/'cloud/azure_prefit_diagnostic_v1.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class AdmissionTests(unittest.TestCase):
    def test_exact_profile_caps(self):
        module.validate_caps([0, 1, 2, 3], '400000 100000', str(24 << 30), '0', 840000000, 60000000)
        for affinity, cpu, memory, swap, runtime, stop in (
                ([0, 1, 2, 4], '400000 100000', str(24 << 30), '0', 840000000, 60000000),
                ([0, 1, 2, 3], '800000 100000', str(24 << 30), '0', 840000000, 60000000),
                ([0, 1, 2, 3], '400000 100000', 'max', '0', 840000000, 60000000),
                ([0, 1, 2, 3], '400000 100000', str(24 << 30), '1', 840000000, 60000000),
                ([0, 1, 2, 3], '400000 100000', str(24 << 30), '0', 841000000, 60000000)):
            with self.assertRaises(ValueError):
                module.validate_caps(affinity, cpu, memory, swap, runtime, stop)

    def test_systemd_finite_duration(self):
        self.assertEqual(module.duration_us('14min'), 840000000)
        self.assertEqual(module.duration_us('1min'), 60000000)
        self.assertEqual(module.duration_us('1min 500ms'), 60500000)
        with self.assertRaises(ValueError):
            module.duration_us('infinity')

    def test_no_compilation_command_exists(self):
        source = (FPGA/'cloud/azure_prefit_diagnostic_v1.py').read_text()
        self.assertNotIn('execute_module', source)
        self.assertNotIn('quartus_fit', source)
        self.assertIn("for mode in (packet['mode'],):", source)


if __name__ == '__main__':
    unittest.main()
