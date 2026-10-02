import importlib.util
import json
from pathlib import Path
import unittest

FPGA = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, FPGA/'cloud'/f'{name}.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class EarlierDeadlineAdmissionTests(unittest.TestCase):
    def test_additive_profile_matches_independently_captured_user_admission(self):
        previous = load('azure_prefit_diagnostic_v1')
        current = load('azure_prefit_diagnostic_v2')
        admission = json.loads((FPGA/'cloud/azure-protected-admission-earlier-v1.json').read_text())
        self.assertEqual(current.DEADLINE, admission['authorized_epoch'])
        self.assertEqual(current.PROTECTED, admission['protected_sha256'])
        self.assertEqual(previous.DEADLINE, admission['previous_epoch'])
        self.assertNotEqual(previous.PROTECTED['/etc/gfn16-deallocate-at-epoch'], current.PROTECTED['/etc/gfn16-deallocate-at-epoch'])
        current.validate_caps([0, 1, 2, 3], '400000 100000', str(24 << 30), '0', 840000000, 60000000)


if __name__ == '__main__':
    unittest.main()
