import unittest
from fpga.reference.anext_point_compute_projection_v1 import calculate,COUNT
from fpga.reference.anext_compute_projection_v1 import calculate as old
class Projection(unittest.TestCase):
    def test_exact_delta(self):
        for n in (1,2,COUNT):
            p=calculate(n);a=old(n,11196)
            self.assertEqual(p['backend_cycles']-a['backend_cycles'],n)
            self.assertEqual(p['command_square_latency_cycles']-p['backend_cycles'],2*n)
            self.assertEqual(p['conditional_double_extra_cycles'],0)
            self.assertFalse(p['same_base_native_chain_exists']);self.assertFalse(p['point_specific_1000_pass'])
    def test_invalid(self):
        for n in (True,0,-1):
            with self.assertRaises(ValueError):calculate(n)
if __name__=='__main__':unittest.main()
