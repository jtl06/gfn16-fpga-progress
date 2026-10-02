import unittest
from fpga.reference import stream27_crt_carry_mapping as m

class ExistingMappingTests(unittest.TestCase):
    def test_table_qualifies_ambiguous_name_header(self):
        raw=b'; Name ; Dummy ;\n; x ; y ;\n+--+\n; Name ; Mode ; AX/CoefSelA ; Output Register ;\n+--+\n; product ; Independent27 ; input ; output ;\n+--+\n'
        rows=m.table(raw,'Name',('Mode','AX/CoefSelA','Output Register'))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['Name'],'product')
        with self.assertRaises(ValueError):m.table(raw,'Name',('missing',))
    def test_own_and_inclusive_are_distinct(self):
        row={'needed':'575.6 (569.6)'}
        self.assertEqual(m.metric(row,'needed'),575.6)
        self.assertEqual(m.metric(row,'needed',own=True),569.6)
        with self.assertRaises(ValueError):m.metric({'needed':'not-a-resource'},'needed')
    def test_actual_source_bound_mapping_and_disjoint_closure(self):
        result=m.analyse();h=result['hierarchy']
        self.assertEqual(result['shared_physical_DSP_packing_rows'],376)
        self.assertEqual(h['carry16']['DSP_physical'],272)
        self.assertEqual(h['crt16']['DSP_physical'],96)
        self.assertEqual(h['shared_setup']['DSP_physical'],8)
        self.assertEqual(h['fields3']['DSP_physical'],942)
        self.assertEqual(h['whole']['DSP_physical'],1318)
        self.assertEqual(h['whole']['DSP_needed'],1300)
        self.assertEqual(result['explicit_logic_targeted_multipliers'],[])
        self.assertEqual(result['inferred_multiplication_targets'],
            {'dsp':441,'decomposed into smaller multipliers':52})
    def test_same_sparse_constant_product_exact59(self):
        # Scalar algebra/bound check only; not a new native RTL result.
        for prime,shift in ((69206017,21),(67239937,17)):
            self.assertEqual(prime,1+(1<<26)+(1<<shift))
            for value in (0,1,(1<<5)-1,(1<<26)-1,(1<<27)-1,(1<<31), (1<<32)-1):
                product=value+ (value<<26)+(value<<shift)
                self.assertEqual(product,value*prime)
                self.assertLess(product,1<<59)
                self.assertEqual(product>>32,(value*prime)>>32)
    def test_legal_coefficient_and_general_CRT_bounds_are_distinct(self):
        r=m.analyse()['precision']
        self.assertEqual(r['magnitude_bits'],77)
        self.assertLess(r['max_legal_coefficient_magnitude'],1<<77)
        self.assertGreaterEqual(r['canonical_CRT_magnitude_max'],1<<77)
        self.assertLess(r['canonical_CRT_magnitude_max'],1<<78)
        self.assertEqual(r['canonical_CRT_signed_bits'],79)
    def test_private_hypothesis_keeps_conservative_physical_DSP_margin(self):
        r=m.analyse()['private_hypothesis']
        self.assertEqual(r['conservative_extra_DSP'],64)
        self.assertEqual(r['projected_physical_DSP_if_all_added'],1382)
        self.assertLess(r['projected_physical_DSP_if_all_added'],r['planning_DSP_target'])
        self.assertIn('P2mont_t2',r['scope'])

if __name__=='__main__':unittest.main()
