import random
import unittest

from fpga.reference import stream27_r85_width_bounds as bounds


class WidthBoundsTests(unittest.TestCase):
    def test_all_geometry_endpoint_proofs_and_signed_widths(self):
        for aw in range(5,17):
            for p in (8,16):
                v=bounds.prove_profile(aw,p)
                self.assertLess(v['coefficient_limit_max'],1 << 77)
                self.assertLess(v['q1_abs_upper'],1 << 47)
                self.assertLessEqual(v['q2_abs_upper'],v['q'])
                for base in (v['base_min'],v['base_min']+1,604832956,999999937,10**9):
                    a=bounds.coefficient_limit(base,aw,p)
                    self.assertLessEqual(bounds.ceildiv(a,base),v['q1_abs_upper'])
                    self.assertLessEqual(bounds.ceildiv(a,base*base),v['q2_abs_upper'])
        full=bounds.prove_profile()
        self.assertEqual(full['coefficient_limit_max'],131168016564584965062752)
        self.assertEqual(full['base_min'],131077)
        self.assertEqual(full['legal_coefficient']['mathematical_bits'],78)
        self.assertEqual(full['first_quotient']['mathematical_bits'],48)
        self.assertEqual(full['exact_reciprocal']['mathematical_bits'],79)
        self.assertEqual(bounds.parameters(5,16)['base_min'],300)
        self.assertEqual(bounds.parameters(8,16)['base_min'],599)
        with self.assertRaises(ValueError):bounds.coefficient_limit(2)

    def test_full_centered_crt_and_double_domains(self):
        v=bounds.crt_bounds();half=bounds.M//2
        self.assertEqual(v['centered_coefficient']['mathematical_bits'],79)
        self.assertEqual(v['after_integer_doubling']['mathematical_bits'],80)
        for x in (0,half,half+1,bounds.M-1):
            centered=x-bounds.M if x>half else x
            self.assertGreaterEqual(centered,-half)
            self.assertLessEqual(centered,half)
            self.assertEqual(bounds.signed_truncate(centered,79),centered)
            self.assertEqual(bounds.signed_truncate(2*centered,80),2*centered)
        self.assertNotEqual(bounds.signed_truncate(half,78),half)
        self.assertNotEqual(bounds.signed_truncate(2*half,79),2*half)

    def test_reciprocal_precision_negative_floor_and_products(self):
        rng=random.Random(0x6a09e667)
        for width in (47,77):
            for base in (2,3,599,131077,604832956,999999937,10**9):
                values=[0,1,-1,base-1,base,-base,-base-1,(1 << width)-1,-((1 << width)-1)]
                values.extend(rng.randrange(-(1 << width)+1,1 << width) for _ in range(300))
                for value in values:
                    got=bounds.reciprocal_divide(value,base,width)
                    self.assertEqual((got['quotient'],got['remainder']),divmod(value,base))
                    self.assertLessEqual(got['product_bits'],2*width)
            with self.assertRaises(ValueError):bounds.reciprocal_divide(-(1 << width),2,width)
        self.assertEqual(bounds.reciprocal_divide(-1,10**9,77)['quotient'],-1)

    def test_full96_detection_cannot_be_replaced_by_80_slice(self):
        rows=bounds.malformed_counterexamples()
        self.assertTrue(all(not r['admitted_before_truncation'] and r['admitted_after_truncation'] for r in rows))
        a=bounds.coefficient_limit(10**9)
        for v in (-a,a):self.assertTrue(bounds.coefficient_admitted(v))
        for v in (-a-1,a+1):self.assertFalse(bounds.coefficient_admitted(v))
        with self.assertRaises(ValueError):bounds.coefficient_admitted(1 << 95)

    def test_small_and_canonical_fold_range_and_fault_boundaries(self):
        for aw,p in ((5,8),(5,16),(8,16),(16,16)):
            v=bounds.parameters(aw,p)
            for base in (v['base_min'],604832956,10**9):
                q=v['q']
                for y in (-q,-1,0,base-1,base,2*base-2+q):
                    for carry in (-2,-1,0,1,2,3):
                        got=bounds.small_carry(y,carry,base,aw,p)
                        if not got['error']:
                            self.assertEqual((got['carry'],got['digit']),divmod(y+carry,base))
                self.assertTrue(bounds.small_carry(0,-3,base,aw,p,True)['error'])
                self.assertTrue(bounds.small_carry(-1,0,base,aw,p,True)['error'])
                self.assertTrue(bounds.small_carry(1 << 31,0,base,aw,p)['error'])
                for value in (-2*base,-base,-1,0,base,2*base,3*base-1):
                    got=bounds.canonical_fold(value,base)
                    self.assertEqual((got['carry'],got['digit']),divmod(value,base))
                for value in (-2*base-1,3*base,1 << 33):
                    self.assertTrue(bounds.canonical_fold(value,base)['error'])

    def test_actual_signextension_is_already_merged(self):
        source=bounds.inspect_sources();physical=bounds.physical_report()
        self.assertEqual(source['effective_source_widths']['divider_magnitudes'],[77,47])
        self.assertEqual(len(physical['crt_merges']),16)
        self.assertEqual(len(physical['double_merges']),16)
        self.assertEqual(physical['register_representation_upper_bounds'],
                         dict(crt_per_lane=80,double_per_lane=81,canonical_read=32))
        self.assertFalse(physical['full_width_CRT_carry_multiplier_fabric_claim'])


if __name__ == '__main__':unittest.main()
