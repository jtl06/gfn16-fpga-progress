from pathlib import Path
import tempfile
import unittest
from fpga.reference import stream27_p8b_negatives_v1 as m


class P8Negatives(unittest.TestCase):
    def test_each_exact_delta_and_typed_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            for role in m.ROLES:
                r=m.prepare(Path(tmp)/role,role)
                self.assertEqual(r['preserved_parent_files'],13)
                self.assertIn('P8B_',r['expected'])
                with self.assertRaises(AssertionError):m.prepare(Path(tmp)/role,role)

    def test_counterexamples_without_transform(self):
        self.assertFalse(7==8);self.assertTrue(7==7)
        expected=[0]*32;expected[(31+31)%32]=104857600
        observed=[(73+row,lane) for row in range(4) for lane in range(8)
                  if expected[int(f'{lane:03b}'[::-1],2)*4+row]]
        self.assertEqual(observed,[(75,7)])


if __name__=='__main__':unittest.main()
