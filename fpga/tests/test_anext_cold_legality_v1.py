import unittest
from fpga.reference import anext_cold_legality_v1 as s

class ColdLegality(unittest.TestCase):
    def test_reversible_frozen_parent_and_public_failure_barrier(self):
        e=s.expected();self.assertEqual(len(e),3)
        text=e[s.TARGET]
        predicate=text[text.index('    always_comb begin'):text.index('    assign field_write_en')]
        self.assertNotIn('$signed(image_read_words',predicate)
        self.assertIn('capture_valid[0] && !input_legal',predicate)
        self.assertIn('image_read_valid!=read_due',predicate)
        self.assertIn('image_error || transfer_error',predicate)
        self.assertIn('!fault && !cancel',text)
        self.assertIn('if(fault)begin state<=FAILED;error<=1;done<=0;',text)
        self.assertIn('if(cancel)begin state<=IDLE;done<=0;error<=0;',text)
        self.assertIn('destination_words[lane*32+:32]<=source_words[lane*33+:32]',text)

    def test_full_signed33_bounds_before_truncation(self):
        for base in (300,598,131333,1000000000):
            for word in (-1,0,1,base-1):
                d=s.checked_destination([word]*16,base)
                self.assertEqual(d,[word & 0xffffffff]*16)
            for word in (-(1<<32),-2,base,base+1,(1<<32)-1):
                self.assertIsNone(s.checked_destination([word]*16,base))
            # Both truncate to apparently legal low bits; neither may advance.
            for word in ((1<<32)-1,-(1<<32)+7):
                self.assertIsNone(s.checked_destination([word]+[0]*15,base))

    def test_every_lane_must_be_legal_and_fault_abi_is_explicit(self):
        for lane in range(16):
            words=[7]*16;words[lane]=300
            self.assertIsNone(s.checked_destination(words,300))
        c=s.contract();self.assertEqual(c['numeric_fault_edge_delta'],1)
        self.assertEqual(c['raw_metadata_image_transfer_cancel_delta'],0)
        self.assertEqual(c['normal_cold_cycle_delta'],0);self.assertEqual(c['warm_cycle_delta'],0)
        self.assertTrue(c['retry_requires_complete_reload'])
        self.assertFalse(c['failed_whole_publication']);self.assertFalse(c['failed_cache_promotion'])

if __name__=='__main__':unittest.main()
