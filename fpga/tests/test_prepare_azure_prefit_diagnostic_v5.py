import copy
from datetime import datetime, timedelta
import importlib.util
import json
from pathlib import Path
import unittest

FPGA = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_v5', FPGA/'tools/prepare_azure_prefit_diagnostic_v5.py')
helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
STAGE = FPGA/'results/throughput-20260929/quartus-prefit-azure-diag-stage-v5'


class RuntimeAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.expected = json.loads((STAGE/'payload.json').read_text())['tool_sha256']
        self.observation = json.loads((STAGE/'runtime-drift-readonly-v1.json').read_text())
        self.now = datetime.fromisoformat(self.observation['observed_at_utc'])+timedelta(seconds=1)

    def test_actual_observed_runtime_package_matches_and_quartus_unchanged(self):
        tools = helper.observed_tools(self.expected, self.observation, self.now)
        self.assertEqual(tools['/usr/bin/python3'], 'e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f')
        for name, pin in self.expected.items():
            if name != '/usr/bin/python3':
                self.assertEqual(tools[name], pin)

    def test_unknown_native_tool_change_missing_pin_and_package_drift_block(self):
        cases = []
        changed = copy.deepcopy(self.observation); changed['tool_sha256'][helper.ROOT+'/altera_pro/26.1/quartus/linux64/quartus_sta'] = '0'*64; cases.append(changed)
        missing = copy.deepcopy(self.observation); missing['tool_sha256'].pop('/usr/bin/time'); cases.append(missing)
        bad_package = copy.deepcopy(self.observation); bad_package['dpkg_verification']['stdout'] = 'changed binary'; cases.append(bad_package)
        no_history = copy.deepcopy(self.observation); no_history['apt_history'] = ''; cases.append(no_history)
        for observation in cases:
            with self.subTest(observation=observation.get('apt_history_sha256')):
                with self.assertRaises(ValueError):
                    helper.observed_tools(self.expected, observation, self.now)

    def test_stale_future_and_unsupported_package_block(self):
        for now in (self.now-timedelta(seconds=2), self.now+timedelta(seconds=900)):
            with self.assertRaises(ValueError):
                helper.observed_tools(self.expected, self.observation, now)
        observation = copy.deepcopy(self.observation); observation['installed_packages']['stdout'] = 'python3.12-minimal\tUNKNOWN\n'
        with self.assertRaises(ValueError):
            helper.observed_tools(self.expected, observation, self.now)


if __name__ == '__main__':
    unittest.main()
