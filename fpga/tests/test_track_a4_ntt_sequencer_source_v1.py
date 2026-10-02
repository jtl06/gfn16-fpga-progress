import unittest
from fpga.reference import track_a4_ntt_sequencer_source_v1 as s


class SequencerSourceTests(unittest.TestCase):
    def test_exact_frozen_profile_and_five_phase_cases(self):
        result=s.verify()
        self.assertEqual(len(result['phases']),5)
        self.assertEqual(result['phases'][1],dict(step=1,op=0,root_phase=1,dif=1))
        self.assertEqual(result['phases'][3],dict(step=3,op=0,root_phase=2,dif=0))

    def test_root_order_domain_metrics_and_quarantine_faults(self):
        parent=(s.ROOT/s.PARENT).read_text(); source=(s.ROOT/s.NEW).read_text()
        variants=(('profile_format(8\'d2)','profile_format(8\'d1)'),
                  ('root_phase=step==0 ? 2\'d0','root_phase=step==0 ? 2\'d1'),
                  ('ntt_cycles<=ntt_cycles+1','ntt_cycles<=ntt_cycles+2'),
                  ('profile_words_loaded+1','profile_words_loaded+2'),
                  ('state!=FAILED','state!=IDLE'),
                  ('block_read_en && !start_ntt','block_read_en'),
                  ("32'd104857601","32'd104857603"))
        for old,new in variants:
            self.assertIn(old,source)
            with self.subTest(new=new),self.assertRaises(ValueError):
                s.validate_text(parent,source.replace(old,new,1))

    def test_no_crt_carry_host_ownership_growth(self):
        parent=(s.ROOT/s.PARENT).read_text(); source=(s.ROOT/s.NEW).read_text()
        with self.assertRaisesRegex(ValueError,'ownership expansion'):
            s.validate_text(parent,source+'\n// genefer_crt3\n')


if __name__=='__main__':unittest.main()
