import unittest
from fpga.reference import anext_compute_projection_v1 as p
class Projection(unittest.TestCase):
    def test_real_phase_and_clock_binding(self):
        r=p.project();self.assertEqual(r['backend_cycles'],25989+(p.COUNT-1)*21872)
        self.assertEqual(r['command_square_latency_cycles'],25991+(p.COUNT-1)*21874)
        self.assertEqual(sum(r['backend_cycles_by_phase'].values()),r['backend_cycles'])
        self.assertEqual(r['conditional_double_extra_cycles'],0)
        self.assertFalse(r['measured_exact_sample_PRP']);self.assertFalse(r['promotion_allowed'])
    def test_cold_boundary_and_arguments(self):
        self.assertEqual(p.calculate(1)['backend_cycles'],25989)
        self.assertEqual(p.calculate(2)['backend_cycles'],47861)
        for value in (True,0,-1,1.1):
            with self.assertRaises(ValueError):p.calculate(value)
            with self.assertRaises(ValueError):p.calculate(period_ps=value)
if __name__=='__main__':unittest.main()
