import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r9_seed1_physical',ROOT/'results/throughput-20260929/r9-seed1-clock-replay-independent-v1.py')
recipe = importlib.util.module_from_spec(spec); spec.loader.exec_module(recipe)


class SeparateSeed1Data(unittest.TestCase):
    def test_exact_literal_framework_derivative(self):
        raw = recipe.PARENT.read_bytes()
        result = recipe.derive(raw)
        for old,new,count in reversed(recipe.CHANGES):
            self.assertEqual(result.count(new),count,new)
            result = result.replace(new,old)
        self.assertEqual(result.encode(),raw)

    def test_framework_drift_refuses(self):
        with self.assertRaises(ValueError): recipe.derive(recipe.PARENT.read_bytes()+b'\n')


if __name__ == '__main__': unittest.main()
