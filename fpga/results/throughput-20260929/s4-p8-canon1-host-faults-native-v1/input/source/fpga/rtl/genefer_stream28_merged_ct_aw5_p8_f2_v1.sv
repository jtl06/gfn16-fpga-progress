// Connected P16-c CT: physical occupied rows are never filtered by eligibility.
module genefer_stream28_merged_ct_aw5_p8_f2_v1 #(parameter int GEN_W=8) (
 input logic clk,rst_n,in_slot_valid,frame_start,quarantine,context_enabled,
 input logic [GEN_W-1:0] generation_in,live_generation,
 input logic [223:0] data_in,
 output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,
 output logic [GEN_W-1:0] generation_out,
 output logic [223:0] data_out);
 localparam int STAGES=5,FRAME_T=4,PAIRS=4;
 logic [STAGES:0] slot,start; logic [GEN_W-1:0] generation[0:STAGES];
 logic [223:0] data[0:STAGES];
 logic [STAGES-1:0] stage_pending; logic aggregate_error;
 wire stop=quarantine || aggregate_error;
 assign slot[0]=in_slot_valid;assign start[0]=frame_start;
 assign generation[0]=generation_in;assign data[0]=data_in;
 assign out_error=aggregate_error;assign fault_pending=aggregate_error || (|stage_pending);
 assign out_slot_valid=slot[STAGES] && !stop;
 assign out_frame_start=start[STAGES] && out_slot_valid;
 assign generation_out=generation[STAGES];
 assign out_eligible=out_slot_valid && context_enabled && generation_out==live_generation;
 always_ff @(posedge clk or negedge rst_n)
   if(!rst_n)aggregate_error<=0;
   else if(!stop && (|stage_pending))aggregate_error<=1;
 if(1)begin: stage0
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [223:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[0]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  assign row_slot=slot[0];assign row_start=start[0];
  assign row_generation=generation[0];assign row_data=data[0];
  assign shuffle_pending=1'b0;
  wire [26:0] packed_roots;
  merged_stream27_root_ct_aw5_p8_f2_s0_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[0+:28]),.v(row_data[28+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[28+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[56+:28]),.v(row_data[84+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[56+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[112+:28]),.v(row_data[140+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[140+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[168+:28]),.v(row_data[196+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[168+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  assign slot[1]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[1]=start_pipe[5];assign generation[1]=generation_pipe[5];
  assign data[1]=bf_data;
  always_ff @(posedge clk or negedge rst_n)begin
   if(!rst_n)begin slot_pipe<=0;start_pipe<=0;local_error<=0;remaining<=0;end
   else begin
    if(!stop && (cadence_bad || shuffle_pending || (|pair_error) || bf_valid!={PAIRS{slot_pipe[5]}}))local_error<=1;
    if(stop)begin slot_pipe<=0;start_pipe<=0;end
    else begin
     slot_pipe<={slot_pipe[4:0],accept};start_pipe<={start_pipe[4:0],accept && row_start};
     generation_pipe[0]<=row_generation;
     for(int k=1;k<6;k=k+1)generation_pipe[k]<=generation_pipe[k-1];
     if(accept)begin
      if(row_start)begin remaining<=COUNT_W'(FRAME_T-1);owner_generation<=row_generation;end
      else remaining<=remaining-COUNT_W'(1);
     end
    end
   end
  end
 end
 if(1)begin: stage1
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [223:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[1]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  assign row_slot=slot[1];assign row_start=start[1];
  assign row_generation=generation[1];assign row_data=data[1];
  assign shuffle_pending=1'b0;
  wire [53:0] packed_roots;
  merged_stream27_root_ct_aw5_p8_f2_s1_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[0+:28]),.v(row_data[56+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[56+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[28+:28]),.v(row_data[84+:28]),.w(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[112+:28]),.v(row_data[168+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[140+:28]),.v(row_data[196+:28]),.w(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[140+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  assign slot[2]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[2]=start_pipe[5];assign generation[2]=generation_pipe[5];
  assign data[2]=bf_data;
  always_ff @(posedge clk or negedge rst_n)begin
   if(!rst_n)begin slot_pipe<=0;start_pipe<=0;local_error<=0;remaining<=0;end
   else begin
    if(!stop && (cadence_bad || shuffle_pending || (|pair_error) || bf_valid!={PAIRS{slot_pipe[5]}}))local_error<=1;
    if(stop)begin slot_pipe<=0;start_pipe<=0;end
    else begin
     slot_pipe<={slot_pipe[4:0],accept};start_pipe<={start_pipe[4:0],accept && row_start};
     generation_pipe[0]<=row_generation;
     for(int k=1;k<6;k=k+1)generation_pipe[k]<=generation_pipe[k-1];
     if(accept)begin
      if(row_start)begin remaining<=COUNT_W'(FRAME_T-1);owner_generation<=row_generation;end
      else remaining<=remaining-COUNT_W'(1);
     end
    end
   end
  end
 end
 if(1)begin: stage2
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [223:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[2]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  assign row_slot=slot[2];assign row_start=start[2];
  assign row_generation=generation[2];assign row_data=data[2];
  assign shuffle_pending=1'b0;
  wire [107:0] packed_roots;
  merged_stream27_root_ct_aw5_p8_f2_s2_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[0+:28]),.v(row_data[112+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[112+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[28+:28]),.v(row_data[140+:28]),.w(packed_roots[54+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[140+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[56+:28]),.v(row_data[168+:28]),.w(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[56+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[84+:28]),.v(row_data[196+:28]),.w(packed_roots[81+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[84+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  assign slot[3]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[3]=start_pipe[5];assign generation[3]=generation_pipe[5];
  assign data[3]=bf_data;
  always_ff @(posedge clk or negedge rst_n)begin
   if(!rst_n)begin slot_pipe<=0;start_pipe<=0;local_error<=0;remaining<=0;end
   else begin
    if(!stop && (cadence_bad || shuffle_pending || (|pair_error) || bf_valid!={PAIRS{slot_pipe[5]}}))local_error<=1;
    if(stop)begin slot_pipe<=0;start_pipe<=0;end
    else begin
     slot_pipe<={slot_pipe[4:0],accept};start_pipe<={start_pipe[4:0],accept && row_start};
     generation_pipe[0]<=row_generation;
     for(int k=1;k<6;k=k+1)generation_pipe[k]<=generation_pipe[k-1];
     if(accept)begin
      if(row_start)begin remaining<=COUNT_W'(FRAME_T-1);owner_generation<=row_generation;end
      else remaining<=remaining-COUNT_W'(1);
     end
    end
   end
  end
 end
 if(1)begin: stage3
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [223:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[3]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  logic [PAIRS-1:0] sh_slot,sh_start,sh_error,sh_pending;
  logic [GEN_W-1:0] sh_generation[0:PAIRS-1];
  logic shuffle_alignment_bad;
  assign row_slot=sh_slot[0];assign row_start=sh_start[0];assign row_generation=sh_generation[0];
  always_comb begin
   shuffle_alignment_bad=(|sh_slot) && (!(&sh_slot) || sh_start!={PAIRS{sh_start[0]}});
   for(int k=1;k<PAIRS;k=k+1)
    if((|sh_slot) && sh_generation[k]!=sh_generation[0])shuffle_alignment_bad=1;
  end
  assign shuffle_pending=(|sh_error) || (|sh_pending) || shuffle_alignment_bad;
  genefer_stream27_mdc_commutator_sm1_registered_v1 #(.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(2),.FRAME_T(FRAME_T),.CONTEXTS(1)) shuffle0 (
   .clk,.rst_n,.in_slot_valid(slot[3]),.frame_start(start[3]),.quarantine(stop),
   .upper_in(data[3][0+:28]),.lower_in(data[3][28+:28]),
   .upper_payload(1'b0),.lower_payload(1'b0),.context_in(1'b0),
   .generation_in(generation[3]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(sh_slot[0]),.out_frame_start(sh_start[0]),.out_eligible(),
   .out_error(sh_error[0]),.fault_pending(sh_pending[0]),
   .upper_out(row_data[0+:28]),.lower_out(row_data[28+:28]),
   .upper_payload_out(),.lower_payload_out(),.context_out(),
   .generation_out(sh_generation[0]));
  genefer_stream27_mdc_commutator_sm1_registered_v1 #(.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(2),.FRAME_T(FRAME_T),.CONTEXTS(1)) shuffle1 (
   .clk,.rst_n,.in_slot_valid(slot[3]),.frame_start(start[3]),.quarantine(stop),
   .upper_in(data[3][56+:28]),.lower_in(data[3][84+:28]),
   .upper_payload(1'b0),.lower_payload(1'b0),.context_in(1'b0),
   .generation_in(generation[3]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(sh_slot[1]),.out_frame_start(sh_start[1]),.out_eligible(),
   .out_error(sh_error[1]),.fault_pending(sh_pending[1]),
   .upper_out(row_data[56+:28]),.lower_out(row_data[84+:28]),
   .upper_payload_out(),.lower_payload_out(),.context_out(),
   .generation_out(sh_generation[1]));
  genefer_stream27_mdc_commutator_sm1_registered_v1 #(.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(2),.FRAME_T(FRAME_T),.CONTEXTS(1)) shuffle2 (
   .clk,.rst_n,.in_slot_valid(slot[3]),.frame_start(start[3]),.quarantine(stop),
   .upper_in(data[3][112+:28]),.lower_in(data[3][140+:28]),
   .upper_payload(1'b0),.lower_payload(1'b0),.context_in(1'b0),
   .generation_in(generation[3]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(sh_slot[2]),.out_frame_start(sh_start[2]),.out_eligible(),
   .out_error(sh_error[2]),.fault_pending(sh_pending[2]),
   .upper_out(row_data[112+:28]),.lower_out(row_data[140+:28]),
   .upper_payload_out(),.lower_payload_out(),.context_out(),
   .generation_out(sh_generation[2]));
  genefer_stream27_mdc_commutator_sm1_registered_v1 #(.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(2),.FRAME_T(FRAME_T),.CONTEXTS(1)) shuffle3 (
   .clk,.rst_n,.in_slot_valid(slot[3]),.frame_start(start[3]),.quarantine(stop),
   .upper_in(data[3][168+:28]),.lower_in(data[3][196+:28]),
   .upper_payload(1'b0),.lower_payload(1'b0),.context_in(1'b0),
   .generation_in(generation[3]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(sh_slot[3]),.out_frame_start(sh_start[3]),.out_eligible(),
   .out_error(sh_error[3]),.fault_pending(sh_pending[3]),
   .upper_out(row_data[168+:28]),.lower_out(row_data[196+:28]),
   .upper_payload_out(),.lower_payload_out(),.context_out(),
   .generation_out(sh_generation[3]));
  wire [107:0] packed_roots;
  merged_stream27_root_ct_aw5_p8_f2_s3_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[0+:28]),.v(row_data[28+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[28+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[56+:28]),.v(row_data[84+:28]),.w(packed_roots[54+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[56+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[112+:28]),.v(row_data[140+:28]),.w(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[140+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[168+:28]),.v(row_data[196+:28]),.w(packed_roots[81+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[168+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  assign slot[4]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[4]=start_pipe[5];assign generation[4]=generation_pipe[5];
  assign data[4]=bf_data;
  always_ff @(posedge clk or negedge rst_n)begin
   if(!rst_n)begin slot_pipe<=0;start_pipe<=0;local_error<=0;remaining<=0;end
   else begin
    if(!stop && (cadence_bad || shuffle_pending || (|pair_error) || bf_valid!={PAIRS{slot_pipe[5]}}))local_error<=1;
    if(stop)begin slot_pipe<=0;start_pipe<=0;end
    else begin
     slot_pipe<={slot_pipe[4:0],accept};start_pipe<={start_pipe[4:0],accept && row_start};
     generation_pipe[0]<=row_generation;
     for(int k=1;k<6;k=k+1)generation_pipe[k]<=generation_pipe[k-1];
     if(accept)begin
      if(row_start)begin remaining<=COUNT_W'(FRAME_T-1);owner_generation<=row_generation;end
      else remaining<=remaining-COUNT_W'(1);
     end
    end
   end
  end
 end
 if(1)begin: stage4
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [223:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[4]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  logic [PAIRS-1:0] sh_slot,sh_start,sh_error,sh_pending;
  logic [GEN_W-1:0] sh_generation[0:PAIRS-1];
  logic shuffle_alignment_bad;
  assign row_slot=sh_slot[0];assign row_start=sh_start[0];assign row_generation=sh_generation[0];
  always_comb begin
   shuffle_alignment_bad=(|sh_slot) && (!(&sh_slot) || sh_start!={PAIRS{sh_start[0]}});
   for(int k=1;k<PAIRS;k=k+1)
    if((|sh_slot) && sh_generation[k]!=sh_generation[0])shuffle_alignment_bad=1;
  end
  assign shuffle_pending=(|sh_error) || (|sh_pending) || shuffle_alignment_bad;
  genefer_stream27_mdc_commutator_sm1_registered_v1 #(.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(1),.FRAME_T(FRAME_T),.CONTEXTS(1)) shuffle0 (
   .clk,.rst_n,.in_slot_valid(slot[4]),.frame_start(start[4]),.quarantine(stop),
   .upper_in(data[4][0+:28]),.lower_in(data[4][56+:28]),
   .upper_payload(1'b0),.lower_payload(1'b0),.context_in(1'b0),
   .generation_in(generation[4]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(sh_slot[0]),.out_frame_start(sh_start[0]),.out_eligible(),
   .out_error(sh_error[0]),.fault_pending(sh_pending[0]),
   .upper_out(row_data[0+:28]),.lower_out(row_data[56+:28]),
   .upper_payload_out(),.lower_payload_out(),.context_out(),
   .generation_out(sh_generation[0]));
  genefer_stream27_mdc_commutator_sm1_registered_v1 #(.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(1),.FRAME_T(FRAME_T),.CONTEXTS(1)) shuffle1 (
   .clk,.rst_n,.in_slot_valid(slot[4]),.frame_start(start[4]),.quarantine(stop),
   .upper_in(data[4][28+:28]),.lower_in(data[4][84+:28]),
   .upper_payload(1'b0),.lower_payload(1'b0),.context_in(1'b0),
   .generation_in(generation[4]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(sh_slot[1]),.out_frame_start(sh_start[1]),.out_eligible(),
   .out_error(sh_error[1]),.fault_pending(sh_pending[1]),
   .upper_out(row_data[28+:28]),.lower_out(row_data[84+:28]),
   .upper_payload_out(),.lower_payload_out(),.context_out(),
   .generation_out(sh_generation[1]));
  genefer_stream27_mdc_commutator_sm1_registered_v1 #(.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(1),.FRAME_T(FRAME_T),.CONTEXTS(1)) shuffle2 (
   .clk,.rst_n,.in_slot_valid(slot[4]),.frame_start(start[4]),.quarantine(stop),
   .upper_in(data[4][112+:28]),.lower_in(data[4][168+:28]),
   .upper_payload(1'b0),.lower_payload(1'b0),.context_in(1'b0),
   .generation_in(generation[4]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(sh_slot[2]),.out_frame_start(sh_start[2]),.out_eligible(),
   .out_error(sh_error[2]),.fault_pending(sh_pending[2]),
   .upper_out(row_data[112+:28]),.lower_out(row_data[168+:28]),
   .upper_payload_out(),.lower_payload_out(),.context_out(),
   .generation_out(sh_generation[2]));
  genefer_stream27_mdc_commutator_sm1_registered_v1 #(.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(1),.FRAME_T(FRAME_T),.CONTEXTS(1)) shuffle3 (
   .clk,.rst_n,.in_slot_valid(slot[4]),.frame_start(start[4]),.quarantine(stop),
   .upper_in(data[4][140+:28]),.lower_in(data[4][196+:28]),
   .upper_payload(1'b0),.lower_payload(1'b0),.context_in(1'b0),
   .generation_in(generation[4]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(sh_slot[3]),.out_frame_start(sh_start[3]),.out_eligible(),
   .out_error(sh_error[3]),.fault_pending(sh_pending[3]),
   .upper_out(row_data[140+:28]),.lower_out(row_data[196+:28]),
   .upper_payload_out(),.lower_payload_out(),.context_out(),
   .generation_out(sh_generation[3]));
  wire [107:0] packed_roots;
  merged_stream27_root_ct_aw5_p8_f2_s4_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[0+:28]),.v(row_data[56+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[56+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[28+:28]),.v(row_data[84+:28]),.w(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[112+:28]),.v(row_data[168+:28]),.w(packed_roots[54+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd67239937),.Q(32'd4227727361),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[140+:28]),.v(row_data[196+:28]),.w(packed_roots[81+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[140+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  assign slot[5]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[5]=start_pipe[5];assign generation[5]=generation_pipe[5];
  assign data[5]=bf_data;
  always_ff @(posedge clk or negedge rst_n)begin
   if(!rst_n)begin slot_pipe<=0;start_pipe<=0;local_error<=0;remaining<=0;end
   else begin
    if(!stop && (cadence_bad || shuffle_pending || (|pair_error) || bf_valid!={PAIRS{slot_pipe[5]}}))local_error<=1;
    if(stop)begin slot_pipe<=0;start_pipe<=0;end
    else begin
     slot_pipe<={slot_pipe[4:0],accept};start_pipe<={start_pipe[4:0],accept && row_start};
     generation_pipe[0]<=row_generation;
     for(int k=1;k<6;k=k+1)generation_pipe[k]<=generation_pipe[k-1];
     if(accept)begin
      if(row_start)begin remaining<=COUNT_W'(FRAME_T-1);owner_generation<=row_generation;end
      else remaining<=remaining-COUNT_W'(1);
     end
    end
   end
  end
 end
 assign data_out[0+:28]=data[STAGES][0+:28];
 assign data_out[28+:28]=data[STAGES][56+:28];
 assign data_out[56+:28]=data[STAGES][28+:28];
 assign data_out[84+:28]=data[STAGES][84+:28];
 assign data_out[112+:28]=data[STAGES][112+:28];
 assign data_out[140+:28]=data[STAGES][168+:28];
 assign data_out[168+:28]=data[STAGES][140+:28];
 assign data_out[196+:28]=data[STAGES][196+:28];
endmodule
