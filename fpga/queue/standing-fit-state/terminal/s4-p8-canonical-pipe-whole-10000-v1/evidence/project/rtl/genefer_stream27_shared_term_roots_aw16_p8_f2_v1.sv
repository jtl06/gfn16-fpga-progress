module genefer_stream27_shared_term_roots_aw16_p8_f2_v1 (
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
 assign seed_R_roots=seed_start ? 216'h52892a45b6dabc1e420a3c57bed32389089c0edf49ba870acaaf20 : prefetched;
 assign next_seed_R_roots=pw_start ? 216'h5d2ca764626b18084409bf177ee5cc47da46f7051e92f8982fa0ee : prefetched;
 initial begin
  roots[0]=216'h52892a45b6dabc1e420a3c57bed32389089c0edf49ba870acaaf20;
  roots[1]=216'h7754cee11d66285a54a1b4d56be16d1a0ad2dcbf062595133d4d5f;
  roots[2]=216'h7096f501f52165ad15470a7d573540f78e58610e9abdde60aa4435;
  roots[3]=216'h0bdd4d4e8c565d81148f8ffd6e2356305495b9f5d5bc5f794a7412;
  roots[4]=216'h28d3070aed9f24cbefe126a203f43501f079dfc25a759310b34d9f;
  roots[5]=216'h40d2f847eda0fcc2d8cda7c4e6677ebdaa10a84b10068f4a012e18;
  roots[6]=216'h712dd1c1e245cd9d89440c6ed79333e4889a036f5efedd58222456;
  roots[7]=216'h79504e60ddf63861876b33ef12b5d21d74463c51c0d34a23e796bd;
  roots[8]=216'h42a157e7b3d5082cbfbeba880841f1a492c24b6e09bb493aca96da;
  roots[9]=216'h41e4d107cb65e5600f68141e131537ecc85982675b557d9897504e;
  roots[10]=216'h756bfee15a8028fd3f8a20780ed43e072078bf1c4ac2f072a9a1f3;
  roots[11]=216'h22d6b42bad2980e860352313f97646a17a37abd10f2db43a1c497a;
  roots[12]=216'h5186ea25d722c120aab99c0aa8e205f90abfc0df13522cc997ba68;
  roots[13]=216'h735db7c19c490ca2cd192bc65cf28adf22af241c1b765c9093346f;
  roots[14]=216'h436ffa479a00bc797f1b30f01cb1515b92d6548e09b7486acb16f4;
  roots[15]=216'h510bc7c5e6870d6316e693bd23441793cc7d8d86db1565e89f5344;
  roots[16]=216'h48c32a46ef9abd5f27f9943b00e4fb1d9a611c4d1c258ac07d4ea9;
  roots[17]=216'h5f1de7a4244310b5dd22a9645bc10c7468def1734d0f2952601ad7;
  roots[18]=216'h7d8e6ec056322c4985f136ef41f449929c774dacd71ca5e91e6b44;
  roots[19]=216'h1d8b414c5697dd74dd0b91845ea473f7027201200f697fa214d00d;
  roots[20]=216'h336584299b4f81669c5e134c7457ad2c480ada7744a436736d7933;
  roots[21]=216'h0c113aee85d8a8de27e4a45b0382ceed7ca6a250cbb5beba8b482a;
  roots[22]=216'h2db149ea51d6c9b9d73d08e518727b495ab116d508f1a052e3cbf7;
  roots[23]=216'h13b7afed910a08c7faa12720abf62ec4ee3aa7629249e341b8c399;
  roots[24]=216'h58775764f91518eefcd0a240660108e12adf63db0626d4733d2573;
  roots[25]=216'h2c6b21aa7a9bd1d3b7ec85a90285cf65f24693421c8878e870f0e4;
  roots[26]=216'h2fc1c1ea0fc7c80934be3ef96856b825b0297b4a5c870650711f37;
  roots[27]=216'h454396075f8d4561116513fdd3706e8bf0f2ae825142d6d9d9a526;
  roots[28]=216'h128ab4edb6a968f6db2921449af20c73b4bef189ca107ababff0aa;
  roots[29]=216'h06ece60f2a63441cfb233c809bb8027b0600309f8056e54bf72358;
  roots[30]=216'h00e275cfebb14d7811c7111dc7329e15b8acbd49597be878d282f2;
  roots[31]=216'h2dd119aa4ddcd1b1e8fc89e2e0869f43f62c97818c85e1f27143c3;
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
   0:update_R_factor=27'd63927297;
   1:update_R_factor=27'd32246639;
   2:update_R_factor=27'd61318116;
   3:update_R_factor=27'd32694043;
   4:update_R_factor=27'd57300235;
   5:update_R_factor=27'd7886564;
   6:update_R_factor=27'd51421416;
   7:update_R_factor=27'd57059548;
   8:update_R_factor=27'd51154749;
   9:update_R_factor=27'd5702892;
   10:update_R_factor=27'd53311350;
   default:update_R_factor=27'd63927297;
  endcase
 end
endmodule
