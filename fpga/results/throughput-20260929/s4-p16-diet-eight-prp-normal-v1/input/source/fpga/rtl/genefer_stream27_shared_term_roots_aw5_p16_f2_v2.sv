module genefer_stream27_shared_term_roots_aw5_p16_f2_v2 (
 input logic clk,rst_n,seed_slot,seed_start,pw_slot,pw_start,
 input logic [1:0] seed_row,
 input logic [0:0] pw_row,
 output logic [431:0] seed_R_roots,next_seed_R_roots,
 output logic [26:0] update_R_factor);
 logic [431:0] roots[0:1],prefetched;
 wire [0:0] seed_address=1'(seed_row+2'd1);
 wire [0:0] following_address=pw_row+1'(5);
 assign seed_R_roots=seed_start ? 432'h09b4480ed17705c681e2074fc3d6f1bfbe2248089e1ea5f03e2b4334ceef096e222524ed2c9b825a831467449df317c1946003cf7401 : prefetched;
 assign next_seed_R_roots=pw_start ? 432'h09b4480ed17705c681e2074fc3d6f1bfbe2248089e1ea5f03e2b4334ceef096e222524ed2c9b825a831467449df317c1946003cf7401 : prefetched;
 assign update_R_factor=27'd58851265;
 initial begin
  roots[0]=432'h09b4480ed17705c681e2074fc3d6f1bfbe2248089e1ea5f03e2b4334ceef096e222524ed2c9b825a831467449df317c1946003cf7401;
  roots[1]=432'h0303204fa79bfda851490b15d6f77b6dfe111240984f5520f8155d25f4ef6b4962196718c6133ce755a91f424b5c1805e34d7b459652;
 end
 always_ff @(posedge clk)if(rst_n && (seed_slot || pw_slot))
  prefetched<=roots[seed_slot ? seed_address : following_address];
endmodule
