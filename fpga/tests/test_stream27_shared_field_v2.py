import unittest
from fpga.reference import stream27_shared_field_v1 as parent
from fpga.reference.stream27_shared_field_v2 import geometry,prepare
from fpga.reference.stream_ntt_model import bit_reverse


class SmallShared(unittest.TestCase):
    def test_large_rtl_exactly_preserved(self):
        for p in (8,16):
            for field in range(3):
                a=parent.prepare(256,p,field);b=prepare(256,p,field)
                self.assertEqual(a['files'],b['files']);self.assertEqual(a['top'],b['top'])

    def test_aw5_p16_input_and_feedback_delays_explicit(self):
        g=geometry(32,16)
        self.assertEqual((g['initial_term_seeds'],g['input_delay'],g['pointwise_accept'],g['physical_first']),
            (2,5,41,78))
        self.assertEqual((g['warm_interval'],g['feedback_fifo_rows'],g['correction_cache_latency'],g['cache_margin']),
            (126,4,40,0))
        self.assertEqual(geometry(64,16)['feedback_fifo_rows'],4)
        self.assertEqual(geometry(128,16)['feedback_fifo_rows'],0)

    def test_small_lane_dependent_table_indices_and_widths(self):
        for n,p in ((32,16),(64,16),(128,16),(32,8)):
            b=prepare(n,p);source=b['files'][b['top']+'.sv'];rw=(n//p).bit_length()-1;pw=p.bit_length()-1
            self.assertNotIn('[-',source)
            self.assertEqual(b['parameters']['P'],p)
            for lane in range(p):
                fixed=bit_reverse(lane,pw)*(n//p)%p
                self.assertIn(f"A_table[protocol_pw_epoch[0]][({pw}'d{fixed}",source)
            term=b['files']['genefer_stream27_term_context_param_v2.sv']
            self.assertIn("2'(pointwise_row)",term);self.assertNotIn('pointwise_row[1:0]',term)
            self.assertIn('SEEDS-3\'d1',term)
            # The +4 update target must not wrap to zero when ROW_W=1.
            self.assertIn("TARGET_W'(pointwise_row)+TARGET_W'(4)",term)
            self.assertIn("wide_target<TARGET_W'(ROWS)",term)


if __name__=='__main__':unittest.main()
