import unittest
from fpga.reference.stream27_warm_canonical_v1 import prepare,CANON_PIN,PRODUCTION_PIN
from fpga.reference.stream27_warm_canonical_native_v1 import compile_bench
from fpga.reference.stream27_warm_canonical_v2 import prepare as successor


class FinalImageSource(unittest.TestCase):
    def test_hardware_only_final_rows_and_explicit_read_latency(self):
        b=prepare(32);s=b['files'][b['top']+'.sv']
        self.assertIn('digit_epoch==final_epoch',s)
        self.assertIn('begin_canonical(canonical_request)',s)
        self.assertIn('busy=(active || finalizing || warm_done)',s)
        self.assertIn('done=canonical_done && publish_ok',s)
        self.assertIn('read_req(read_req && canonical_ready)',s)
        self.assertEqual(b['canonical_cost']['normal'],192)
        self.assertEqual(b['source_sha256']['rtl/kernel/genefer_stream27_canonical_image_v1.sv'],CANON_PIN)

    def test_actual_production_parent_not_reference_surrogate(self):
        b=prepare(256,paired=True);s=b['files'][b['top']+'.sv']
        self.assertIn('NTT_LANES(64)',s)
        self.assertIn('crtmont_prefill_pipe_v1',s)
        self.assertEqual(b['paired_production']['manifest_sha256'],PRODUCTION_PIN)
        self.assertTrue(b['paired_production']['RTL_sha256']['genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1.sv'].startswith('704f7fed'))

    def test_actual_materialized_words_and_production_comparator(self):
        s=compile_bench()
        self.assertIn('signed96(d.read_data,0)',s)
        self.assertIn('d.read_address_out==j-1',s)
        self.assertIn('d.canonical_cycles==finalization',s)
        self.assertIn('got==materialized[j]',s)
        self.assertIn('d.t5b_start=1',s)
        self.assertIn('S4_T5B_BIT_IDENTITY',s)

    def test_read_terminal_qualified_with_current_live_owner(self):
        b=successor(32);s=b['files'][b['top']+'.sv']
        self.assertIn('assign read_valid=canonical_read_valid && publish_ok && !out_error;',s)
        self.assertTrue(b['terminal_read_live_qualified'])


if __name__=='__main__':unittest.main()
