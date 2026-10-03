// S4 shared one-field warm composition; source/native/clock gates separate.
// P is explicit and shared with probes. CONTEXTS=2 remains a rejected hook.
module genefer_stream27_shared_warm_aw16_p16_f1_storage_combo_quarantine_v1_timing10_v1_protected_field100_v1 #(parameter int AW=16,P=16,CONTEXTS=2,QUARANTINE_REPLICAS=1,BOUNDARY_INPUTREG=1,MONT_FACTORED=1,COMM_STAGE_SHARED_MLAB=1,CORR_SERIAL_BFS=2) (
 input logic clk,rst_n,in_slot_valid,frame_start,context_in,correction_context,
 input logic [1:0] context_enabled,
 input logic [7:0] generation_in,input logic [15:0] live_generation,
 input logic [31:0] base_in,
 input logic [15:0] epoch_in,correction_epoch,
 input logic correction_valid,input logic [7:0] correction_generation,
 input logic [511:0] data_in,c0_in,c1_in,
 output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,out_error_fast,
 output logic [7:0] generation_out,output logic [431:0] data_out,
 output logic [15:0] out_epoch,
 output logic commit_valid,commit_frame_start,
 output logic [7:0] commit_generation,output logic [15:0] commit_epoch,
 output logic [431:0] commit_data,
 output logic [2:0] owner_count,output logic frame_accept,correction_accept,
 output logic out_context,commit_context,
 output logic [1:0] correction_bank,pointwise_bank,sink_bank,
 output logic [11:0] output_row,
 output logic [31:0] cycle_count,frame_count);
 wire [31:0] protocol_correction_base;
 localparam int ROW_W=12,ROWS=4096,LANES=16;
 logic controller_error;
 wire stop=out_error_fast;
 wire [1:0] transform_quarantine;
 logic [ROW_W:0] input_remaining;
 logic [ROW_W-1:0] input_row;
 logic [7:0] active_generation;logic active_context;
 logic [31:0] active_base,high_base;
 logic [15:0] active_epoch;
 logic [511:0] high_correction;
 wire [511:0] ordered_c0,ordered_high;
 logic c1_pending,small_capture,seed_running;
 logic [1:0] seed_row;
 logic [26:0] high_owner,small_first_owner,seed_owner;
 logic [15:0] table_epoch[0:3];logic [7:0] table_generation[0:3];logic table_context[0:3];
 logic [3:0] tables_ready;
 logic [1:0] payload_reserved,payload_ready;
 logic [26:0] payload_owner[0:1];
 logic [26:0] A_table[0:1][0:LANES-1],B_table[0:1][0:LANES-1];
 logic [8:0] child_error,child_pending;
 logic admission_bad,join_bad;
 wire raw_begin=rst_n && in_slot_valid && frame_start && !stop;
 wire [31:0] digit_base=frame_start ? base_in : active_base;
 wire [24:0] digit_generation=frame_start ? {context_in,epoch_in,generation_in} : {active_context,active_epoch,active_generation};
 wire [ROW_W-1:0] digit_row=frame_start ? ROW_W'(0) : input_row;
 wire accepted=rst_n && in_slot_valid && !stop && (!frame_start || frame_accept);
 wire accepted_correction=rst_n && correction_valid && correction_accept && !stop;
 wire boundary_slot=(accepted_correction || c1_pending) && !stop;
 wire [31:0] boundary_base=accepted_correction ? protocol_correction_base : high_base;
 wire [26:0] boundary_owner=accepted_correction ? {correction_bank,correction_context,correction_epoch,correction_generation} : high_owner;
 wire protocol_frame_accept,protocol_correction_accept,protocol_commit,protocol_pw_accept;
 wire [15:0] protocol_pw_epoch,protocol_sink_epoch;
 wire [ROW_W-1:0] protocol_pw_row,protocol_sink_row;
 wire protocol_error,protocol_pending;
 assign frame_accept=protocol_frame_accept;assign correction_accept=protocol_correction_accept;
 assign out_error=controller_error;
 assign out_error_fast=protocol_error;
 assign fault_pending=out_error_fast || (|child_pending) || protocol_pending || (!stop && (admission_bad || join_bad));
 function automatic logic correction_ok(input logic [31:0] word,input logic [31:0] limit);
  logic signed [32:0] wide_value;logic [32:0] magnitude;
  begin wide_value=$signed({word[31],word});magnitude=word[31] ? 33'(-wide_value) : 33'(wide_value);
   correction_ok=magnitude<={1'b0,limit};end
 endfunction
 // Exact uint32(base-1) identity: base0 must retain unsigned underflow.
 function automatic logic correction_c0_ok(input logic [31:0] word,input logic [31:0] base);
  logic signed [32:0] wide_value;logic [32:0] magnitude;
  begin wide_value=$signed({word[31],word});magnitude=word[31] ? 33'(-wide_value) : 33'(wide_value);
   correction_c0_ok=(base==32'd0) || magnitude<{1'b0,base};end
 endfunction
 always_comb begin
  admission_bad=(frame_start && (!in_slot_valid || input_remaining!=0)) ||
   (in_slot_valid && !frame_start && input_remaining==0) || (!in_slot_valid && input_remaining!=0) ||
   (in_slot_valid && !frame_start && (context_in!=active_context || generation_in!=active_generation || epoch_in!=active_epoch));
  if(in_slot_valid)begin
   if(digit_base<32'd131077 || digit_base>32'd1000000000)admission_bad=1;
   for(int lane=0;lane<LANES;lane=lane+1)if(data_in[lane*32+:32]>=digit_base && data_in[lane*32+:32]!=32'hffffffff)admission_bad=1;
  end
  if(correction_valid)begin
   if(c1_pending || seed_running || payload_reserved[correction_context])admission_bad=1;
   for(int lane=0;lane<LANES;lane=lane+1)
    if(!correction_c0_ok(c0_in[lane*32+:32],protocol_correction_base) ||
       !correction_ok(c1_in[lane*32+:32],32'd131456))admission_bad=1;
  end
 end
 logic [LANES-1:0] digit_valid,digit_error,boundary_valid,boundary_error;
 logic [ROW_W+25:0] digit_tag[0:LANES-1];logic [26:0] boundary_tag[0:LANES-1];
 wire [431:0] digit_data,boundary_data;
 wire raw_digit_slot=&digit_valid,boundary_out_slot=&boundary_valid;
 wire digit_slot;wire [ROW_W+25:0] launch_tag;
 wire [431:0] launch_data;
 assign child_error[0]=|digit_error;assign child_error[1]=|boundary_error;
 always_comb begin
  child_pending[0]=(|digit_error) || ((|digit_valid) && !(&digit_valid));
  child_pending[1]=(|boundary_error) || ((|boundary_valid) && !(&boundary_valid));
  for(int lane=1;lane<LANES;lane=lane+1)begin
   if(raw_digit_slot && digit_tag[lane]!=digit_tag[0])child_pending[0]=1;
   if(boundary_out_slot && boundary_tag[lane]!=boundary_tag[0])child_pending[1]=1;
  end
 end
 for(genvar lane=0;lane<LANES;lane=lane+1)begin: reducers
  wire [31:0] digit_residue,boundary_residue;
  genefer_digit_reduce27_pipe #(.P(32'd69206017),.PAYLOAD_W(ROW_W+26)) digits (
   .clk,.rst_n,.in_valid(accepted),.digit(data_in[lane*32+:32]),
   .payload_in({digit_generation,frame_start,digit_row}),
   .out_valid(digit_valid[lane]),.out_error(digit_error[lane]),.residue(digit_residue),.payload_out(digit_tag[lane]));
  genefer_stream27_signed_boundary_inputreg_v1 #(.P(32'd69206017),.AW(16),.BLOCKS(LANES),.PAYLOAD_W(27)) boundary (
   .clk,.rst_n,.quarantine(stop),.in_valid(boundary_slot),.boundary_high(c1_pending && !accepted_correction),
   .correction(accepted_correction ? ordered_c0[lane*32+:32] : ordered_high[lane*32+:32]),.base(boundary_base),
   .payload_in(boundary_owner),.out_valid(boundary_valid[lane]),.out_error(boundary_error[lane]),
   .residue(boundary_residue),.payload_out(boundary_tag[lane]));
  assign digit_data[lane*27+:27]=digit_residue[26:0];
  assign boundary_data[lane*27+:27]=boundary_residue[26:0];
 end
 wire small_twist_slot,small_twist_start,small_slot,small_start;
 wire [26:0] small_twist_owner,small_owner;
 wire [431:0] small_twisted,small_data;
 genefer_stream27_mul_param_v1 #(.LANES(LANES),.GEN_W(27),.P(32'd69206017),.Q(32'd4225761281)) small_twist (
  .clk,.rst_n,.in_slot_valid(boundary_out_slot),.frame_start(1'b1),.quarantine(stop),
  .generation_in(boundary_tag[0]),.lhs(boundary_data),.rhs(432'h0d48f849038a8589705388adc562da55ecdae3ed15fca6c813a1e04a5e286e948088de21f184be001358d743078a2194fc0fa83fffc2),
  .out_slot_valid(small_twist_slot),.out_frame_start(small_twist_start),.out_error(child_error[2]),
  .fault_pending(child_pending[2]),.generation_out(small_twist_owner),.result(small_twisted));
 genefer_stream27_correction_serial_p16_f1_v1 #(.GEN_W(27)) correction_transform (
  .clk,.rst_n,.in_slot_valid(small_twist_slot),.frame_start(small_twist_start),.quarantine(stop),
  .context_enabled(1'b1),.generation_in(small_twist_owner),.live_generation(small_twist_owner),.data_in(small_twisted),
  .out_slot_valid(small_slot),.out_frame_start(small_start),.out_eligible(),.out_error(child_error[3]),
  .fault_pending(child_pending[3]),.generation_out(small_owner),.data_out(small_data));
 wire [447:0] input_wide,fwd_data,square_wide,inv_data;
 wire [431:0] canonical_spectrum,addA_rhs,addA_data,addB_data,squared;
 wire fwd_slot,fwd_start,addA_slot,addA_start,addB_slot,addB_start,square_slot,square_start,inv_slot,inv_start;
 wire [24:0] fwd_generation,addA_generation,addB_generation,square_generation,inv_generation;
 wire [26:0] protocol_payload_owner_next;
 wire [ROW_W-1:0] protocol_payload_row_next;
 logic [26:0] term_payload_owner;logic [ROW_W-1:0] term_payload_row;
 logic [26:0] term_payload_coeff;
 wire [ROW_W-1:0] term_payload_target_next=protocol_payload_row_next+ROW_W'(4);
 wire [ROW_W-1:0] pw_row=protocol_pw_row;
 logic [ROW_W-1:0] addA_row;logic [1:0] addA_bank;
 wire [ROW_W-1:0] seed_target=ROW_W'(seed_row);
 wire [ROW_W-1:0] term_target=pw_row+ROW_W'(4);
 wire [431:0] term_seed_coeff,term_seed_roots,term_next_coeff,term_next_roots,term_data;
 wire [26:0] term_factor;wire term_slot,term_start,term_cache_ready;
 wire [26:0] term_owner,term_cache_owner;wire [ROW_W-1:0] term_row;
  assign input_wide[0+:28]={1'b0,launch_data[0+:27]};
  assign ordered_c0[0+:32]=c0_in[0+:32];
  assign ordered_high[0+:32]=high_correction[0+:32];
  wire [27:0] raw_spectrum0=fwd_data[0+:28];
  assign canonical_spectrum[0+:27]=27'(raw_spectrum0>=28'd69206017 ? raw_spectrum0-28'd69206017 : raw_spectrum0);
  assign square_wide[0+:28]={1'b0,squared[0+:27]};
  assign data_out[0+:27]=inv_data[0+:27];
  assign addA_rhs[0+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[0+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[0+:27]=term_payload_coeff;
  assign input_wide[28+:28]={1'b0,launch_data[27+:27]};
  assign ordered_c0[32+:32]=c0_in[256+:32];
  assign ordered_high[32+:32]=high_correction[256+:32];
  wire [27:0] raw_spectrum1=fwd_data[28+:28];
  assign canonical_spectrum[27+:27]=27'(raw_spectrum1>=28'd69206017 ? raw_spectrum1-28'd69206017 : raw_spectrum1);
  assign square_wide[28+:28]={1'b0,squared[27+:27]};
  assign data_out[27+:27]=inv_data[28+:27];
  assign addA_rhs[27+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[27+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[27+:27]=term_payload_coeff;
  assign input_wide[56+:28]={1'b0,launch_data[54+:27]};
  assign ordered_c0[64+:32]=c0_in[128+:32];
  assign ordered_high[64+:32]=high_correction[128+:32];
  wire [27:0] raw_spectrum2=fwd_data[56+:28];
  assign canonical_spectrum[54+:27]=27'(raw_spectrum2>=28'd69206017 ? raw_spectrum2-28'd69206017 : raw_spectrum2);
  assign square_wide[56+:28]={1'b0,squared[54+:27]};
  assign data_out[54+:27]=inv_data[56+:27];
  assign addA_rhs[54+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[54+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[54+:27]=term_payload_coeff;
  assign input_wide[84+:28]={1'b0,launch_data[81+:27]};
  assign ordered_c0[96+:32]=c0_in[384+:32];
  assign ordered_high[96+:32]=high_correction[384+:32];
  wire [27:0] raw_spectrum3=fwd_data[84+:28];
  assign canonical_spectrum[81+:27]=27'(raw_spectrum3>=28'd69206017 ? raw_spectrum3-28'd69206017 : raw_spectrum3);
  assign square_wide[84+:28]={1'b0,squared[81+:27]};
  assign data_out[81+:27]=inv_data[84+:27];
  assign addA_rhs[81+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[81+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[81+:27]=term_payload_coeff;
  assign input_wide[112+:28]={1'b0,launch_data[108+:27]};
  assign ordered_c0[128+:32]=c0_in[64+:32];
  assign ordered_high[128+:32]=high_correction[64+:32];
  wire [27:0] raw_spectrum4=fwd_data[112+:28];
  assign canonical_spectrum[108+:27]=27'(raw_spectrum4>=28'd69206017 ? raw_spectrum4-28'd69206017 : raw_spectrum4);
  assign square_wide[112+:28]={1'b0,squared[108+:27]};
  assign data_out[108+:27]=inv_data[112+:27];
  assign addA_rhs[108+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[108+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[108+:27]=term_payload_coeff;
  assign input_wide[140+:28]={1'b0,launch_data[135+:27]};
  assign ordered_c0[160+:32]=c0_in[320+:32];
  assign ordered_high[160+:32]=high_correction[320+:32];
  wire [27:0] raw_spectrum5=fwd_data[140+:28];
  assign canonical_spectrum[135+:27]=27'(raw_spectrum5>=28'd69206017 ? raw_spectrum5-28'd69206017 : raw_spectrum5);
  assign square_wide[140+:28]={1'b0,squared[135+:27]};
  assign data_out[135+:27]=inv_data[140+:27];
  assign addA_rhs[135+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[135+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[135+:27]=term_payload_coeff;
  assign input_wide[168+:28]={1'b0,launch_data[162+:27]};
  assign ordered_c0[192+:32]=c0_in[192+:32];
  assign ordered_high[192+:32]=high_correction[192+:32];
  wire [27:0] raw_spectrum6=fwd_data[168+:28];
  assign canonical_spectrum[162+:27]=27'(raw_spectrum6>=28'd69206017 ? raw_spectrum6-28'd69206017 : raw_spectrum6);
  assign square_wide[168+:28]={1'b0,squared[162+:27]};
  assign data_out[162+:27]=inv_data[168+:27];
  assign addA_rhs[162+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[162+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[162+:27]=term_payload_coeff;
  assign input_wide[196+:28]={1'b0,launch_data[189+:27]};
  assign ordered_c0[224+:32]=c0_in[448+:32];
  assign ordered_high[224+:32]=high_correction[448+:32];
  wire [27:0] raw_spectrum7=fwd_data[196+:28];
  assign canonical_spectrum[189+:27]=27'(raw_spectrum7>=28'd69206017 ? raw_spectrum7-28'd69206017 : raw_spectrum7);
  assign square_wide[196+:28]={1'b0,squared[189+:27]};
  assign data_out[189+:27]=inv_data[196+:27];
  assign addA_rhs[189+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[189+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[189+:27]=term_payload_coeff;
  assign input_wide[224+:28]={1'b0,launch_data[216+:27]};
  assign ordered_c0[256+:32]=c0_in[32+:32];
  assign ordered_high[256+:32]=high_correction[32+:32];
  wire [27:0] raw_spectrum8=fwd_data[224+:28];
  assign canonical_spectrum[216+:27]=27'(raw_spectrum8>=28'd69206017 ? raw_spectrum8-28'd69206017 : raw_spectrum8);
  assign square_wide[224+:28]={1'b0,squared[216+:27]};
  assign data_out[216+:27]=inv_data[224+:27];
  assign addA_rhs[216+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[216+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[216+:27]=term_payload_coeff;
  assign input_wide[252+:28]={1'b0,launch_data[243+:27]};
  assign ordered_c0[288+:32]=c0_in[288+:32];
  assign ordered_high[288+:32]=high_correction[288+:32];
  wire [27:0] raw_spectrum9=fwd_data[252+:28];
  assign canonical_spectrum[243+:27]=27'(raw_spectrum9>=28'd69206017 ? raw_spectrum9-28'd69206017 : raw_spectrum9);
  assign square_wide[252+:28]={1'b0,squared[243+:27]};
  assign data_out[243+:27]=inv_data[252+:27];
  assign addA_rhs[243+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[243+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[243+:27]=term_payload_coeff;
  assign input_wide[280+:28]={1'b0,launch_data[270+:27]};
  assign ordered_c0[320+:32]=c0_in[160+:32];
  assign ordered_high[320+:32]=high_correction[160+:32];
  wire [27:0] raw_spectrum10=fwd_data[280+:28];
  assign canonical_spectrum[270+:27]=27'(raw_spectrum10>=28'd69206017 ? raw_spectrum10-28'd69206017 : raw_spectrum10);
  assign square_wide[280+:28]={1'b0,squared[270+:27]};
  assign data_out[270+:27]=inv_data[280+:27];
  assign addA_rhs[270+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[270+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[270+:27]=term_payload_coeff;
  assign input_wide[308+:28]={1'b0,launch_data[297+:27]};
  assign ordered_c0[352+:32]=c0_in[416+:32];
  assign ordered_high[352+:32]=high_correction[416+:32];
  wire [27:0] raw_spectrum11=fwd_data[308+:28];
  assign canonical_spectrum[297+:27]=27'(raw_spectrum11>=28'd69206017 ? raw_spectrum11-28'd69206017 : raw_spectrum11);
  assign square_wide[308+:28]={1'b0,squared[297+:27]};
  assign data_out[297+:27]=inv_data[308+:27];
  assign addA_rhs[297+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[297+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[297+:27]=term_payload_coeff;
  assign input_wide[336+:28]={1'b0,launch_data[324+:27]};
  assign ordered_c0[384+:32]=c0_in[96+:32];
  assign ordered_high[384+:32]=high_correction[96+:32];
  wire [27:0] raw_spectrum12=fwd_data[336+:28];
  assign canonical_spectrum[324+:27]=27'(raw_spectrum12>=28'd69206017 ? raw_spectrum12-28'd69206017 : raw_spectrum12);
  assign square_wide[336+:28]={1'b0,squared[324+:27]};
  assign data_out[324+:27]=inv_data[336+:27];
  assign addA_rhs[324+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[324+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[324+:27]=term_payload_coeff;
  assign input_wide[364+:28]={1'b0,launch_data[351+:27]};
  assign ordered_c0[416+:32]=c0_in[352+:32];
  assign ordered_high[416+:32]=high_correction[352+:32];
  wire [27:0] raw_spectrum13=fwd_data[364+:28];
  assign canonical_spectrum[351+:27]=27'(raw_spectrum13>=28'd69206017 ? raw_spectrum13-28'd69206017 : raw_spectrum13);
  assign square_wide[364+:28]={1'b0,squared[351+:27]};
  assign data_out[351+:27]=inv_data[364+:27];
  assign addA_rhs[351+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[351+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[351+:27]=term_payload_coeff;
  assign input_wide[392+:28]={1'b0,launch_data[378+:27]};
  assign ordered_c0[448+:32]=c0_in[224+:32];
  assign ordered_high[448+:32]=high_correction[224+:32];
  wire [27:0] raw_spectrum14=fwd_data[392+:28];
  assign canonical_spectrum[378+:27]=27'(raw_spectrum14>=28'd69206017 ? raw_spectrum14-28'd69206017 : raw_spectrum14);
  assign square_wide[392+:28]={1'b0,squared[378+:27]};
  assign data_out[378+:27]=inv_data[392+:27];
  assign addA_rhs[378+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[378+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[378+:27]=term_payload_coeff;
  assign input_wide[420+:28]={1'b0,launch_data[405+:27]};
  assign ordered_c0[480+:32]=c0_in[480+:32];
  assign ordered_high[480+:32]=high_correction[480+:32];
  wire [27:0] raw_spectrum15=fwd_data[420+:28];
  assign canonical_spectrum[405+:27]=27'(raw_spectrum15>=28'd69206017 ? raw_spectrum15-28'd69206017 : raw_spectrum15);
  assign square_wide[420+:28]={1'b0,squared[405+:27]};
  assign data_out[405+:27]=inv_data[420+:27];
  assign addA_rhs[405+:27]=A_table[fwd_generation[24]][{pw_row[8],pw_row[9],pw_row[10],pw_row[11]}];
  assign term_seed_coeff[405+:27]=B_table[seed_owner[24]][{seed_target[8],seed_target[9],seed_target[10],seed_target[11]}];
  assign term_next_coeff[405+:27]=term_payload_coeff;
 genefer_stream28_merged_ct_aw16_p16_f1_v1_shared_comm_mlab_v1 #(.GEN_W(25)) forward_transform (
  .clk,.rst_n,.in_slot_valid(digit_slot),.frame_start(digit_slot && launch_tag[ROW_W]),.quarantine(transform_quarantine[0]),
  .context_enabled(context_enabled[fwd_generation[24]]),.generation_in(launch_tag[ROW_W+25:ROW_W+1]),.live_generation({fwd_generation[24:8],(fwd_generation[24] ? live_generation[15:8] : live_generation[7:0])}),.data_in(input_wide),
  .out_slot_valid(fwd_slot),.out_frame_start(fwd_start),.out_eligible(),.out_error(child_error[4]),
  .fault_pending(child_pending[4]),.generation_out(fwd_generation),.data_out(fwd_data));
 assign digit_slot=raw_digit_slot;assign launch_data=digit_data;assign launch_tag=digit_tag[0];
 genefer_stream27_shared_term_roots_aw16_p16_f1_v1 term_roots (
  .clk,.rst_n,.seed_slot(seed_running),.seed_start(seed_running && seed_row==0),.seed_row,
  .pw_slot(fwd_slot),.pw_start(fwd_start),.pw_row(term_payload_row),
  .seed_R_roots(term_seed_roots),.next_seed_R_roots(term_next_roots),.update_R_factor(term_factor));
 genefer_stream27_term_context_param_v1_contexts_v1_storage2_v1_payload_lookahead_v1_select_token_v1 #(.AW(16),.LANES(LANES),.P(32'd69206017),.Q(32'd4225761281)) term_producer (
  .clk,.rst_n,.quarantine(stop),.seed_slot(seed_running),.seed_start(seed_running && seed_row==0),
  .seed_owner,.seed_row,.seed_coeff(term_seed_coeff),.seed_R_roots(term_seed_roots),
  .pointwise_slot(fwd_slot),.pointwise_start(fwd_start),.pointwise_owner({pointwise_bank,fwd_generation}),
  .pointwise_row(pw_row),.payload_owner(term_payload_owner),.payload_row(term_payload_row),.next_coeff(term_next_coeff),.next_seed_R_roots(term_next_roots),.update_R_factor(term_factor),
  .term_slot,.term_start,.term_owner,.term_row,.term_data,
  .cache_ready(term_cache_ready),.cache_owner(term_cache_owner),.out_error(child_error[5]),.fault_pending(child_pending[5]));
 genefer_stream27_add_param_v1 #(.GEN_W(25),.LANES(LANES),.P(32'd69206017)) add_A (
  .clk,.rst_n,.in_slot_valid(fwd_slot),.frame_start(fwd_start),.quarantine(stop),
  .generation_in(fwd_generation),.lhs(canonical_spectrum),.rhs(addA_rhs),
  .out_slot_valid(addA_slot),.out_frame_start(addA_start),.out_error(child_error[6]),
  .fault_pending(child_pending[6]),.generation_out(addA_generation),.result(addA_data));
 wire term_join_valid=term_slot && term_row==addA_row &&
  term_owner=={addA_bank,table_context[addA_bank],table_epoch[addA_bank],addA_generation[7:0]};
 genefer_stream27_add_param_v1 #(.GEN_W(25),.LANES(LANES),.P(32'd69206017)) add_B (
  .clk,.rst_n,.in_slot_valid(addA_slot && term_join_valid),.frame_start(addA_start),.quarantine(stop),
  .generation_in(addA_generation),.lhs(addA_data),.rhs(term_data),
  .out_slot_valid(addB_slot),.out_frame_start(addB_start),.out_error(child_error[7]),
  .fault_pending(child_pending[7]),.generation_out(addB_generation),.result(addB_data));
 genefer_stream27_square_p16_f1_v1_contexts_v1 #(.GEN_W(25)) pointwise_square (
  .clk,.rst_n,.in_slot_valid(addB_slot),.frame_start(addB_start),.quarantine(stop),
  .generation_in(addB_generation),.data_in(addB_data),.out_slot_valid(square_slot),.out_frame_start(square_start),
  .out_error(child_error[8]),.fault_pending(child_pending[8]),.generation_out(square_generation),.data_out(squared));
 wire inverse_error,inverse_pending;
 // Same-D, same-origin-edge transform-local sticky quarantine copies.
 genefer_stream27_quarantine_replicas_v1 #(.COPIES(2)) fault_replicas (
  .clk,.rst_n,.fault_set(out_error_fast),.quarantine(transform_quarantine));
 genefer_stream28_merged_gs_aw16_p16_f1_v1_shared_comm_mlab_v1_c2_inputreg_v1 #(.GEN_W(25)) inverse_transform (
  .clk,.rst_n,.in_slot_valid(square_slot),.frame_start(square_start),.quarantine(transform_quarantine[1]),
  .context_enabled(context_enabled[inv_generation[24]]),.generation_in(square_generation),.live_generation({inv_generation[24:8],(inv_generation[24] ? live_generation[15:8] : live_generation[7:0])}),.data_in(square_wide),
  .out_slot_valid(inv_slot),.out_frame_start(inv_start),.out_eligible(),.out_error(inverse_error),
  .fault_pending(inverse_pending),.generation_out(inv_generation),.data_out(inv_data));
 assign out_slot_valid=inv_slot && !stop;assign out_frame_start=inv_start && out_slot_valid;
 assign generation_out=inv_generation[7:0];assign out_context=inv_generation[24];assign out_epoch=inv_generation[23:8];assign output_row=protocol_sink_row;
 assign out_eligible=protocol_commit;
 always_comb begin
  join_bad=(fwd_slot && (!protocol_pw_accept || !tables_ready[pointwise_bank] ||
   table_epoch[pointwise_bank]!=protocol_pw_epoch || table_generation[pointwise_bank]!=fwd_generation[7:0] || table_context[pointwise_bank]!=fwd_generation[24] ||
   !payload_ready[fwd_generation[24]] ||
   payload_owner[fwd_generation[24]]!={pointwise_bank,fwd_generation})) ||
   (small_slot && small_capture && small_owner!=small_first_owner) ||
   (addA_slot && !term_join_valid);
 end
 genefer_stream27_epoch_protocol_contexts_v1_payload_lookahead_v1_protected_field100_v1 #(.CONTEXTS(2),.BANKS(4),.ROWS(ROWS),.POINTWISE_FIRST(4207),
  .SINK_FIRST(8417),.EPOCH_W(16)) epoch_protocol (
  .clk,.rst_n,.quarantine(stop),.fault_report_copies(transform_quarantine),.external_fault_pending(admission_bad || join_bad || (|child_pending) || inverse_pending),
  .frame_begin(raw_begin),.frame_context(context_in),.frame_epoch(epoch_in),.frame_generation(generation_in),.frame_base(base_in),
  .correction_valid,.correction_context,.correction_epoch,.correction_generation,
  .cache_ready(term_cache_ready),.cache_context(term_cache_owner[24]),.cache_epoch(term_cache_owner[23:8]),.cache_generation(term_cache_owner[7:0]),
  .pointwise_slot(fwd_slot),.pointwise_frame_start(fwd_start),.pointwise_context(fwd_generation[24]),
  .pointwise_epoch_in(fwd_generation[23:8]),.pointwise_generation(fwd_generation[7:0]),
  .sink_slot(out_slot_valid),.sink_frame_start(out_frame_start),.sink_context(out_context),.sink_epoch_in(out_epoch),.sink_generation(generation_out),
  .context_enabled,.live_generation,.frame_accept(protocol_frame_accept),.correction_accept(protocol_correction_accept),
  .correction_base(protocol_correction_base),.pointwise_accept(protocol_pw_accept),.commit_enable(protocol_commit),
  .pointwise_epoch(protocol_pw_epoch),.sink_epoch(protocol_sink_epoch),
  .pointwise_payload_owner_next(protocol_payload_owner_next),.pointwise_payload_row_next(protocol_payload_row_next),
  .pointwise_row(protocol_pw_row),.sink_row(protocol_sink_row),.correction_bank,.pointwise_bank,.sink_bank,.owner_count,.out_error(protocol_error),.fault_pending(protocol_pending));
 // Predict payload only; every authoritative owner/calendar check stays live.
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin term_payload_owner<=0;term_payload_row<=0;end
  else begin term_payload_owner<=protocol_payload_owner_next;term_payload_row<=protocol_payload_row_next;end
 end
 always_ff @(posedge clk)if(rst_n)begin
  term_payload_coeff<=B_table[protocol_payload_owner_next[24]][{term_payload_target_next[8],term_payload_target_next[9],term_payload_target_next[10],term_payload_target_next[11]}];
  if(!stop && small_slot && small_capture && small_owner[24]==protocol_payload_owner_next[24])
   term_payload_coeff<=small_data[27*int'(term_payload_target_next[ROW_W-1-:4])+:27];
 end
 // synthesis translate_off
 always @(negedge clk)if(rst_n && fwd_slot && !stop && protocol_pw_accept)begin
  if(term_payload_owner!={pointwise_bank,fwd_generation} || term_payload_row!=pw_row)
   $fatal(1,"C2_LOOKAHEAD_CURRENT_OWNER_ROW");
  if(term_payload_coeff!=B_table[fwd_generation[24]][{term_target[8],term_target[9],term_target[10],term_target[11]}])
   $fatal(1,"C2_LOOKAHEAD_CURRENT_B_COEFFICIENT");
 end
 // synthesis translate_on
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   input_remaining<=0;input_row<=0;c1_pending<=0;small_capture<=0;seed_running<=0;seed_row<=0;
   tables_ready<=0;payload_reserved<=0;payload_ready<=0;controller_error<=0;commit_valid<=0;commit_frame_start<=0;cycle_count<=0;frame_count<=0;
  end else begin
   cycle_count<=cycle_count+32'd1;commit_valid<=0;commit_frame_start<=0;
   // Report accepted sticky origin; NEVER requalify by later STOP.
   controller_error<=out_error_fast;
   if(!stop)begin
    c1_pending<=accepted_correction;
    if(accepted)begin
     if(frame_start)begin
      input_remaining<=(ROW_W+1)'(ROWS-1);input_row<=ROW_W'(1);
      active_base<=base_in;active_generation<=generation_in;active_epoch<=epoch_in;active_context<=context_in;
      frame_count<=frame_count+32'd1;
     end else begin input_remaining<=input_remaining-(ROW_W+1)'(1);input_row<=input_row+ROW_W'(1);end
    end
    if(accepted_correction)begin
     payload_reserved[correction_context]<=1;payload_ready[correction_context]<=0;
     high_correction<=c1_in;high_base<=protocol_correction_base;
     high_owner<={correction_bank,correction_context,correction_epoch,correction_generation};tables_ready[correction_bank]<=0;end
    if(seed_running)begin seed_row<=seed_row+2'd1;if(seed_row==3)seed_running<=0;end
    if(small_slot)begin
     if(!small_capture)payload_owner[small_owner[24]]<=small_owner;
     if(small_capture)B_table[small_owner[24]][0]<=small_data[0+:27];
     else A_table[small_owner[24]][0]<=small_data[0+:27];
     if(small_capture)B_table[small_owner[24]][1]<=small_data[216+:27];
     else A_table[small_owner[24]][1]<=small_data[216+:27];
     if(small_capture)B_table[small_owner[24]][2]<=small_data[108+:27];
     else A_table[small_owner[24]][2]<=small_data[108+:27];
     if(small_capture)B_table[small_owner[24]][3]<=small_data[324+:27];
     else A_table[small_owner[24]][3]<=small_data[324+:27];
     if(small_capture)B_table[small_owner[24]][4]<=small_data[54+:27];
     else A_table[small_owner[24]][4]<=small_data[54+:27];
     if(small_capture)B_table[small_owner[24]][5]<=small_data[270+:27];
     else A_table[small_owner[24]][5]<=small_data[270+:27];
     if(small_capture)B_table[small_owner[24]][6]<=small_data[162+:27];
     else A_table[small_owner[24]][6]<=small_data[162+:27];
     if(small_capture)B_table[small_owner[24]][7]<=small_data[378+:27];
     else A_table[small_owner[24]][7]<=small_data[378+:27];
     if(small_capture)B_table[small_owner[24]][8]<=small_data[27+:27];
     else A_table[small_owner[24]][8]<=small_data[27+:27];
     if(small_capture)B_table[small_owner[24]][9]<=small_data[243+:27];
     else A_table[small_owner[24]][9]<=small_data[243+:27];
     if(small_capture)B_table[small_owner[24]][10]<=small_data[135+:27];
     else A_table[small_owner[24]][10]<=small_data[135+:27];
     if(small_capture)B_table[small_owner[24]][11]<=small_data[351+:27];
     else A_table[small_owner[24]][11]<=small_data[351+:27];
     if(small_capture)B_table[small_owner[24]][12]<=small_data[81+:27];
     else A_table[small_owner[24]][12]<=small_data[81+:27];
     if(small_capture)B_table[small_owner[24]][13]<=small_data[297+:27];
     else A_table[small_owner[24]][13]<=small_data[297+:27];
     if(small_capture)B_table[small_owner[24]][14]<=small_data[189+:27];
     else A_table[small_owner[24]][14]<=small_data[189+:27];
     if(small_capture)B_table[small_owner[24]][15]<=small_data[405+:27];
     else A_table[small_owner[24]][15]<=small_data[405+:27];
     small_capture<=!small_capture;
     if(small_capture)begin seed_running<=1;seed_row<=0;seed_owner<=small_owner;
      table_epoch[small_owner[26:25]]<=small_owner[23:8];table_generation[small_owner[26:25]]<=small_owner[7:0];table_context[small_owner[26:25]]<=small_owner[24];
     end else small_first_owner<=small_owner;
    end
    if(fwd_slot)begin addA_row<=pw_row;addA_bank<=pointwise_bank;
     if(pw_row==ROW_W'(ROWS-1) && payload_owner[fwd_generation[24]]=={pointwise_bank,fwd_generation})begin
      payload_reserved[fwd_generation[24]]<=0;payload_ready[fwd_generation[24]]<=0;
     end
    end
    if(term_cache_ready && payload_reserved[term_cache_owner[24]] &&
       payload_owner[term_cache_owner[24]]==term_cache_owner)payload_ready[term_cache_owner[24]]<=1;
    if(term_cache_ready && table_epoch[term_cache_owner[26:25]]==term_cache_owner[23:8] &&
       table_generation[term_cache_owner[26:25]]==term_cache_owner[7:0] && table_context[term_cache_owner[26:25]]==term_cache_owner[24])tables_ready[term_cache_owner[26:25]]<=1;
    if(protocol_commit)begin commit_valid<=1;commit_frame_start<=out_frame_start;
     commit_generation<=generation_out;commit_epoch<=out_epoch;commit_context<=out_context;commit_data<=data_out;end
   end
  end
 end
 // synthesis translate_off
 initial if(AW!=16 || P!=LANES || CONTEXTS!=2 || QUARANTINE_REPLICAS!=1 || BOUNDARY_INPUTREG!=1 || MONT_FACTORED!=1 || COMM_STAGE_SHARED_MLAB!=1 || CORR_SERIAL_BFS!=2)$fatal(1,"S4_SHARED_GENERATED_PARAMETERS");
 // synthesis translate_on
 // synthesis translate_off
 always @(negedge clk)if(rst_n && transform_quarantine!={2{controller_error}})
  $fatal(1,"FIELD100_REPORT_COPY_ALIGNMENT_NOT_FAST_ORIGIN");
 // synthesis translate_on
endmodule
