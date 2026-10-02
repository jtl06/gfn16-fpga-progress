import unittest
from fpga.reference.stream27_term_context_contract_v1 import (
    replay,seed_vectors,factors,factor_index,weight,table_index,production_calendar)
from fpga.reference.stream_ntt_model import FIELDS


class TermContextsV1(unittest.TestCase):
    def test_small_direct_weight_feedback_seams_zero_coefficients(self):
        for field in range(3):
            result=replay(field=field)
            self.assertEqual(result['rows'],64);self.assertEqual(result['pending_products'],0)
            self.assertGreater(result['feedback_products'],0);self.assertGreater(result['reseed_products'],0)
            self.assertEqual(result['bypass_reads'],60)

    def test_bypass_and_reseed_and_factor_faults_are_observable(self):
        for key,kind in (('drop_bypass','CACHE_TARGET'),('retain_old_coefficient','DIRECT_WEIGHT'),('wrong_factor','DIRECT_WEIGHT')):
            with self.assertRaisesRegex(AssertionError,kind):replay(**{key:True})

    def test_exact_factor_and_seed_definition_all_small_rows(self):
        for n in (256,512):
            for field,(p,_) in enumerate(FIELDS):
                seeds=seed_vectors(n,field);fs=factors(n,field);rinv=pow(1<<32,-1,p)
                for row in range(n//8-4):
                    target=row+4
                    for lane in range(8):
                        if table_index(n,target)==table_index(n,row):
                            self.assertEqual(weight(n,field,row,lane)*fs[factor_index(row,n)]*rinv%p,
                                             weight(n,field,target,lane))
                        else:
                            shift=n.bit_length()-1-6
                            self.assertEqual(seeds[(target>>shift)*4+(target&3)][lane],weight(n,field,target,lane))

    def test_production_geometry_and_cancel_do_not_filter_physical_recurrence(self):
        g=production_calendar();self.assertEqual(g['product_tag_bits'],37)
        self.assertEqual(g['factor_words'],11);self.assertFalse(g['single_producer_seed_update_overlap'])
        a=replay();b=replay(cancel_at=70)
        self.assertEqual(a['output'],b['output']);self.assertEqual(b['commits'],20)
        with self.assertRaisesRegex(ValueError,'N512_LIMIT'):replay(65536)


if __name__=='__main__':unittest.main()
