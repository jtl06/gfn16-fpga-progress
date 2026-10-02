module genefer_stream27_shared_term_roots_aw16_p8_f1_v1 (
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
 assign seed_R_roots=seed_start ? 216'h251c31abdc79d0073421c1197be0fca28ce86baece36791a5930de : prefetched;
 assign next_seed_R_roots=pw_start ? 216'h31f89dca40ec4c9a7cd22eb065d11a9128e4addb462b417b5a97d2 : prefetched;
 initial begin
  roots[0]=216'h251c31abdc79d0073421c1197be0fca28ce86baece36791a5930de;
  roots[1]=216'h479c92078c6dc5e9c57204c751d787c6f4170721da118218ddcfbe;
  roots[2]=216'h0acb7c4f26907cbb616caa93d284216cbe83d2689884db990f648e;
  roots[3]=216'h464b5cc7b6946d8741ca1117c6d1d28c80cdae7044bf16bb881d2a;
  roots[4]=216'h681cfce37c6068f78170a30fd200ed3c40ea587853b1c8e9a9c6e4;
  roots[5]=216'h708af7a26ea111d607a8073f0b113824b8e0fb694d63b49a73896e;
  roots[6]=216'h64b0c2c3e9e7ac06fe9f41202c3643c7343f8719d23e77a9d8310c;
  roots[7]=216'h80efc9e06206c864f4b4b5616984395c9280d46e076e3d3b32385a;
  roots[8]=216'h5477fc05f10084963f25af381b6776c8321926fa01332a83f99ab1;
  roots[9]=216'h81708a4051eebc0bf9d9c080c4e4ec33246a799bd4fb9201808dc1;
  roots[10]=216'h7f9a49608cb6d96f5362141593d6b66e803132305f6bd8e03284e5;
  roots[11]=216'h514fbb065608a474852f336f5a375f86cc1c0f26df50b6c035e929;
  roots[12]=216'h0d8e594ece34de04ce8981662ee3e1f3a68bc18b83ecdfd3a26407;
  roots[13]=216'h818b3e804e98350107ff21df0033e793248b0d9bda4e6800d63301;
  roots[14]=216'h20f6feec6120297a672512b31b7155998add4ccf1385e7c9af4308;
  roots[15]=216'h1a9965ed2cd348994ad22ed6a5d1e7b84ecb08f69050781a15f0fe;
  roots[16]=216'h2d3074ead9f1692a96da9cad24c70fe8702602f24e037a0a5f90c0;
  roots[17]=216'h15e2706dc3b1f942a7bb99ab08a74567fa1f53011f1499183d6cde;
  roots[18]=216'h245b49cbf496cde55fe2855403c35cf6249c613bde675fb053140b;
  roots[19]=216'h069d350fac5964ec58baa474e8c7b1844811cf775d59a74074cb19;
  roots[20]=216'h66296143bad3ddff54fa021560d833f0d20181e60f78622230f3bd;
  roots[21]=216'h35fc21e9c07bc8ddec372642793174e16cd963d2db55adc0b54a49;
  roots[22]=216'h816b18a0529cf1e533b1855989e632be4c41a836e0e2925003adb7;
  roots[23]=216'h1da3c46ccb877821cd9fbdc64c234d822a9e4fbb11c1d1d1e7c5c7;
  roots[24]=216'h0a83554f2f955dfd8c42824e77c791b58e15c94e91915a91edd4af;
  roots[25]=216'h4d3ed506d825647ccdadb2664a64f3757c699150c34257a3b7b50d;
  roots[26]=216'h5a3fc625380740ef66dfa413242241310cbfd9ded181cf39efc61a;
  roots[27]=216'h29a0f12b4be1e0f5c16aa347d2c7d4a65a0d6b35165d9dc9544c48;
  roots[28]=216'h759b1561cc9d58265a013d34bff06da2c8fa4ba75910d090fde5ef;
  roots[29]=216'h033d31301859e166a02f152bfa33817f6097d01441b57ac3e950a9;
  roots[30]=216'h4c3f2c26f81a8140c9dd99e6c461ee6ac6ca32a7832815c3bafd49;
  roots[31]=216'h75b62541c93b5d7b7fc9929006e237482ac116fb0113812bfd8fdc;
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
   0:update_R_factor=27'd34377272;
   1:update_R_factor=27'd28794177;
   2:update_R_factor=27'd53142633;
   3:update_R_factor=27'd49242871;
   4:update_R_factor=27'd20188885;
   5:update_R_factor=27'd19786682;
   6:update_R_factor=27'd20650492;
   7:update_R_factor=27'd30003116;
   8:update_R_factor=27'd39479001;
   9:update_R_factor=27'd47669210;
   10:update_R_factor=27'd56137701;
   default:update_R_factor=27'd34377272;
  endcase
 end
endmodule
