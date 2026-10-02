import unittest
from pathlib import Path
from fpga.reference.core27_prefill_structure import CORE
from fpga.reference.core27_prefill_mutations import MUTANTS, mutate


class MutationPreparation(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def test_all_six_anchors_are_unique_and_independently_observed(self):
        source = (self.root/'rtl/kernel'/(CORE+'.sv')).read_text()
        monitor = (self.root/'rtl/tb/core27_prefill_probe.sv').read_text()
        self.assertEqual(len(MUTANTS), 6)
        for name, (before, after, fatal) in MUTANTS.items():
            with self.subTest(name=name):
                changed, expected = mutate(source, name)
                self.assertEqual(changed.replace(after, before, 1), source)
                self.assertNotEqual(changed, source)
                self.assertEqual(expected, fatal)
                self.assertIn('"'+fatal+'"', monitor)

    def test_missing_and_ambiguous_anchors_fail_closed(self):
        before = MUTANTS['base_tag'][0]
        for source in ['', before+before]:
            with self.assertRaisesRegex(ValueError, 'ambiguous'):
                mutate(source, 'base_tag')


if __name__ == '__main__': unittest.main()
