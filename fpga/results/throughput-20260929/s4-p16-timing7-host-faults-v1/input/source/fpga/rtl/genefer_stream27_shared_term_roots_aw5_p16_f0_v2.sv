module genefer_stream27_shared_term_roots_aw5_p16_f0_v2 (
 input logic clk,rst_n,seed_slot,seed_start,pw_slot,pw_start,
 input logic [1:0] seed_row,
 input logic [0:0] pw_row,
 output logic [431:0] seed_R_roots,next_seed_R_roots,
 output logic [26:0] update_R_factor);
 logic [431:0] roots[0:1],prefetched;
 wire [0:0] seed_address=1'(seed_row+2'd1);
 wire [0:0] following_address=pw_row+1'(5);
 assign seed_R_roots=seed_start ? 432'h9e20aaa53beab06a943056ad7a10e0766373f1340dfd2994805acf59494f4dd6d61d717f12b5d01dc6f271c6b1b1c7811b0e2e1c9e3c : prefetched;
 assign next_seed_R_roots=pw_start ? 432'h9e20aaa53beab06a943056ad7a10e0766373f1340dfd2994805acf59494f4dd6d61d717f12b5d01dc6f271c6b1b1c7811b0e2e1c9e3c : prefetched;
 assign update_R_factor=27'd100663256;
 initial begin
  roots[0]=432'h9e20aaa53beab06a943056ad7a10e0766373f1340dfd2994805acf59494f4dd6d61d717f12b5d01dc6f271c6b1b1c7811b0e2e1c9e3c;
  roots[1]=432'h6ceef1cb6221cd370d1bbd1e5ca79d098e9c5eceadf7fd2081005d97e165e603d348df9cd0480c661c784cca00f66711fd00cc005fe8;
 end
 always_ff @(posedge clk)if(rst_n && (seed_slot || pw_slot))
  prefetched<=roots[seed_slot ? seed_address : following_address];
endmodule
