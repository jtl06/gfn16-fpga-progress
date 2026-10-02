from pathlib import Path
import unittest
from fpga.reference import stream27_small_carry_structure as structure
from fpga.reference.stream27_small_carry_oracle import bounds


class SmallCarrySourceContract(unittest.TestCase):
    def test_pinned_sources_and_one_stage(self):
        proof=structure.validate()
        self.assertEqual(proof['register_stages'],1)
        self.assertEqual(proof['acceptance_to_registered_output_edge_offset'],0)
        self.assertEqual(proof['producer_to_consumer_edge_spacing'],1)

    def test_full_widths_and_input_guards(self):
        source=(structure.ROOT/structure.RTL).read_text()
        for token in ['input logic [31:0] base','input logic signed [32:0] y',
                      'input logic signed [2:0] carry_in','output logic signed [2:0] carry_out',
                      'base>=32\'(MIN_BASE) && base<=32\'d1000000000',
                      "carry_in>=-3'sd2 && y>=-Q_BOUND && y<=y_high",
                      '(!block_start || (y>=0 && y<radix))',
                      'total>=-two_radix && total<four_radix']:
            self.assertIn(token,source)
        legal=source.split('assign legal=',1)[1].split(';',1)[0]
        self.assertNotIn('digit_next',legal) # no result correction adder on feedback enable

    def test_valid_error_payload_bubble_reset_contract(self):
        source=(structure.ROOT/structure.RTL).read_text()
        for token in ['out_valid<=in_valid && legal','out_error<=in_valid && !legal',
                      'if(in_valid && legal)carry_out<=carry_next',
                      'if(!rst_n)begin out_valid<=0;out_error<=0;carry_out<=0;end',
                      'if(rst_n && in_valid)begin','payload_out<=payload_in',
                      'if(legal)digit<=digit_next[31:0]']:
            self.assertIn(token,source)
        self.assertNotIn('if(!rst_n)digit',source)

    def test_conservative_bound_matches_pinned_profile_proof(self):
        from fpga.reference import stream_ntt_blockwrap2_proposal as frozen
        for aw in range(5,17):
            for p in (8,16):
                minimum=max(2*(1<<aw)+5,(2*(2*(1<<aw)+24*p)+2)//3+1)
                for base in (minimum,604832956,10**9):
                    actual=bounds(aw,p,base)
                    old=frozen.bound_proof(1<<aw,p,base)
                    self.assertEqual(actual['coefficient_bound'],old['doubled_coefficient_bound'])
                    self.assertEqual(actual['exact_q2_bound'],old['q2_abs_bound'])
                    self.assertLessEqual(old['q2_abs_bound'],actual['q'])


if __name__=='__main__':unittest.main()
