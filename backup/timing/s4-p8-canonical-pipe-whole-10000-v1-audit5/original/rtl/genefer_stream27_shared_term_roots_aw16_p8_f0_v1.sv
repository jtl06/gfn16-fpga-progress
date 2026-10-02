module genefer_stream27_shared_term_roots_aw16_p8_f0_v1 (
 input logic clk,rst_n,seed_slot,seed_start,pw_slot,pw_start,
 input logic [1:0] seed_row,
 input logic [12:0] pw_row,
 output logic [215:0] seed_R_roots,next_seed_R_roots,
 output logic [26:0] update_R_factor);
 (* ramstyle="M20K" *) logic [215:0] roots[0:31];
 logic [215:0] prefetched;
 wire [12:0] seed_target=13'(seed_row+2'd1);
 wire [12:0] following_target=pw_row+13'd5;
 wire [12:0] first_target=13'd4;
 wire [4:0] seed_address=5'({seed_target[12-:3],seed_target[1:0]});
 wire [4:0] update_address=5'({following_target[12-:3],following_target[1:0]});
 assign seed_R_roots=seed_start ? 216'h28d70173e51fd800d7eae3e502c1e39b7d538c90db2d4faada560c : prefetched;
 assign next_seed_R_roots=pw_start ? 216'h38f03a11e1f8c4c43a4ecb78b64b5a1a2224bcbc1a541d6af57c54 : prefetched;
 initial begin
  roots[0]=216'h28d70173e51fd800d7eae3e502c1e39b7d538c90db2d4faada560c;
  roots[1]=216'h2e38a85338eafda923612edb93f551f84ae5c0f70f2db7d45a4907;
  roots[2]=216'h0e265ef73b34297b4a963496ad55c3d90ed784dea3a82c71cafa73;
  roots[3]=216'h2688d3342ee5a303f0260381fb5be7b43813097960a1cf422bc619;
  roots[4]=216'h01029838dfad023f13e69c1d83406c69af8272caae0cb5307e695b;
  roots[5]=216'h0e8f62172e13c57d3e8bb4582ea0c102f577dfa1dfd86cba44f26a;
  roots[6]=216'h2fcdca130646c5be3b38ac38990a4aac4446aa77efa978904ad0ef;
  roots[7]=216'ha359a26494cbb9a56baaaf528ac012be518da83670f1fe2821c03c;
  roots[8]=216'h66b8b24c28e9bd0f5dbac21448c722815cabafd4e8d8c96124e6d5;
  roots[9]=216'h97b10cc609de6de7e8d52702e57a85bc403f48786fa6f2a84b21ac;
  roots[10]=216'h0c3ad91778a4e4879ec7530c273725bb9cab488cc740c90d57e6e0;
  roots[11]=216'h9c78424570f7bcc9585acad4f4c3c4743117717a4c9d9f94ac4c0f;
  roots[12]=216'h082e3357fa399ea0072f0fff1a398c29365e7ad98fc0cb9c47e68e;
  roots[13]=216'h03e39df8838c4862ab9cd7aa8c838887cb1eef0718dde59324434f;
  roots[14]=216'h3d9e8a314c2ec2d64dd7093645324c1823467cfc2d1505389d5f5a;
  roots[15]=216'hc0baf720e8a1227a60ba94b3e8c9371314691d9dc1eb941e028d7e;
  roots[16]=216'h18cf4795e61714ccad854a6a4f744b3ec70698279d3b521a9895be;
  roots[17]=216'h9dc2eae547a2a932bc39bda878e809d38c8ec58ec236b23df929ba;
  roots[18]=216'ha2479ea4b70c324313c61b9d87546e49530236d623d2ce99c5a62e;
  roots[19]=216'h7022418afbb7d4c8e4c9cae366e22ec37f4a2790822e8825fa2efd;
  roots[20]=216'h2d218cf35bce6a38077d1cff107688df38bee419498258bd0fb4ea;
  roots[21]=216'h81ccb748c6691e527b0599b09f60cd0065765ff3c03e6b86383291;
  roots[22]=216'h150eead65e22ac92b5e551a94371bf8963580ed405dd1345845d99;
  roots[23]=216'h321edbf2bc24888966fd52d3207a895a863ed4af9a92b24aeda9b8;
  roots[24]=216'h99a60485cb3f7682c0a313a7ebbc1f81a80c0fcb4b07c9acdf06cc;
  roots[25]=216'h2d8572f34f51aa27c7731f0711b902b5ba6fa9491793595b4d94d6;
  roots[26]=216'h643e85ec782f4993a1fa318bc0dc750e12015e3e30ca012026bfdd;
  roots[27]=216'h92c30206a79fc4a131534fd9d5b6402af4c7faa1dad7e002e50401;
  roots[28]=216'ha67a65e430b34a1f9b5aa00c94c3a6c7b11b270a4ecda28c664bb0;
  roots[29]=216'h0c80fd776fe0589e5ac05034a819e0bbaa53e88b2f49432856d79c;
  roots[30]=216'h04a2bdb86ba851168389c12f8ee55c3404e4797fc281f6cdefc128;
  roots[31]=216'hc2606fa0b3f21045b0905b49ee14f79942f10cd805c8c0dd86e7e6;
 end
 always_ff @(posedge clk)if(rst_n && (seed_slot || pw_slot))
  prefetched<=roots[seed_slot ? seed_address : update_address];
 wire [10:0] group_index=pw_row[12:2];
 integer factor_index;
 always_comb begin factor_index=0;
  if(group_index[0:0]==1'd1)factor_index=1;
  if(group_index[1:0]==2'd3)factor_index=2;
  if(group_index[2:0]==3'd7)factor_index=3;
  if(group_index[3:0]==4'd15)factor_index=4;
  if(group_index[4:0]==5'd31)factor_index=5;
  if(group_index[5:0]==6'd63)factor_index=6;
  if(group_index[6:0]==7'd127)factor_index=7;
  if(group_index[7:0]==8'd255)factor_index=8;
  if(group_index[8:0]==9'd511)factor_index=9;
  if(group_index[9:0]==10'd1023)factor_index=10;
  case(factor_index)
   0:update_R_factor=27'd102538812;
   1:update_R_factor=27'd50729409;
   2:update_R_factor=27'd12857691;
   3:update_R_factor=27'd5804203;
   4:update_R_factor=27'd66686504;
   5:update_R_factor=27'd81954295;
   6:update_R_factor=27'd31527557;
   7:update_R_factor=27'd74810631;
   8:update_R_factor=27'd56326957;
   9:update_R_factor=27'd9866461;
   10:update_R_factor=27'd14349174;
   default:update_R_factor=27'd102538812;
  endcase
 end
endmodule
