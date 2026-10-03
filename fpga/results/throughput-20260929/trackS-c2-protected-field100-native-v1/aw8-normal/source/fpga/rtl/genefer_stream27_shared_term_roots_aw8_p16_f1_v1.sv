module genefer_stream27_shared_term_roots_aw8_p16_f1_v1 (
 input logic clk,rst_n,seed_slot,seed_start,pw_slot,pw_start,
 input logic [1:0] seed_row,
 input logic [3:0] pw_row,
 output logic [431:0] seed_R_roots,next_seed_R_roots,
 output logic [26:0] update_R_factor);
 (* ramstyle="M20K" *) logic [431:0] roots[0:15];
 logic [431:0] prefetched;
 wire [3:0] seed_target=4'(seed_row+2'd1);
 wire [3:0] following_target=pw_row+4'd5;
 wire [3:0] first_target=4'd4;
 wire [3:0] seed_address=4'(seed_target);
 wire [3:0] update_address=4'(following_target);
 assign seed_R_roots=seed_start ? 432'h0d754f8ed156147e377eb239104713ca082586bf57bb7f792890127a0677e13f3108daf492a6a16dc38728f8971ae15df4f2386161ba : prefetched;
 assign next_seed_R_roots=pw_start ? 432'h2ff0d32a81e5a13e492f9a36da21e2d184cba5cfc072679c11b30e1a3b98ad388cf0bd57062a551f5756329a1d39ad1aaa77e0cab105 : prefetched;
 initial begin
  roots[0]=432'h0d754f8ed156147e377eb239104713ca082586bf57bb7f792890127a0677e13f3108daf492a6a16dc38728f8971ae15df4f2386161ba;
  roots[1]=432'h2b81ef6b0fc219f027e603fb0351006cbce7f268e0eca5b0026b4b13af130e0a1da5fe718c0231ce941a580684b4ff87cb6d5b269256;
  roots[2]=432'h0f9cd1ce8c65cd4bbf1b98881ca4d895566ced559dc8d42866e57c304f9a2a760cc15450021775ffd0c55334ef5599da4d4fd8d65606;
  roots[3]=432'h195c614d5473dcfdc122a247dbc6b1062831df3b411a49bbfcb6ca6e432202b79bc56a1d6214bc53d0fc520ce875bed0c474fa077162;
  roots[4]=432'h2ff0d32a81e5a13e492f9a36da21e2d184cba5cfc072679c11b30e1a3b98ad388cf0bd57062a551f5756329a1d39ad1aaa77e0cab105;
  roots[5]=432'h7125d1e25b45c8ca0117a8bfdd205ee6befc23289714f2b13d61ab4d4d9a26d64cc0ebcfbb248608b70c85e4266f43d4e352e18395a5;
  roots[6]=432'h1ffa2aac80bab182647611b3715024c87d0366f0c24c42ebd677a4050e91cfde2dcc6ce376b46391461d71fe4451c0965938d154d8e7;
  roots[7]=432'h109cf1ae6c61d18bfc2990807ae3cfae048e0a3fd66e1289523db00694c90fad66e530c41f9be77c24f5b44e694976a0747d2011705d;
  roots[8]=432'h707348027197042374afbd916a26bab24430a9b7d9a65158eb35d6728f18822e1cf50dfd9820404d11f3d5fcc98540c27259dbd1b4c6;
  roots[9]=432'h5dec5ee4c274293ff8f51a00e175cb60884e93ef52c29291c7adaf3db2ada8c9aa5056aa71372ab1f081871cf7cf1cc7d69f4b252c18;
  roots[10]=432'h223c668c387335d9ce8d86c62e61e049f0cbf6c2489f58330c14fb46b48ea7a96e3061a6db35cb24b71362c22593a800327e6419b035;
  roots[11]=432'h125dc56e344759ffb3ea020982d463f03a7b81f910492d7a16da52062efc8fba2074cfc83ba806f8a31eda2ea424ba9dab06f86a9f22;
  roots[12]=432'h7da775c0cb114c60ce1d35e63c73159098a54ded5cce9740862d190dafb70eca092537bd291b085af217134cc51d96dda8ff786ae012;
  roots[13]=432'h5ee63544a3395d2f49a09c16cc029c2156b47bd59b6832c0b2f9a949fb9567408d59db61cb8693c6a4498b5a7ece9520b630100939ff;
  roots[14]=432'h780911617eddd909560520d53f724fe098be03ed51d329b9e59aca73730502119f658e550510355f77895cd816d46549100b12fdfe9f;
  roots[15]=432'h3fe082c883efac09d246c0c5b74700cf6e27e61286bae3eb48a384096a7bef52b08a022c3601ba79531a2c00a4ba80502111221bdddd;
 end
 always_ff @(posedge clk)if(rst_n && (seed_slot || pw_slot))
  prefetched<=roots[seed_slot ? seed_address : update_address];
 wire [1:0] group_index=pw_row[3:2];
 integer factor_index;
 always_comb begin factor_index=0;
  if(group_index[0:0]==1'd1)factor_index=1;
  case(factor_index)
   0:update_R_factor=27'd30539304;
   1:update_R_factor=27'd33946804;
   default:update_R_factor=27'd30539304;
  endcase
 end
endmodule
