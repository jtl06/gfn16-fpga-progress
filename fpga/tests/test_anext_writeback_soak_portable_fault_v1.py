import copy
import json
import unittest
from fpga.reference import anext_writeback_soak_portable_fault_v1 as f

class PortableF3Controls(unittest.TestCase):
    def manifests(self):
        return [json.loads((f.ROOT/'artifacts'/name/'manifest.json').read_text())
                for name, _ in (f.ORIGINAL, f.PORTABLE)]

    def test_exact_original_fault_contracts_and_shared_assets(self):
        original, portable = self.manifests()
        before = copy.deepcopy(original)
        steps = f.fault_steps(original, portable)
        self.assertEqual(original, before)
        self.assertEqual(len(steps), 2)
        for step in steps:
            donor = next(s for s in original['steps'] if s['name'] == step['name'])
            for field in ('name', 'argv', 'expected_returncode', 'expected_stderr'):
                self.assertEqual(step[field], donor[field])
            self.assertEqual(step['validator']['config'], donor['validator']['config'])
            self.assertEqual(step['validator']['source'], portable['steps'][0]['validator']['source'])
            self.assertEqual(step['validator']['assets'], portable['steps'][0]['validator']['assets'])

    def test_missing_fault_and_wrong_rc_reject(self):
        original, portable = self.manifests()
        for altered in (dict(original, steps=original['steps'][:-1]), copy.deepcopy(original)):
            if len(altered['steps']) == 3:
                altered['steps'][1]['expected_returncode'] = 0
            with self.assertRaises(ValueError):
                f.fault_steps(altered, portable)

if __name__ == '__main__':
    unittest.main()
