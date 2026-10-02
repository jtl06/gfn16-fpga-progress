import itertools
import unittest
from fpga.reference import anext_cancel_distribution_v1 as gen


class CancelPayloadSource(unittest.TestCase):
    def test_exact_literal_reversal_and_three_kernel_outputs(self):
        for kind,target in gen.TARGETS.items():
            source=gen.source(kind)
            self.assertEqual(source,(gen.ROOT/target).read_text())
            restored=source
            for old,new in reversed(gen.changes(kind)):restored=restored.replace(new,old)
            name={'word':'host_word_v1','image':'digit_image_v1','shell':'host_shell_v2'}[kind]
            self.assertEqual(restored,(gen.ROOT/('rtl/kernel/genefer_track_a4_'+name+'.sv')).read_text())

    def test_payload_selection_no_cancel_but_physical_acceptance_kills(self):
        source=gen.source('word')
        self.assertIn('mem_write_select=state==ACCESS && write_reg && !mem_error;',source)
        self.assertIn('mem_write_en=mem_write_select && !cancel;',source)
        for access,write,error,cancel in itertools.product((False,True),repeat=4):
            select,accept=gen.select_host(access,write,error,cancel)
            self.assertEqual(select,access and write and not error)
            self.assertEqual(accept,select and not cancel)
            if cancel:self.assertFalse(accept)

    def test_shell_all_raw_write_muxes_have_stable_owner_and_latekill(self):
        shell=gen.source('shell')
        for line in shell.splitlines():
            if any('wire '+x in line for x in ('[AW-1:0] write_offset','[15:0] write_mask','[511:0] write_words','[1:0] write_kind')):
                self.assertIn('hw_select ?',line);self.assertNotIn('hw_en ?',line)
        self.assertIn('arbitration_error<=arbitration_fault && !bus.cancel;',shell)
        self.assertIn('.cancel(bus.cancel),.configure,.clear_image',shell)

    def test_all_mutations_owned_by_same_edge_accept_no_cancel_reset(self):
        image=gen.source('image')
        self.assertIn('accept=rst_n && request && !fault && !cancel;',image)
        self.assertNotIn('if(cancel)',image)
        self.assertIn('error<=request && fault && !cancel;',image)
        for request,fault,cancel,rst in itertools.product((False,True),repeat=4):
            accepted,error=gen.image_accept(request,fault,cancel,rst)
            self.assertEqual((accepted,error),(rst and request and not fault and not cancel,rst and request and fault and not cancel))

    def test_no_recovery_or_cycle_inheritance_and_missing_site_rejected(self):
        ledger=gen.ledger()
        self.assertEqual(ledger['cycle_delta'],0)
        self.assertFalse(ledger['sequencer_reset_changed']);self.assertTrue(ledger['preserved_recovery_failure'])
        self.assertFalse(ledger['timing_claim']);self.assertFalse(ledger['native_pass'])
        with self.assertRaisesRegex(ValueError,'SINGLE_SITE'):gen.transform('wrong source',gen.changes('image'))


if __name__=='__main__':unittest.main()
