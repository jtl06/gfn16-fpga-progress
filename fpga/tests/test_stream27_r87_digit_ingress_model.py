import random
import unittest
from fpga.reference import stream27_r87_digit_ingress_model as m
from fpga.reference import stream27_host_contexts as host


class DigitIngressTests(unittest.TestCase):
    def test_actual_c2_first_ct_graph_all_fields(self):
        bundle=host.prepare(32,16,corr_serial_bfs=2,mont_factored=1,
                            cold_launch_fence=1,explicit_net_declarations=1)
        for f in range(3):
            g=m.graph(bundle,f)
            self.assertEqual((g['upper_multipliers'],g['lower_multipliers']),(0,8))

    def test_raw_lower_product_bound_and_exact_redc(self):
        rng=random.Random(87)
        for p,_ in m.FIELDS:
            pairs=[(x,w) for x in (0,1,p-1,p,p+1,2*p,3*p,m.RAW_MAX)
                   for w in (0,1,p-1,m.R%p)]
            pairs += [(rng.randrange(m.RAW_MAX+1),rng.randrange(p)) for _ in range(1024)]
            inverse=pow(m.R,-1,p)
            for x,w in pairs:
                product=m.split30(x,w)
                self.assertEqual(product,x*w)
                self.assertLess(product,p*m.R)
                self.assertEqual(m.redc_unsigned(product,p),x*w*inverse%p)
            self.assertGreater((m.RAW_MAX*(p-1)).bit_length(),55)

    def test_literal_bypass_and_signed_minus_one_fail(self):
        for p,_ in m.FIELDS:
            c=m.current_ct_bypass_counterexample(p)
            self.assertTrue(c['residue_mismatch'] or c['lazy_range_failure'])
            self.assertNotEqual((m.R-1)%p,p-1)
        self.assertTrue(m.current_ct_bypass_counterexample(m.FIELDS[0][0])['truncated'])

    def test_model_has_no_implicit_wide_or_fault_admission(self):
        for p,_ in m.FIELDS:
            with self.assertRaisesRegex(ValueError,'REDC_BOUND'):
                m.redc_unsigned(p*m.R,p)
        with self.assertRaisesRegex(ValueError,'PARTIAL_PRODUCT_RANGE'):
            m.split30(1<<30,1)
        self.assertIn('MODEL_ONLY',m.study()['status'])


if __name__=='__main__':
    unittest.main()
