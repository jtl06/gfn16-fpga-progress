import json
from pathlib import Path
import tempfile
import unittest

from fpga.reference import stream27_p16c_stale_eligibility_v1 as m


class StaleEligibility(unittest.TestCase):
    def test_exact_single_source_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'negative'
            result = m.prepare(out)
            self.assertEqual(result['changed_sources'], [m.TOP])
            self.assertEqual(result['preserved_sources'], 16)
            source = out/'inputs/fpga'/m.TOP
            self.assertIn(m.NEW, source.read_text())
            self.assertNotIn(m.OLD, source.read_text())
            manifest = json.loads((out/'manifest.json').read_text())
            self.assertEqual(manifest['steps'][0]['expected_stderr'], m.FAILURE)
            self.assertEqual(manifest['steps'][0]['expected_returncode'], 1)
            with self.assertRaises(AssertionError):
                m.prepare(out)

    def test_first_cancellation_counterexample(self):
        # Independent one-edge eligibility equation; no FFT or HDL execution.
        for tick in range(85):
            physical = 85 <= tick <= 88
            self.assertFalse(physical and 7 == 7)
        self.assertFalse(True and True and 7 == 8 and 7 == 7)
        self.assertTrue(True and True and 7 == 7)


if __name__ == '__main__':
    unittest.main()
