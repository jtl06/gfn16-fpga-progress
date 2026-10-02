module genefer_stream27_shared_term_roots_aw5_p8_f1_v2 (
 input logic clk,rst_n,seed_slot,seed_start,pw_slot,pw_start,
 input logic [1:0] seed_row,
 input logic [1:0] pw_row,
 output logic [215:0] seed_R_roots,next_seed_R_roots,
 output logic [26:0] update_R_factor);
 logic [215:0] roots[0:3],prefetched;
 wire [1:0] seed_address=2'(seed_row+2'd1);
 wire [1:0] following_address=pw_row+2'(5);
 assign seed_R_roots=seed_start ? 216'h24ad8ccbea4e6c511413b7dd7da1dfd04ccc05f6d09b8e4a0c8e38 : prefetched;
 assign next_seed_R_roots=pw_start ? 216'h24ad8ccbea4e6c511413b7dd7da1dfd04ccc05f6d09b8e4a0c8e38 : prefetched;
 assign update_R_factor=27'd4194242;
 initial begin
  roots[0]=216'h24ad8ccbea4e6c511413b7dd7da1dfd04ccc05f6d09b8e4a0c8e38;
  roots[1]=216'h54060625ff3f42031063819df3a598582c54f4fac039bb9418c88f;
  roots[2]=216'h2a8e5c8b2e347441f45b39c174b810cd5205e65603f008fba1fee2;
  roots[3]=216'h307003ca71ff8caffde8ac0043004259f4ffb4c1c155b883f548f1;
 end
 always_ff @(posedge clk)if(rst_n && (seed_slot || pw_slot))
  prefetched<=roots[seed_slot ? seed_address : following_address];
endmodule
