module genefer_stream27_shared_term_roots_aw8_p16_f2_v1 (
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
 assign seed_R_roots=seed_start ? 432'h6930fc02e1e08482848bafcf6ea781bdac10484ad9a136a0cdd92d76218d6143ce597bc49910a76cf1bd6c02c8d2800115edf3df4243 : prefetched;
 assign next_seed_R_roots=pw_start ? 432'h4b014146a7d7dd0000f4a01fe181708c62d26e7416b300f12b9fe374bf32e17019a90c17129e9d1dc5389d38596c59410daf6be04a14 : prefetched;
 initial begin
  roots[0]=432'h6930fc02e1e08482848bafcf6ea781bdac10484ad9a136a0cdd92d76218d6143ce597bc49910a76cf1bd6c02c8d2800115edf3df4243;
  roots[1]=432'h427033c7b9f98c69369bb2f92ca0726c94f2326dc91f3fdade18064fb95e0610d444e6154aa35d56c40c30fe7ef9e0921a8189beafd0;
  roots[2]=432'h60227ea403b030bf32d9a839a4e77f8b74108e91c75318c3179ce91bcedb0c8e24a4f5c67fa1673021fe7b58c0b09547dfb42306097d;
  roots[3]=432'h15dd056d4c5f58811bda2ffc84d7a4ddbc0be448cd4139a259d8cd7719592124d4e00099edc00cc261b1a7d6ca4b059c381d407afc59;
  roots[4]=432'h4b014146a7d7dd0000f4a01fe181708c62d26e7416b300f12b9fe374bf32e17019a90c17129e9d1dc5389d38596c59410daf6be04a14;
  roots[5]=432'h4cbaf96670a0d8c0f22ea801ba43e76fba8392090bd14b8287d6913b17ace8a50a69cf74a486316b84adcdc06ac6485443e53979835a;
  roots[6]=432'h15b4c92d5166e11170d99df1e4e722ed701c2252464c386b3878f42dfe3c0a483885897bff8ef08021ab786ccb10f2d804bac10168a9;
  roots[7]=432'h67f945e308d749d6deac85442a83ced86686a4f38cd53b426758996f04ebc227628d3ff02c1821fa94f19f8a624c0f0a9a76c2aeb129;
  roots[8]=432'h5c6d83647a4f9872b8b6b1c8e9472a34521b3976051ff5d35e014710455e0dff5444ac16baaa9d28c134d156d9e5d58b0ba5a2a08b4d;
  roots[9]=432'h3e5be3683c839873488531b6ef7123067edc1f3099fe3e30c2383b2b2f8fcaa20e0c4fef42b62217c6794fdc315604da421010b9bdff;
  roots[10]=432'h7a5d3b60bc5898d2f5e325c143b674527a31f5b120032e18019a3e092f006ee21ff8436bb3b7b289a6d849b62576c986e08f5b25ee16;
  roots[11]=432'h6ecf64422e137cf6ef72a14211c271a27cb24bb0cabdc5eaaa4744386c1968fa7cd8d7b15aa529d4c543eb4e580296870dfb9320408f;
  roots[12]=432'h25406acb5ff2add4b11a0589dcd53c628858f3af5c84f42871617c4da1c66653c7389415962d9d4d553c231058fb9e418c9b7bd06c92;
  roots[13]=432'h382dad49024a5d6e1569925d52e1a55f50cbd4165b3849289af6dc24015b6b87d498375a3c3934b8967e099c30beccd0aadca9eca46c;
  roots[14]=432'h486c50e6fa75e9e04c32041679d613c9be3e06c8929900a1aedfed50f60c85e93e748c91172e8ddd30f0a2fee26ba090118d21ffce5d;
  roots[15]=432'h1b4786ec9f0f29f9f72180e11be639c74e394716954c8b49586e980e5af38e3ca19514c2741d87b190b5f888e9c0ef532c38019c7901;
 end
 always_ff @(posedge clk)if(rst_n && (seed_slot || pw_slot))
  prefetched<=roots[seed_slot ? seed_address : update_address];
 wire [1:0] group_index=pw_row[3:2];
 integer factor_index;
 always_comb begin factor_index=0;
  if(group_index[0:0]==1'd1)factor_index=1;
  case(factor_index)
   0:update_R_factor=27'd61418887;
   1:update_R_factor=27'd21006932;
   default:update_R_factor=27'd61418887;
  endcase
 end
endmodule
