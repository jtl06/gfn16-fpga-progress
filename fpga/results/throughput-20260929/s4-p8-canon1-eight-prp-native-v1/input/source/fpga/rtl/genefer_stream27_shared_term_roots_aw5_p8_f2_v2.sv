module genefer_stream27_shared_term_roots_aw5_p8_f2_v2 (
 input logic clk,rst_n,seed_slot,seed_start,pw_slot,pw_start,
 input logic [1:0] seed_row,
 input logic [1:0] pw_row,
 output logic [215:0] seed_R_roots,next_seed_R_roots,
 output logic [26:0] update_R_factor);
 logic [215:0] roots[0:3],prefetched;
 wire [1:0] seed_address=2'(seed_row+2'd1);
 wire [1:0] following_address=pw_row+2'(5);
 assign seed_R_roots=seed_start ? 216'h34ceef096e222524ed2c9b825a831467449df317c1946003cf7401 : prefetched;
 assign next_seed_R_roots=pw_start ? 216'h34ceef096e222524ed2c9b825a831467449df317c1946003cf7401 : prefetched;
 assign update_R_factor=27'd58851265;
 initial begin
  roots[0]=216'h34ceef096e222524ed2c9b825a831467449df317c1946003cf7401;
  roots[1]=216'h09b4480ed17705c681e2074fc3d6f1bfbe2248089e1ea5f03e2b43;
  roots[2]=216'h25f4ef6b4962196718c6133ce755a91f424b5c1805e34d7b459652;
  roots[3]=216'h0303204fa79bfda851490b15d6f77b6dfe111240984f5520f8155d;
 end
 always_ff @(posedge clk)if(rst_n && (seed_slot || pw_slot))
  prefetched<=roots[seed_slot ? seed_address : following_address];
endmodule
