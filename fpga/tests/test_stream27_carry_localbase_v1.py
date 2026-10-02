"""Pure scalar/model/source metadata only, no HDL/fullN numeric work."""
import unittest
from fpga.reference import stream27_carry_localbase_v1 as s


class CarryLocalBase(unittest.TestCase):
    def test_exact33bit_thresholds_and_quotient_regions(self):
        for aw in range(5,17):
            for p in (8,16):
                for base in (max(2*(1<<aw)+5,(2*(2*(1<<aw)+24*p)+2)//3+1),1000000000):
                    t=s.terms(base,aw,p)
                    self.assertEqual(t['y_high'],2*base-2+2*(1<<aw)+23*p)
                    for value in (-2*base,-base-1,-base,-1,0,base-1,base,2*base-1,2*base,3*base-1,3*base,4*base-1):
                        q=-2 if value<t['negative_radix'] else -1 if value<0 else 0 if value<t['radix'] else 1 if value<t['two_radix'] else 2 if value<t['three_radix'] else 3
                        self.assertEqual((q,value-q*base),divmod(value,base))
        with self.assertRaises(ValueError):s.terms(1000000001,16,8)

    def test_lane_has_exact_begin_cohort_and_no_feedback_stage(self):
        lane=(s.ROOT/s.LANE).read_text();cell=(s.ROOT/s.CELL).read_text()
        self.assertIn('if(rst_n && state==IDLE && begin_block && !fault_now)',lane)
        self.assertEqual(lane.count('.three_radix(three_radix_reg)'),2)
        self.assertIn('state<=ACTIVE;base_reg<=base;reciprocal_reg<=reciprocal;limit_reg<=coefficient_limit;',lane)
        self.assertIn('.carry_in(small_carry)',lane)
        self.assertIn('if(in_valid && legal)carry_out<=carry_next;',cell)
        self.assertNotIn('assign three_radix=',cell)
        self.assertNotIn('assign y_high=',cell)
        self.assertIn('out_error<=in_valid && !legal;',cell)

    def test_actual_paired_source_and_independent_small_reference(self):
        for aw,p in ((5,8),(5,16),(8,8),(8,16)):
            m,files=s.role(aw,p)
            self.assertEqual(m['carry_localbase']['added_edges'],0)
            self.assertEqual([step['expected_returncode'] for step in m['steps']],[0,0])
            self.assertTrue(all('paired=1' in step['expected_stdout'] for step in m['steps']))
            self.assertEqual(m['carry_localbase']['counts']['paired'],1)
            self.assertIn(b'PAIRED=true',files[s.HEADER])
            probe=files['rtl/'+s.PROBE+'.sv']
            self.assertIn(b'pair_mismatch=',probe)
            self.assertIn(b'actual.digit_data!=parent.digit_data',probe)
            self.assertIn(b'S4_PARAM_FIELD_OWNER_JOIN',files[s.CPP])
            self.assertIn(b'S4_PARAM_MINUS2_QUARANTINE',files[s.CPP])
            old,new=s.bundle(aw,p)
            self.assertEqual(old['geometry'],new['geometry'])
            for name,text in old['files'].items():self.assertEqual(new['files'][name],text)

    def test_independent_lane_faults_and_frozen_p16_numeric_corpus(self):
        from fpga.reference import stream27_carry_localbase_fault_vectors_v1 as v
        from fpga.reference import track_a4_blockcarry_lane_vectors_v1 as old
        for aw in (5,8):
            self.assertEqual(v.corpus(aw,16),old.corpus(aw))
        for p in (8,16):
            m,files=s.fault_role(5,p)
            self.assertEqual([step['expected_returncode'] for step in m['steps']],[0,1])
            self.assertTrue(m['carry_localbase']['paired_exact_parent'])
            self.assertEqual(m['carry_localbase']['added_edges'],0)
            self.assertGreater(m['carry_localbase']['counts']['error_edges'],0)
            self.assertIn(b'CARRY_LOCALBASE_LANE_PAIR',files[s.FAULT_CPP])
            self.assertIn(b'for age in range(30)',files[s.FAULT_VECTORS])


if __name__=='__main__':unittest.main()
