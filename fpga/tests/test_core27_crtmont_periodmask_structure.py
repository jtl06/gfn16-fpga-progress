"""Source-only isolation checks; no HDL/native tools or NTT computations."""
import json
from pathlib import Path
import unittest
from fpga.reference import core27_crtmont_periodmask_structure as s

ROOT = Path(__file__).resolve().parents[1]


class CrtmontPeriodmaskStructureTests(unittest.TestCase):
    def test_exact_derivative_and_audited_parent_pins(self):
        self.assertEqual(len(s.validate_files(ROOT)), 4)
        review = json.loads((ROOT / 'results/throughput-20260929/crtmont-a1-selected100-v1/independent-review-v1.json').read_text())
        for name, digest in s.PINS.items():
            self.assertEqual(review['source_sha256'][name + '.sv'], digest)

    def test_only_module_and_child_names_change_in_integration(self):
        for name in (s.ENGINE, s.HOST, s.TOP):
            child = {s.ENGINE: s.RECURRENCE, s.HOST: s.ENGINE, s.TOP: s.HOST}[name]
            old = (ROOT / 'rtl/kernel' / (name + '.sv')).read_text()
            new = (ROOT / 'rtl/kernel' / (s.NAMES[name] + '.sv')).read_text()
            restored = new.replace('module ' + s.NAMES[name] + ' #(', 'module ' + name + ' #(')
            restored = restored.replace(s.NAMES[child] + ' #(', child + ' #(')
            self.assertEqual(old, restored)

    def test_changed_parent_is_rejected_before_derivation(self):
        old = (ROOT / 'rtl/kernel' / (s.TOP + '.sv')).read_text()
        with self.assertRaisesRegex(ValueError, 'ancestor drift'):
            s.expected(s.TOP, old + '// changed\n')


if __name__ == '__main__':
    unittest.main()
