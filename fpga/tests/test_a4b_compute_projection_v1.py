import json
import unittest
from fpga.reference import a4b_compute_projection_v1 as p

class Projection(unittest.TestCase):
    def test_full_operation_reconciliation(self):
        r=p.project();n=p.COUNT
        self.assertEqual(r['backend_cycles'],37572+(n-1)*24721)
        self.assertEqual(r['command_square_latency_cycles'],37574+(n-1)*24723)
        self.assertEqual(sum(r['backend_cycles_by_phase'].values()),r['backend_cycles'])
        self.assertEqual(r['warm_control_cycles'],5);self.assertEqual(r['cold_control_cycles'],7)
        self.assertEqual(r['parent_t5b_backend_cycles'],55109963212)
        self.assertFalse(r['measured_sample_base']);self.assertFalse(r['audited_clock_claim'])

    def test_drift_and_boolean_rejected(self):
        m=json.loads((p.ROOT/p.NATIVE).read_text())['measurements']
        for key in ('NTT_cycles','warm_backend_cycles','root_load_cycles','seed_setup_cycles'):
            with self.assertRaises(ValueError):p.calculate(dict(m,**{key:m[key]+1}))
        for count in (0,True,1.1):
            with self.assertRaises(ValueError):p.calculate(m,count=count)
        self.assertEqual(p.calculate(m,count=1)['backend_cycles'],37572)

if __name__=='__main__':unittest.main()
