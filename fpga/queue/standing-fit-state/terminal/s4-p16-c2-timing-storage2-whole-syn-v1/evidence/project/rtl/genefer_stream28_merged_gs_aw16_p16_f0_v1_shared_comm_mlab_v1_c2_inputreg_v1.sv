// Connected P16-c GS: physical occupied rows are never filtered by eligibility.
module genefer_stream28_merged_gs_aw16_p16_f0_v1_shared_comm_mlab_v1_c2_inputreg_v1 #(parameter int GEN_W=8) (
 input logic clk,rst_n,in_slot_valid,frame_start,quarantine,context_enabled,
 input logic [GEN_W-1:0] generation_in,live_generation,
 input logic [447:0] data_in,
 output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,
 output logic [GEN_W-1:0] generation_out,
 output logic [447:0] data_out);
 localparam int STAGES=16,FRAME_T=4096,PAIRS=8;
 logic [STAGES:0] slot,start; logic [GEN_W-1:0] generation[0:STAGES];
 logic [447:0] data[0:STAGES];
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
  logic [447:0] row_data,bf_data;
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
  wire [215:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s0_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[28+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[28+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[56+:28]),.v(row_data[84+:28]),.w(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[56+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[112+:28]),.v(row_data[140+:28]),.w(packed_roots[54+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[140+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[168+:28]),.v(row_data[196+:28]),.w(packed_roots[81+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[168+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[224+:28]),.v(row_data[252+:28]),.w(packed_roots[108+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[252+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[280+:28]),.v(row_data[308+:28]),.w(packed_roots[135+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[280+:28]),.y1(bf_data[308+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[336+:28]),.v(row_data[364+:28]),.w(packed_roots[162+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[336+:28]),.y1(bf_data[364+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[392+:28]),.v(row_data[420+:28]),.w(packed_roots[189+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[392+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
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
  logic [447:0] row_data,bf_data;
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
  wire [107:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s1_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[56+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[56+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[28+:28]),.v(row_data[84+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[112+:28]),.v(row_data[168+:28]),.w(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[140+:28]),.v(row_data[196+:28]),.w(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[140+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[224+:28]),.v(row_data[280+:28]),.w(packed_roots[54+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[280+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[252+:28]),.v(row_data[308+:28]),.w(packed_roots[54+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[252+:28]),.y1(bf_data[308+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[336+:28]),.v(row_data[392+:28]),.w(packed_roots[81+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[336+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[364+:28]),.v(row_data[420+:28]),.w(packed_roots[81+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[364+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
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
  logic [447:0] row_data,bf_data;
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
  wire [53:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s2_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[112+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[112+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[28+:28]),.v(row_data[140+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[140+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[56+:28]),.v(row_data[168+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[56+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[84+:28]),.v(row_data[196+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[84+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[224+:28]),.v(row_data[336+:28]),.w(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[336+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[252+:28]),.v(row_data[364+:28]),.w(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[252+:28]),.y1(bf_data[364+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[280+:28]),.v(row_data[392+:28]),.w(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[280+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[308+:28]),.v(row_data[420+:28]),.w(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[308+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
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
  logic [447:0] row_data,bf_data;
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
  assign row_slot=slot[3];assign row_start=start[3];
  assign row_generation=generation[3];assign row_data=data[3];
  assign shuffle_pending=1'b0;
  wire [26:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s3_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[224+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[224+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[28+:28]),.v(row_data[252+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[252+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[56+:28]),.v(row_data[280+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[56+:28]),.y1(bf_data[280+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[84+:28]),.v(row_data[308+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[84+:28]),.y1(bf_data[308+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[112+:28]),.v(row_data[336+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[112+:28]),.y1(bf_data[336+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[140+:28]),.v(row_data[364+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[140+:28]),.y1(bf_data[364+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[168+:28]),.v(row_data[392+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[168+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[196+:28]),.v(row_data[420+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[196+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
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
  logic [447:0] row_data,bf_data;
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
  wire [223:0] shared_upper_in,shared_lower_in,shared_upper_out,shared_lower_out;
  wire shared_shuffle_error,shared_shuffle_pending;
  assign shuffle_pending=shared_shuffle_error || shared_shuffle_pending;
  assign shared_upper_in[0+:28]=data[4][0+:28];
  assign shared_lower_in[0+:28]=data[4][28+:28];
  assign row_data[0+:28]=shared_upper_out[0+:28];
  assign row_data[28+:28]=shared_lower_out[0+:28];
  assign shared_upper_in[28+:28]=data[4][56+:28];
  assign shared_lower_in[28+:28]=data[4][84+:28];
  assign row_data[56+:28]=shared_upper_out[28+:28];
  assign row_data[84+:28]=shared_lower_out[28+:28];
  assign shared_upper_in[56+:28]=data[4][112+:28];
  assign shared_lower_in[56+:28]=data[4][140+:28];
  assign row_data[112+:28]=shared_upper_out[56+:28];
  assign row_data[140+:28]=shared_lower_out[56+:28];
  assign shared_upper_in[84+:28]=data[4][168+:28];
  assign shared_lower_in[84+:28]=data[4][196+:28];
  assign row_data[168+:28]=shared_upper_out[84+:28];
  assign row_data[196+:28]=shared_lower_out[84+:28];
  assign shared_upper_in[112+:28]=data[4][224+:28];
  assign shared_lower_in[112+:28]=data[4][252+:28];
  assign row_data[224+:28]=shared_upper_out[112+:28];
  assign row_data[252+:28]=shared_lower_out[112+:28];
  assign shared_upper_in[140+:28]=data[4][280+:28];
  assign shared_lower_in[140+:28]=data[4][308+:28];
  assign row_data[280+:28]=shared_upper_out[140+:28];
  assign row_data[308+:28]=shared_lower_out[140+:28];
  assign shared_upper_in[168+:28]=data[4][336+:28];
  assign shared_lower_in[168+:28]=data[4][364+:28];
  assign row_data[336+:28]=shared_upper_out[168+:28];
  assign row_data[364+:28]=shared_lower_out[168+:28];
  assign shared_upper_in[196+:28]=data[4][392+:28];
  assign shared_lower_in[196+:28]=data[4][420+:28];
  assign row_data[392+:28]=shared_upper_out[196+:28];
  assign row_data[420+:28]=shared_lower_out[196+:28];
  genefer_stream27_mdc_commutator_shared_mlab_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(1),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[4]),.frame_start(start[4]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[4]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [26:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s4_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[28+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[28+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[56+:28]),.v(row_data[84+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[56+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[112+:28]),.v(row_data[140+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[140+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[168+:28]),.v(row_data[196+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[168+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[224+:28]),.v(row_data[252+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[252+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[280+:28]),.v(row_data[308+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[280+:28]),.y1(bf_data[308+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[336+:28]),.v(row_data[364+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[336+:28]),.y1(bf_data[364+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[392+:28]),.v(row_data[420+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[392+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
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
 if(1)begin: stage5
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [447:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[5]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  wire [223:0] shared_upper_in,shared_lower_in,shared_upper_out,shared_lower_out;
  wire shared_shuffle_error,shared_shuffle_pending;
  assign shuffle_pending=shared_shuffle_error || shared_shuffle_pending;
  assign shared_upper_in[0+:28]=data[5][0+:28];
  assign shared_lower_in[0+:28]=data[5][56+:28];
  assign row_data[0+:28]=shared_upper_out[0+:28];
  assign row_data[56+:28]=shared_lower_out[0+:28];
  assign shared_upper_in[28+:28]=data[5][28+:28];
  assign shared_lower_in[28+:28]=data[5][84+:28];
  assign row_data[28+:28]=shared_upper_out[28+:28];
  assign row_data[84+:28]=shared_lower_out[28+:28];
  assign shared_upper_in[56+:28]=data[5][112+:28];
  assign shared_lower_in[56+:28]=data[5][168+:28];
  assign row_data[112+:28]=shared_upper_out[56+:28];
  assign row_data[168+:28]=shared_lower_out[56+:28];
  assign shared_upper_in[84+:28]=data[5][140+:28];
  assign shared_lower_in[84+:28]=data[5][196+:28];
  assign row_data[140+:28]=shared_upper_out[84+:28];
  assign row_data[196+:28]=shared_lower_out[84+:28];
  assign shared_upper_in[112+:28]=data[5][224+:28];
  assign shared_lower_in[112+:28]=data[5][280+:28];
  assign row_data[224+:28]=shared_upper_out[112+:28];
  assign row_data[280+:28]=shared_lower_out[112+:28];
  assign shared_upper_in[140+:28]=data[5][252+:28];
  assign shared_lower_in[140+:28]=data[5][308+:28];
  assign row_data[252+:28]=shared_upper_out[140+:28];
  assign row_data[308+:28]=shared_lower_out[140+:28];
  assign shared_upper_in[168+:28]=data[5][336+:28];
  assign shared_lower_in[168+:28]=data[5][392+:28];
  assign row_data[336+:28]=shared_upper_out[168+:28];
  assign row_data[392+:28]=shared_lower_out[168+:28];
  assign shared_upper_in[196+:28]=data[5][364+:28];
  assign shared_lower_in[196+:28]=data[5][420+:28];
  assign row_data[364+:28]=shared_upper_out[196+:28];
  assign row_data[420+:28]=shared_lower_out[196+:28];
  genefer_stream27_mdc_commutator_shared_mlab_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(2),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[5]),.frame_start(start[5]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[5]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [26:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s5_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[56+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[56+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[28+:28]),.v(row_data[84+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[112+:28]),.v(row_data[168+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[140+:28]),.v(row_data[196+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[140+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[224+:28]),.v(row_data[280+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[280+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[252+:28]),.v(row_data[308+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[252+:28]),.y1(bf_data[308+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[336+:28]),.v(row_data[392+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[336+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[364+:28]),.v(row_data[420+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[364+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
  assign slot[6]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[6]=start_pipe[5];assign generation[6]=generation_pipe[5];
  assign data[6]=bf_data;
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
 if(1)begin: stage6
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [447:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[6]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  wire [223:0] shared_upper_in,shared_lower_in,shared_upper_out,shared_lower_out;
  wire shared_shuffle_error,shared_shuffle_pending;
  assign shuffle_pending=shared_shuffle_error || shared_shuffle_pending;
  assign shared_upper_in[0+:28]=data[6][0+:28];
  assign shared_lower_in[0+:28]=data[6][112+:28];
  assign row_data[0+:28]=shared_upper_out[0+:28];
  assign row_data[112+:28]=shared_lower_out[0+:28];
  assign shared_upper_in[28+:28]=data[6][28+:28];
  assign shared_lower_in[28+:28]=data[6][140+:28];
  assign row_data[28+:28]=shared_upper_out[28+:28];
  assign row_data[140+:28]=shared_lower_out[28+:28];
  assign shared_upper_in[56+:28]=data[6][56+:28];
  assign shared_lower_in[56+:28]=data[6][168+:28];
  assign row_data[56+:28]=shared_upper_out[56+:28];
  assign row_data[168+:28]=shared_lower_out[56+:28];
  assign shared_upper_in[84+:28]=data[6][84+:28];
  assign shared_lower_in[84+:28]=data[6][196+:28];
  assign row_data[84+:28]=shared_upper_out[84+:28];
  assign row_data[196+:28]=shared_lower_out[84+:28];
  assign shared_upper_in[112+:28]=data[6][224+:28];
  assign shared_lower_in[112+:28]=data[6][336+:28];
  assign row_data[224+:28]=shared_upper_out[112+:28];
  assign row_data[336+:28]=shared_lower_out[112+:28];
  assign shared_upper_in[140+:28]=data[6][252+:28];
  assign shared_lower_in[140+:28]=data[6][364+:28];
  assign row_data[252+:28]=shared_upper_out[140+:28];
  assign row_data[364+:28]=shared_lower_out[140+:28];
  assign shared_upper_in[168+:28]=data[6][280+:28];
  assign shared_lower_in[168+:28]=data[6][392+:28];
  assign row_data[280+:28]=shared_upper_out[168+:28];
  assign row_data[392+:28]=shared_lower_out[168+:28];
  assign shared_upper_in[196+:28]=data[6][308+:28];
  assign shared_lower_in[196+:28]=data[6][420+:28];
  assign row_data[308+:28]=shared_upper_out[196+:28];
  assign row_data[420+:28]=shared_lower_out[196+:28];
  genefer_stream27_mdc_commutator_shared_mlab_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(4),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[6]),.frame_start(start[6]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[6]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [26:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s6_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[112+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[112+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[28+:28]),.v(row_data[140+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[140+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[56+:28]),.v(row_data[168+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[56+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[84+:28]),.v(row_data[196+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[84+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[224+:28]),.v(row_data[336+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[336+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[252+:28]),.v(row_data[364+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[252+:28]),.y1(bf_data[364+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[280+:28]),.v(row_data[392+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[280+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[308+:28]),.v(row_data[420+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[308+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
  assign slot[7]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[7]=start_pipe[5];assign generation[7]=generation_pipe[5];
  assign data[7]=bf_data;
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
 if(1)begin: stage7
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [447:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[7]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  wire [223:0] shared_upper_in,shared_lower_in,shared_upper_out,shared_lower_out;
  wire shared_shuffle_error,shared_shuffle_pending;
  assign shuffle_pending=shared_shuffle_error || shared_shuffle_pending;
  assign shared_upper_in[0+:28]=data[7][0+:28];
  assign shared_lower_in[0+:28]=data[7][224+:28];
  assign row_data[0+:28]=shared_upper_out[0+:28];
  assign row_data[224+:28]=shared_lower_out[0+:28];
  assign shared_upper_in[28+:28]=data[7][28+:28];
  assign shared_lower_in[28+:28]=data[7][252+:28];
  assign row_data[28+:28]=shared_upper_out[28+:28];
  assign row_data[252+:28]=shared_lower_out[28+:28];
  assign shared_upper_in[56+:28]=data[7][56+:28];
  assign shared_lower_in[56+:28]=data[7][280+:28];
  assign row_data[56+:28]=shared_upper_out[56+:28];
  assign row_data[280+:28]=shared_lower_out[56+:28];
  assign shared_upper_in[84+:28]=data[7][84+:28];
  assign shared_lower_in[84+:28]=data[7][308+:28];
  assign row_data[84+:28]=shared_upper_out[84+:28];
  assign row_data[308+:28]=shared_lower_out[84+:28];
  assign shared_upper_in[112+:28]=data[7][112+:28];
  assign shared_lower_in[112+:28]=data[7][336+:28];
  assign row_data[112+:28]=shared_upper_out[112+:28];
  assign row_data[336+:28]=shared_lower_out[112+:28];
  assign shared_upper_in[140+:28]=data[7][140+:28];
  assign shared_lower_in[140+:28]=data[7][364+:28];
  assign row_data[140+:28]=shared_upper_out[140+:28];
  assign row_data[364+:28]=shared_lower_out[140+:28];
  assign shared_upper_in[168+:28]=data[7][168+:28];
  assign shared_lower_in[168+:28]=data[7][392+:28];
  assign row_data[168+:28]=shared_upper_out[168+:28];
  assign row_data[392+:28]=shared_lower_out[168+:28];
  assign shared_upper_in[196+:28]=data[7][196+:28];
  assign shared_lower_in[196+:28]=data[7][420+:28];
  assign row_data[196+:28]=shared_upper_out[196+:28];
  assign row_data[420+:28]=shared_lower_out[196+:28];
  genefer_stream27_mdc_commutator_shared_mlab_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(8),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[7]),.frame_start(start[7]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[7]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [26:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s7_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[224+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[224+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[28+:28]),.v(row_data[252+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[252+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[56+:28]),.v(row_data[280+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[56+:28]),.y1(bf_data[280+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[84+:28]),.v(row_data[308+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[84+:28]),.y1(bf_data[308+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[112+:28]),.v(row_data[336+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[112+:28]),.y1(bf_data[336+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[140+:28]),.v(row_data[364+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[140+:28]),.y1(bf_data[364+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[168+:28]),.v(row_data[392+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[168+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[196+:28]),.v(row_data[420+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[196+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
  assign slot[8]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[8]=start_pipe[5];assign generation[8]=generation_pipe[5];
  assign data[8]=bf_data;
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
 if(1)begin: stage8
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [447:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[8]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  wire [223:0] shared_upper_in,shared_lower_in,shared_upper_out,shared_lower_out;
  wire shared_shuffle_error,shared_shuffle_pending;
  assign shuffle_pending=shared_shuffle_error || shared_shuffle_pending;
  assign shared_upper_in[0+:28]=data[8][0+:28];
  assign shared_lower_in[0+:28]=data[8][28+:28];
  assign row_data[0+:28]=shared_upper_out[0+:28];
  assign row_data[28+:28]=shared_lower_out[0+:28];
  assign shared_upper_in[28+:28]=data[8][56+:28];
  assign shared_lower_in[28+:28]=data[8][84+:28];
  assign row_data[56+:28]=shared_upper_out[28+:28];
  assign row_data[84+:28]=shared_lower_out[28+:28];
  assign shared_upper_in[56+:28]=data[8][112+:28];
  assign shared_lower_in[56+:28]=data[8][140+:28];
  assign row_data[112+:28]=shared_upper_out[56+:28];
  assign row_data[140+:28]=shared_lower_out[56+:28];
  assign shared_upper_in[84+:28]=data[8][168+:28];
  assign shared_lower_in[84+:28]=data[8][196+:28];
  assign row_data[168+:28]=shared_upper_out[84+:28];
  assign row_data[196+:28]=shared_lower_out[84+:28];
  assign shared_upper_in[112+:28]=data[8][224+:28];
  assign shared_lower_in[112+:28]=data[8][252+:28];
  assign row_data[224+:28]=shared_upper_out[112+:28];
  assign row_data[252+:28]=shared_lower_out[112+:28];
  assign shared_upper_in[140+:28]=data[8][280+:28];
  assign shared_lower_in[140+:28]=data[8][308+:28];
  assign row_data[280+:28]=shared_upper_out[140+:28];
  assign row_data[308+:28]=shared_lower_out[140+:28];
  assign shared_upper_in[168+:28]=data[8][336+:28];
  assign shared_lower_in[168+:28]=data[8][364+:28];
  assign row_data[336+:28]=shared_upper_out[168+:28];
  assign row_data[364+:28]=shared_lower_out[168+:28];
  assign shared_upper_in[196+:28]=data[8][392+:28];
  assign shared_lower_in[196+:28]=data[8][420+:28];
  assign row_data[392+:28]=shared_upper_out[196+:28];
  assign row_data[420+:28]=shared_lower_out[196+:28];
  genefer_stream27_mdc_commutator_shared_mlab_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(16),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[8]),.frame_start(start[8]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[8]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [26:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s8_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[28+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[28+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[56+:28]),.v(row_data[84+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[56+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[112+:28]),.v(row_data[140+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[140+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[168+:28]),.v(row_data[196+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[168+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[224+:28]),.v(row_data[252+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[252+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[280+:28]),.v(row_data[308+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[280+:28]),.y1(bf_data[308+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[336+:28]),.v(row_data[364+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[336+:28]),.y1(bf_data[364+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[392+:28]),.v(row_data[420+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[392+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
  assign slot[9]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[9]=start_pipe[5];assign generation[9]=generation_pipe[5];
  assign data[9]=bf_data;
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
 if(1)begin: stage9
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [447:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[9]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  wire [223:0] shared_upper_in,shared_lower_in,shared_upper_out,shared_lower_out;
  wire shared_shuffle_error,shared_shuffle_pending;
  assign shuffle_pending=shared_shuffle_error || shared_shuffle_pending;
  assign shared_upper_in[0+:28]=data[9][0+:28];
  assign shared_lower_in[0+:28]=data[9][56+:28];
  assign row_data[0+:28]=shared_upper_out[0+:28];
  assign row_data[56+:28]=shared_lower_out[0+:28];
  assign shared_upper_in[28+:28]=data[9][28+:28];
  assign shared_lower_in[28+:28]=data[9][84+:28];
  assign row_data[28+:28]=shared_upper_out[28+:28];
  assign row_data[84+:28]=shared_lower_out[28+:28];
  assign shared_upper_in[56+:28]=data[9][112+:28];
  assign shared_lower_in[56+:28]=data[9][168+:28];
  assign row_data[112+:28]=shared_upper_out[56+:28];
  assign row_data[168+:28]=shared_lower_out[56+:28];
  assign shared_upper_in[84+:28]=data[9][140+:28];
  assign shared_lower_in[84+:28]=data[9][196+:28];
  assign row_data[140+:28]=shared_upper_out[84+:28];
  assign row_data[196+:28]=shared_lower_out[84+:28];
  assign shared_upper_in[112+:28]=data[9][224+:28];
  assign shared_lower_in[112+:28]=data[9][280+:28];
  assign row_data[224+:28]=shared_upper_out[112+:28];
  assign row_data[280+:28]=shared_lower_out[112+:28];
  assign shared_upper_in[140+:28]=data[9][252+:28];
  assign shared_lower_in[140+:28]=data[9][308+:28];
  assign row_data[252+:28]=shared_upper_out[140+:28];
  assign row_data[308+:28]=shared_lower_out[140+:28];
  assign shared_upper_in[168+:28]=data[9][336+:28];
  assign shared_lower_in[168+:28]=data[9][392+:28];
  assign row_data[336+:28]=shared_upper_out[168+:28];
  assign row_data[392+:28]=shared_lower_out[168+:28];
  assign shared_upper_in[196+:28]=data[9][364+:28];
  assign shared_lower_in[196+:28]=data[9][420+:28];
  assign row_data[364+:28]=shared_upper_out[196+:28];
  assign row_data[420+:28]=shared_lower_out[196+:28];
  genefer_stream27_mdc_commutator_shared_mlab_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(32),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[9]),.frame_start(start[9]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[9]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [26:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s9_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[56+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[56+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[28+:28]),.v(row_data[84+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[112+:28]),.v(row_data[168+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[140+:28]),.v(row_data[196+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[140+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[224+:28]),.v(row_data[280+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[280+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[252+:28]),.v(row_data[308+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[252+:28]),.y1(bf_data[308+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[336+:28]),.v(row_data[392+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[336+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[364+:28]),.v(row_data[420+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[364+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
  assign slot[10]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[10]=start_pipe[5];assign generation[10]=generation_pipe[5];
  assign data[10]=bf_data;
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
 if(1)begin: stage10
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [447:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[10]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  wire [223:0] shared_upper_in,shared_lower_in,shared_upper_out,shared_lower_out;
  wire shared_shuffle_error,shared_shuffle_pending;
  assign shuffle_pending=shared_shuffle_error || shared_shuffle_pending;
  assign shared_upper_in[0+:28]=data[10][0+:28];
  assign shared_lower_in[0+:28]=data[10][112+:28];
  assign row_data[0+:28]=shared_upper_out[0+:28];
  assign row_data[112+:28]=shared_lower_out[0+:28];
  assign shared_upper_in[28+:28]=data[10][28+:28];
  assign shared_lower_in[28+:28]=data[10][140+:28];
  assign row_data[28+:28]=shared_upper_out[28+:28];
  assign row_data[140+:28]=shared_lower_out[28+:28];
  assign shared_upper_in[56+:28]=data[10][56+:28];
  assign shared_lower_in[56+:28]=data[10][168+:28];
  assign row_data[56+:28]=shared_upper_out[56+:28];
  assign row_data[168+:28]=shared_lower_out[56+:28];
  assign shared_upper_in[84+:28]=data[10][84+:28];
  assign shared_lower_in[84+:28]=data[10][196+:28];
  assign row_data[84+:28]=shared_upper_out[84+:28];
  assign row_data[196+:28]=shared_lower_out[84+:28];
  assign shared_upper_in[112+:28]=data[10][224+:28];
  assign shared_lower_in[112+:28]=data[10][336+:28];
  assign row_data[224+:28]=shared_upper_out[112+:28];
  assign row_data[336+:28]=shared_lower_out[112+:28];
  assign shared_upper_in[140+:28]=data[10][252+:28];
  assign shared_lower_in[140+:28]=data[10][364+:28];
  assign row_data[252+:28]=shared_upper_out[140+:28];
  assign row_data[364+:28]=shared_lower_out[140+:28];
  assign shared_upper_in[168+:28]=data[10][280+:28];
  assign shared_lower_in[168+:28]=data[10][392+:28];
  assign row_data[280+:28]=shared_upper_out[168+:28];
  assign row_data[392+:28]=shared_lower_out[168+:28];
  assign shared_upper_in[196+:28]=data[10][308+:28];
  assign shared_lower_in[196+:28]=data[10][420+:28];
  assign row_data[308+:28]=shared_upper_out[196+:28];
  assign row_data[420+:28]=shared_lower_out[196+:28];
  genefer_stream27_mdc_commutator_shared_mlab_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(64),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[10]),.frame_start(start[10]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[10]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [26:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s10_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[112+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[112+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[28+:28]),.v(row_data[140+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[140+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[56+:28]),.v(row_data[168+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[56+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[84+:28]),.v(row_data[196+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[84+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[224+:28]),.v(row_data[336+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[336+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[252+:28]),.v(row_data[364+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[252+:28]),.y1(bf_data[364+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[280+:28]),.v(row_data[392+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[280+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[308+:28]),.v(row_data[420+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[308+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
  assign slot[11]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[11]=start_pipe[5];assign generation[11]=generation_pipe[5];
  assign data[11]=bf_data;
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
 if(1)begin: stage11
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [447:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[11]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  wire [223:0] shared_upper_in,shared_lower_in,shared_upper_out,shared_lower_out;
  wire shared_shuffle_error,shared_shuffle_pending;
  assign shuffle_pending=shared_shuffle_error || shared_shuffle_pending;
  assign shared_upper_in[0+:28]=data[11][0+:28];
  assign shared_lower_in[0+:28]=data[11][224+:28];
  assign row_data[0+:28]=shared_upper_out[0+:28];
  assign row_data[224+:28]=shared_lower_out[0+:28];
  assign shared_upper_in[28+:28]=data[11][28+:28];
  assign shared_lower_in[28+:28]=data[11][252+:28];
  assign row_data[28+:28]=shared_upper_out[28+:28];
  assign row_data[252+:28]=shared_lower_out[28+:28];
  assign shared_upper_in[56+:28]=data[11][56+:28];
  assign shared_lower_in[56+:28]=data[11][280+:28];
  assign row_data[56+:28]=shared_upper_out[56+:28];
  assign row_data[280+:28]=shared_lower_out[56+:28];
  assign shared_upper_in[84+:28]=data[11][84+:28];
  assign shared_lower_in[84+:28]=data[11][308+:28];
  assign row_data[84+:28]=shared_upper_out[84+:28];
  assign row_data[308+:28]=shared_lower_out[84+:28];
  assign shared_upper_in[112+:28]=data[11][112+:28];
  assign shared_lower_in[112+:28]=data[11][336+:28];
  assign row_data[112+:28]=shared_upper_out[112+:28];
  assign row_data[336+:28]=shared_lower_out[112+:28];
  assign shared_upper_in[140+:28]=data[11][140+:28];
  assign shared_lower_in[140+:28]=data[11][364+:28];
  assign row_data[140+:28]=shared_upper_out[140+:28];
  assign row_data[364+:28]=shared_lower_out[140+:28];
  assign shared_upper_in[168+:28]=data[11][168+:28];
  assign shared_lower_in[168+:28]=data[11][392+:28];
  assign row_data[168+:28]=shared_upper_out[168+:28];
  assign row_data[392+:28]=shared_lower_out[168+:28];
  assign shared_upper_in[196+:28]=data[11][196+:28];
  assign shared_lower_in[196+:28]=data[11][420+:28];
  assign row_data[196+:28]=shared_upper_out[196+:28];
  assign row_data[420+:28]=shared_lower_out[196+:28];
  genefer_stream27_mdc_commutator_shared_mlab_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(128),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[11]),.frame_start(start[11]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[11]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [26:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s11_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[224+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[224+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[28+:28]),.v(row_data[252+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[252+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[56+:28]),.v(row_data[280+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[56+:28]),.y1(bf_data[280+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[84+:28]),.v(row_data[308+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[84+:28]),.y1(bf_data[308+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[112+:28]),.v(row_data[336+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[112+:28]),.y1(bf_data[336+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[140+:28]),.v(row_data[364+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[140+:28]),.y1(bf_data[364+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[168+:28]),.v(row_data[392+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[168+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[196+:28]),.v(row_data[420+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[196+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
  assign slot[12]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[12]=start_pipe[5];assign generation[12]=generation_pipe[5];
  assign data[12]=bf_data;
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
 if(1)begin: stage12
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [447:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[12]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  wire [223:0] shared_upper_in,shared_lower_in,shared_upper_out,shared_lower_out;
  wire shared_shuffle_error,shared_shuffle_pending;
  assign shuffle_pending=shared_shuffle_error || shared_shuffle_pending;
  assign shared_upper_in[0+:28]=data[12][0+:28];
  assign shared_lower_in[0+:28]=data[12][28+:28];
  assign row_data[0+:28]=shared_upper_out[0+:28];
  assign row_data[28+:28]=shared_lower_out[0+:28];
  assign shared_upper_in[28+:28]=data[12][56+:28];
  assign shared_lower_in[28+:28]=data[12][84+:28];
  assign row_data[56+:28]=shared_upper_out[28+:28];
  assign row_data[84+:28]=shared_lower_out[28+:28];
  assign shared_upper_in[56+:28]=data[12][112+:28];
  assign shared_lower_in[56+:28]=data[12][140+:28];
  assign row_data[112+:28]=shared_upper_out[56+:28];
  assign row_data[140+:28]=shared_lower_out[56+:28];
  assign shared_upper_in[84+:28]=data[12][168+:28];
  assign shared_lower_in[84+:28]=data[12][196+:28];
  assign row_data[168+:28]=shared_upper_out[84+:28];
  assign row_data[196+:28]=shared_lower_out[84+:28];
  assign shared_upper_in[112+:28]=data[12][224+:28];
  assign shared_lower_in[112+:28]=data[12][252+:28];
  assign row_data[224+:28]=shared_upper_out[112+:28];
  assign row_data[252+:28]=shared_lower_out[112+:28];
  assign shared_upper_in[140+:28]=data[12][280+:28];
  assign shared_lower_in[140+:28]=data[12][308+:28];
  assign row_data[280+:28]=shared_upper_out[140+:28];
  assign row_data[308+:28]=shared_lower_out[140+:28];
  assign shared_upper_in[168+:28]=data[12][336+:28];
  assign shared_lower_in[168+:28]=data[12][364+:28];
  assign row_data[336+:28]=shared_upper_out[168+:28];
  assign row_data[364+:28]=shared_lower_out[168+:28];
  assign shared_upper_in[196+:28]=data[12][392+:28];
  assign shared_lower_in[196+:28]=data[12][420+:28];
  assign row_data[392+:28]=shared_upper_out[196+:28];
  assign row_data[420+:28]=shared_lower_out[196+:28];
  genefer_stream27_mdc_commutator_shared_mlab_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(256),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[12]),.frame_start(start[12]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[12]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [26:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s12_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[28+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[28+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[56+:28]),.v(row_data[84+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[56+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[112+:28]),.v(row_data[140+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[140+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[168+:28]),.v(row_data[196+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[168+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[224+:28]),.v(row_data[252+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[252+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[280+:28]),.v(row_data[308+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[280+:28]),.y1(bf_data[308+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[336+:28]),.v(row_data[364+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[336+:28]),.y1(bf_data[364+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[392+:28]),.v(row_data[420+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[392+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
  assign slot[13]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[13]=start_pipe[5];assign generation[13]=generation_pipe[5];
  assign data[13]=bf_data;
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
 if(1)begin: stage13
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [447:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[13]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  wire [223:0] shared_upper_in,shared_lower_in,shared_upper_out,shared_lower_out;
  wire shared_shuffle_error,shared_shuffle_pending;
  assign shuffle_pending=shared_shuffle_error || shared_shuffle_pending;
  assign shared_upper_in[0+:28]=data[13][0+:28];
  assign shared_lower_in[0+:28]=data[13][56+:28];
  assign row_data[0+:28]=shared_upper_out[0+:28];
  assign row_data[56+:28]=shared_lower_out[0+:28];
  assign shared_upper_in[28+:28]=data[13][28+:28];
  assign shared_lower_in[28+:28]=data[13][84+:28];
  assign row_data[28+:28]=shared_upper_out[28+:28];
  assign row_data[84+:28]=shared_lower_out[28+:28];
  assign shared_upper_in[56+:28]=data[13][112+:28];
  assign shared_lower_in[56+:28]=data[13][168+:28];
  assign row_data[112+:28]=shared_upper_out[56+:28];
  assign row_data[168+:28]=shared_lower_out[56+:28];
  assign shared_upper_in[84+:28]=data[13][140+:28];
  assign shared_lower_in[84+:28]=data[13][196+:28];
  assign row_data[140+:28]=shared_upper_out[84+:28];
  assign row_data[196+:28]=shared_lower_out[84+:28];
  assign shared_upper_in[112+:28]=data[13][224+:28];
  assign shared_lower_in[112+:28]=data[13][280+:28];
  assign row_data[224+:28]=shared_upper_out[112+:28];
  assign row_data[280+:28]=shared_lower_out[112+:28];
  assign shared_upper_in[140+:28]=data[13][252+:28];
  assign shared_lower_in[140+:28]=data[13][308+:28];
  assign row_data[252+:28]=shared_upper_out[140+:28];
  assign row_data[308+:28]=shared_lower_out[140+:28];
  assign shared_upper_in[168+:28]=data[13][336+:28];
  assign shared_lower_in[168+:28]=data[13][392+:28];
  assign row_data[336+:28]=shared_upper_out[168+:28];
  assign row_data[392+:28]=shared_lower_out[168+:28];
  assign shared_upper_in[196+:28]=data[13][364+:28];
  assign shared_lower_in[196+:28]=data[13][420+:28];
  assign row_data[364+:28]=shared_upper_out[196+:28];
  assign row_data[420+:28]=shared_lower_out[196+:28];
  genefer_stream27_mdc_commutator_shared_mlab_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(512),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[13]),.frame_start(start[13]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[13]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [26:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s13_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[56+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[56+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[28+:28]),.v(row_data[84+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[112+:28]),.v(row_data[168+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[140+:28]),.v(row_data[196+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[140+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[224+:28]),.v(row_data[280+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[280+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[252+:28]),.v(row_data[308+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[252+:28]),.y1(bf_data[308+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[336+:28]),.v(row_data[392+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[336+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[364+:28]),.v(row_data[420+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[364+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
  assign slot[14]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[14]=start_pipe[5];assign generation[14]=generation_pipe[5];
  assign data[14]=bf_data;
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
 if(1)begin: stage14
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [447:0] row_data,bf_data;
  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[14]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));
  wire [223:0] shared_upper_in,shared_lower_in,shared_upper_out,shared_lower_out;
  wire shared_shuffle_error,shared_shuffle_pending;
  assign shuffle_pending=shared_shuffle_error || shared_shuffle_pending;
  assign shared_upper_in[0+:28]=data[14][0+:28];
  assign shared_lower_in[0+:28]=data[14][112+:28];
  assign row_data[0+:28]=shared_upper_out[0+:28];
  assign row_data[112+:28]=shared_lower_out[0+:28];
  assign shared_upper_in[28+:28]=data[14][28+:28];
  assign shared_lower_in[28+:28]=data[14][140+:28];
  assign row_data[28+:28]=shared_upper_out[28+:28];
  assign row_data[140+:28]=shared_lower_out[28+:28];
  assign shared_upper_in[56+:28]=data[14][56+:28];
  assign shared_lower_in[56+:28]=data[14][168+:28];
  assign row_data[56+:28]=shared_upper_out[56+:28];
  assign row_data[168+:28]=shared_lower_out[56+:28];
  assign shared_upper_in[84+:28]=data[14][84+:28];
  assign shared_lower_in[84+:28]=data[14][196+:28];
  assign row_data[84+:28]=shared_upper_out[84+:28];
  assign row_data[196+:28]=shared_lower_out[84+:28];
  assign shared_upper_in[112+:28]=data[14][224+:28];
  assign shared_lower_in[112+:28]=data[14][336+:28];
  assign row_data[224+:28]=shared_upper_out[112+:28];
  assign row_data[336+:28]=shared_lower_out[112+:28];
  assign shared_upper_in[140+:28]=data[14][252+:28];
  assign shared_lower_in[140+:28]=data[14][364+:28];
  assign row_data[252+:28]=shared_upper_out[140+:28];
  assign row_data[364+:28]=shared_lower_out[140+:28];
  assign shared_upper_in[168+:28]=data[14][280+:28];
  assign shared_lower_in[168+:28]=data[14][392+:28];
  assign row_data[280+:28]=shared_upper_out[168+:28];
  assign row_data[392+:28]=shared_lower_out[168+:28];
  assign shared_upper_in[196+:28]=data[14][308+:28];
  assign shared_lower_in[196+:28]=data[14][420+:28];
  assign row_data[308+:28]=shared_upper_out[196+:28];
  assign row_data[420+:28]=shared_lower_out[196+:28];
  genefer_stream27_mdc_commutator_shared_mlab_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(1024),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[14]),.frame_start(start[14]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[14]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [26:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s14_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[0+:28]),.v(row_data[112+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[112+:28]));
  assign pair_error[0]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[28+:28]),.v(row_data[140+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[140+:28]));
  assign pair_error[1]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[56+:28]),.v(row_data[168+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[56+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[84+:28]),.v(row_data[196+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[84+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[224+:28]),.v(row_data[336+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[336+:28]));
  assign pair_error[4]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[252+:28]),.v(row_data[364+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[252+:28]),.y1(bf_data[364+:28]));
  assign pair_error[5]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[280+:28]),.v(row_data[392+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[280+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_ntt_lazy28_butterfly_v1 #(.P(32'd104857601),.Q(32'd4190109697),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b1),
   .u(row_data[308+:28]),.v(row_data[420+:28]),.w(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[7]),.y0(bf_data[308+:28]),.y1(bf_data[420+:28]));
  assign pair_error[7]=1'b0;
  assign slot[15]=slot_pipe[5] && (&bf_valid) && !stop;
  assign start[15]=start_pipe[5];assign generation[15]=generation_pipe[5];
  assign data[15]=bf_data;
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
 if(1)begin: stage15
  logic row_slot,row_start,local_error,shuffle_pending;
  logic [GEN_W-1:0] row_generation;
  logic [447:0] row_data,bf_data;
  logic [6:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:6];
  logic [PAIRS-1:0] bf_valid,pair_error;
  localparam int COUNT_W=$clog2(FRAME_T+1);
  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;
  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
  wire accept=row_slot && !stop && !local_error;
  assign stage_pending[15]=local_error || shuffle_pending || (|pair_error) ||
   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[6]}}));
  wire [223:0] shared_upper_in,shared_lower_in,shared_upper_out,shared_lower_out;
  wire shared_shuffle_error,shared_shuffle_pending;
  assign shuffle_pending=shared_shuffle_error || shared_shuffle_pending;
  assign shared_upper_in[0+:28]=data[15][0+:28];
  assign shared_lower_in[0+:28]=data[15][224+:28];
  assign row_data[0+:28]=shared_upper_out[0+:28];
  assign row_data[224+:28]=shared_lower_out[0+:28];
  assign shared_upper_in[28+:28]=data[15][28+:28];
  assign shared_lower_in[28+:28]=data[15][252+:28];
  assign row_data[28+:28]=shared_upper_out[28+:28];
  assign row_data[252+:28]=shared_lower_out[28+:28];
  assign shared_upper_in[56+:28]=data[15][56+:28];
  assign shared_lower_in[56+:28]=data[15][280+:28];
  assign row_data[56+:28]=shared_upper_out[56+:28];
  assign row_data[280+:28]=shared_lower_out[56+:28];
  assign shared_upper_in[84+:28]=data[15][84+:28];
  assign shared_lower_in[84+:28]=data[15][308+:28];
  assign row_data[84+:28]=shared_upper_out[84+:28];
  assign row_data[308+:28]=shared_lower_out[84+:28];
  assign shared_upper_in[112+:28]=data[15][112+:28];
  assign shared_lower_in[112+:28]=data[15][336+:28];
  assign row_data[112+:28]=shared_upper_out[112+:28];
  assign row_data[336+:28]=shared_lower_out[112+:28];
  assign shared_upper_in[140+:28]=data[15][140+:28];
  assign shared_lower_in[140+:28]=data[15][364+:28];
  assign row_data[140+:28]=shared_upper_out[140+:28];
  assign row_data[364+:28]=shared_lower_out[140+:28];
  assign shared_upper_in[168+:28]=data[15][168+:28];
  assign shared_lower_in[168+:28]=data[15][392+:28];
  assign row_data[168+:28]=shared_upper_out[168+:28];
  assign row_data[392+:28]=shared_lower_out[168+:28];
  assign shared_upper_in[196+:28]=data[15][196+:28];
  assign shared_lower_in[196+:28]=data[15][420+:28];
  assign row_data[196+:28]=shared_upper_out[196+:28];
  assign row_data[420+:28]=shared_lower_out[196+:28];
  genefer_stream27_mdc_commutator_shared_mlab_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(2048),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[15]),.frame_start(start[15]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[15]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [26:0] packed_roots;
  merged_stream27_root_gs_aw16_p16_f0_s15_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  wire [27:0] raw_u0=row_data[0+:28],raw_v0=row_data[224+:28];
  wire [26:0] canonical_u0=27'(raw_u0>=28'd104857601 ? raw_u0-28'd104857601 : raw_u0);
  wire [26:0] canonical_v0=27'(raw_v0>=28'd104857601 ? raw_v0-28'd104857601 : raw_v0);
  wire [31:0] y0_0,y1_0;
  genefer_stream27_merged_final_gs_pair_inputreg_v1 #(.P(32'd104857601),.Q(32'd4190109697),
   .UPPER_SCALE(32'd56035902)) final_pair0 (
   .clk,.rst_n,.in_valid(accept),.u({5'b0,canonical_u0}),.v({5'b0,canonical_v0}),
   .normalized_lower_root({5'b0,packed_roots[0+:27]}),
   .out_valid(bf_valid[0]),.out_error(pair_error[0]),.y0(y0_0),.y1(y1_0));
  assign bf_data[0+:28]={1'b0,y0_0[26:0]};
  assign bf_data[224+:28]={1'b0,y1_0[26:0]};
  wire [27:0] raw_u1=row_data[28+:28],raw_v1=row_data[252+:28];
  wire [26:0] canonical_u1=27'(raw_u1>=28'd104857601 ? raw_u1-28'd104857601 : raw_u1);
  wire [26:0] canonical_v1=27'(raw_v1>=28'd104857601 ? raw_v1-28'd104857601 : raw_v1);
  wire [31:0] y0_1,y1_1;
  genefer_stream27_merged_final_gs_pair_inputreg_v1 #(.P(32'd104857601),.Q(32'd4190109697),
   .UPPER_SCALE(32'd56035902)) final_pair1 (
   .clk,.rst_n,.in_valid(accept),.u({5'b0,canonical_u1}),.v({5'b0,canonical_v1}),
   .normalized_lower_root({5'b0,packed_roots[0+:27]}),
   .out_valid(bf_valid[1]),.out_error(pair_error[1]),.y0(y0_1),.y1(y1_1));
  assign bf_data[28+:28]={1'b0,y0_1[26:0]};
  assign bf_data[252+:28]={1'b0,y1_1[26:0]};
  wire [27:0] raw_u2=row_data[56+:28],raw_v2=row_data[280+:28];
  wire [26:0] canonical_u2=27'(raw_u2>=28'd104857601 ? raw_u2-28'd104857601 : raw_u2);
  wire [26:0] canonical_v2=27'(raw_v2>=28'd104857601 ? raw_v2-28'd104857601 : raw_v2);
  wire [31:0] y0_2,y1_2;
  genefer_stream27_merged_final_gs_pair_inputreg_v1 #(.P(32'd104857601),.Q(32'd4190109697),
   .UPPER_SCALE(32'd56035902)) final_pair2 (
   .clk,.rst_n,.in_valid(accept),.u({5'b0,canonical_u2}),.v({5'b0,canonical_v2}),
   .normalized_lower_root({5'b0,packed_roots[0+:27]}),
   .out_valid(bf_valid[2]),.out_error(pair_error[2]),.y0(y0_2),.y1(y1_2));
  assign bf_data[56+:28]={1'b0,y0_2[26:0]};
  assign bf_data[280+:28]={1'b0,y1_2[26:0]};
  wire [27:0] raw_u3=row_data[84+:28],raw_v3=row_data[308+:28];
  wire [26:0] canonical_u3=27'(raw_u3>=28'd104857601 ? raw_u3-28'd104857601 : raw_u3);
  wire [26:0] canonical_v3=27'(raw_v3>=28'd104857601 ? raw_v3-28'd104857601 : raw_v3);
  wire [31:0] y0_3,y1_3;
  genefer_stream27_merged_final_gs_pair_inputreg_v1 #(.P(32'd104857601),.Q(32'd4190109697),
   .UPPER_SCALE(32'd56035902)) final_pair3 (
   .clk,.rst_n,.in_valid(accept),.u({5'b0,canonical_u3}),.v({5'b0,canonical_v3}),
   .normalized_lower_root({5'b0,packed_roots[0+:27]}),
   .out_valid(bf_valid[3]),.out_error(pair_error[3]),.y0(y0_3),.y1(y1_3));
  assign bf_data[84+:28]={1'b0,y0_3[26:0]};
  assign bf_data[308+:28]={1'b0,y1_3[26:0]};
  wire [27:0] raw_u4=row_data[112+:28],raw_v4=row_data[336+:28];
  wire [26:0] canonical_u4=27'(raw_u4>=28'd104857601 ? raw_u4-28'd104857601 : raw_u4);
  wire [26:0] canonical_v4=27'(raw_v4>=28'd104857601 ? raw_v4-28'd104857601 : raw_v4);
  wire [31:0] y0_4,y1_4;
  genefer_stream27_merged_final_gs_pair_inputreg_v1 #(.P(32'd104857601),.Q(32'd4190109697),
   .UPPER_SCALE(32'd56035902)) final_pair4 (
   .clk,.rst_n,.in_valid(accept),.u({5'b0,canonical_u4}),.v({5'b0,canonical_v4}),
   .normalized_lower_root({5'b0,packed_roots[0+:27]}),
   .out_valid(bf_valid[4]),.out_error(pair_error[4]),.y0(y0_4),.y1(y1_4));
  assign bf_data[112+:28]={1'b0,y0_4[26:0]};
  assign bf_data[336+:28]={1'b0,y1_4[26:0]};
  wire [27:0] raw_u5=row_data[140+:28],raw_v5=row_data[364+:28];
  wire [26:0] canonical_u5=27'(raw_u5>=28'd104857601 ? raw_u5-28'd104857601 : raw_u5);
  wire [26:0] canonical_v5=27'(raw_v5>=28'd104857601 ? raw_v5-28'd104857601 : raw_v5);
  wire [31:0] y0_5,y1_5;
  genefer_stream27_merged_final_gs_pair_inputreg_v1 #(.P(32'd104857601),.Q(32'd4190109697),
   .UPPER_SCALE(32'd56035902)) final_pair5 (
   .clk,.rst_n,.in_valid(accept),.u({5'b0,canonical_u5}),.v({5'b0,canonical_v5}),
   .normalized_lower_root({5'b0,packed_roots[0+:27]}),
   .out_valid(bf_valid[5]),.out_error(pair_error[5]),.y0(y0_5),.y1(y1_5));
  assign bf_data[140+:28]={1'b0,y0_5[26:0]};
  assign bf_data[364+:28]={1'b0,y1_5[26:0]};
  wire [27:0] raw_u6=row_data[168+:28],raw_v6=row_data[392+:28];
  wire [26:0] canonical_u6=27'(raw_u6>=28'd104857601 ? raw_u6-28'd104857601 : raw_u6);
  wire [26:0] canonical_v6=27'(raw_v6>=28'd104857601 ? raw_v6-28'd104857601 : raw_v6);
  wire [31:0] y0_6,y1_6;
  genefer_stream27_merged_final_gs_pair_inputreg_v1 #(.P(32'd104857601),.Q(32'd4190109697),
   .UPPER_SCALE(32'd56035902)) final_pair6 (
   .clk,.rst_n,.in_valid(accept),.u({5'b0,canonical_u6}),.v({5'b0,canonical_v6}),
   .normalized_lower_root({5'b0,packed_roots[0+:27]}),
   .out_valid(bf_valid[6]),.out_error(pair_error[6]),.y0(y0_6),.y1(y1_6));
  assign bf_data[168+:28]={1'b0,y0_6[26:0]};
  assign bf_data[392+:28]={1'b0,y1_6[26:0]};
  wire [27:0] raw_u7=row_data[196+:28],raw_v7=row_data[420+:28];
  wire [26:0] canonical_u7=27'(raw_u7>=28'd104857601 ? raw_u7-28'd104857601 : raw_u7);
  wire [26:0] canonical_v7=27'(raw_v7>=28'd104857601 ? raw_v7-28'd104857601 : raw_v7);
  wire [31:0] y0_7,y1_7;
  genefer_stream27_merged_final_gs_pair_inputreg_v1 #(.P(32'd104857601),.Q(32'd4190109697),
   .UPPER_SCALE(32'd56035902)) final_pair7 (
   .clk,.rst_n,.in_valid(accept),.u({5'b0,canonical_u7}),.v({5'b0,canonical_v7}),
   .normalized_lower_root({5'b0,packed_roots[0+:27]}),
   .out_valid(bf_valid[7]),.out_error(pair_error[7]),.y0(y0_7),.y1(y1_7));
  assign bf_data[196+:28]={1'b0,y0_7[26:0]};
  assign bf_data[420+:28]={1'b0,y1_7[26:0]};
  assign slot[16]=slot_pipe[6] && (&bf_valid) && !stop;
  assign start[16]=start_pipe[6];assign generation[16]=generation_pipe[6];
  assign data[16]=bf_data;
  always_ff @(posedge clk or negedge rst_n)begin
   if(!rst_n)begin slot_pipe<=0;start_pipe<=0;local_error<=0;remaining<=0;end
   else begin
    if(!stop && (cadence_bad || shuffle_pending || (|pair_error) || bf_valid!={PAIRS{slot_pipe[6]}}))local_error<=1;
    if(stop)begin slot_pipe<=0;start_pipe<=0;end
    else begin
     slot_pipe<={slot_pipe[5:0],accept};start_pipe<={start_pipe[5:0],accept && row_start};
     generation_pipe[0]<=row_generation;
     for(int k=1;k<7;k=k+1)generation_pipe[k]<=generation_pipe[k-1];
     if(accept)begin
      if(row_start)begin remaining<=COUNT_W'(FRAME_T-1);owner_generation<=row_generation;end
      else remaining<=remaining-COUNT_W'(1);
     end
    end
   end
  end
 end
 assign data_out[0+:28]=data[STAGES][0+:28];
 assign data_out[28+:28]=data[STAGES][224+:28];
 assign data_out[56+:28]=data[STAGES][112+:28];
 assign data_out[84+:28]=data[STAGES][336+:28];
 assign data_out[112+:28]=data[STAGES][56+:28];
 assign data_out[140+:28]=data[STAGES][280+:28];
 assign data_out[168+:28]=data[STAGES][168+:28];
 assign data_out[196+:28]=data[STAGES][392+:28];
 assign data_out[224+:28]=data[STAGES][28+:28];
 assign data_out[252+:28]=data[STAGES][252+:28];
 assign data_out[280+:28]=data[STAGES][140+:28];
 assign data_out[308+:28]=data[STAGES][364+:28];
 assign data_out[336+:28]=data[STAGES][84+:28];
 assign data_out[364+:28]=data[STAGES][308+:28];
 assign data_out[392+:28]=data[STAGES][196+:28];
 assign data_out[420+:28]=data[STAGES][420+:28];
endmodule
