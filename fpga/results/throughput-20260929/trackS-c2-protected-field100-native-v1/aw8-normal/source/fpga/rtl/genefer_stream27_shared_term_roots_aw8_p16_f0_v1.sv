module genefer_stream27_shared_term_roots_aw8_p16_f0_v1 (
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
 assign seed_R_roots=seed_start ? 432'h0ae11877a3dcf80f3ae9e218a2e09397ad7d8d0acecb71446691d9358271124fb1e6269aa69f2cab4450e9a105e2cc64039189bf8dd0 : prefetched;
 assign next_seed_R_roots=pw_start ? 432'hb7a516e20b5d29ee39a32638cbbc399ac408cca7e4b94711a8d71f4d1867ef5cf308e0e44ac7e376c82574dc8b5164d708af7b5eea12 : prefetched;
 initial begin
  roots[0]=432'h0ae11877a3dcf80f3ae9e218a2e09397ad7d8d0acecb71446691d9358271124fb1e6269aa69f2cab4450e9a105e2cc64039189bf8dd0;
  roots[1]=432'h93c514e6875d6a8cfd39926058ebf0ce9611e62da71c8e595c6e367f27e7891b031530a3493deb96f1b3d1115985de5ea9d4726ac573;
  roots[2]=432'ha4379d04790c66e20f9487be0d86ec2ee8b27a2371504ed015f6273d3b1311589da40bd9e0e284c4071e4a16ac36bd904d09cc365ec8;
  roots[3]=432'h120a4bd6beb68e0f5632a21539c7bf4e569816359cf4f9b2a160cba3f7b42481098070839ad5ef8ccb651f2a235c1b27791c5150dc77;
  roots[4]=432'hb7a516e20b5d29ee39a32638cbbc399ac408cca7e4b94711a8d71f4d1867ef5cf308e0e44ac7e376c82574dc8b5164d708af7b5eea12;
  roots[5]=432'hb002f8a2ffa0f27b52669495b34b9145e41dd743c3ad57e5ca5505a52eafa45a2a110db37bc24990aa458442474f7816a839136af8df;
  roots[6]=432'h96e2b4a623a97110d4e9c1e562e79adaba9ca4a92eb37d5869905693f9a02680cc01040534437f59985341108597de40a92ae62adaa5;
  roots[7]=432'h6a5bf7abb48111dab95da8a8d46a6df0504241f66830f50939e160097d5677d0553ab5fb0d8d409e6276a7bb412b0904d400f5a57fe3;
  roots[8]=432'h39a34391cb97942a2a3cdebab882b0379539f90dcebc3b3468789b076da2f8124ba905cb42434697d9f4452a51775b1739413358d7db;
  roots[9]=432'h0b1215779dbd5a8d5ae51254a3763fb2d6c809a581c5200e075c0078921be9edbc88b15ff1cdd401e62175eecbd1428db42314897b9f;
  roots[10]=432'h6466bd0c732865b615f62d3d415570bd6ee1e852a66434c1737969c602e5e03fa3488f9833520cf9bbfe03ac103f8ac24a4d05f6b661;
  roots[11]=432'h5346184e973cfdef1faca61c0a8729bf92aac80e31ba88a808aeecb45239e275b8c96419f8377cc11091dae77dc4a3a4cfb171a609d3;
  roots[12]=432'h92d70c66a51e78a7ad514f0a55faf61ec4313c27dd39676a98d31403c95ab886d4b2b8a39f8ceb8c2151a5e565cb43d7ae5e434a3439;
  roots[13]=432'hc7c9d38006c594841c05d37c7f6b6f2c78221a716fc9db5046c49761f3f6ccc1812c9a2e34d0ba398b408c6427ee73e5bd5ff9885402;
  roots[14]=432'hbe42954137ad5cfd34f9c45960e481ce4cffc636c8ef0ca5221e6d7a4abca9b6a87115d7c5c14507650030a4eff9ebde660002734001;
  roots[15]=432'h4960938fd3ed96dc28aa087aead555f73ee541188486376daf391467cabb0c06a8a474d59f55654c32344feb49760327f2079941bf0e;
 end
 always_ff @(posedge clk)if(rst_n && (seed_slot || pw_slot))
  prefetched<=roots[seed_slot ? seed_address : update_address];
 wire [1:0] group_index=pw_row[3:2];
 integer factor_index;
 always_comb begin factor_index=0;
  if(group_index[0:0]==1'd1)factor_index=1;
  case(factor_index)
   0:update_R_factor=27'd32140278;
   1:update_R_factor=27'd553796;
   default:update_R_factor=27'd32140278;
  endcase
 end
endmodule
