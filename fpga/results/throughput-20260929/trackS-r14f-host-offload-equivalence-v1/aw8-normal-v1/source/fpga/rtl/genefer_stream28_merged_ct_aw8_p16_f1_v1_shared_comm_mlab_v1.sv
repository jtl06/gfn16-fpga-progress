// Connected P16-c CT: physical occupied rows are never filtered by eligibility.
module genefer_stream28_merged_ct_aw8_p16_f1_v1_shared_comm_mlab_v1 #(parameter int GEN_W=8) (
 input logic clk,rst_n,in_slot_valid,frame_start,quarantine,context_enabled,
 input logic [GEN_W-1:0] generation_in,live_generation,
 input logic [447:0] data_in,
 output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,
 output logic [GEN_W-1:0] generation_out,
 output logic [447:0] data_out);
 localparam int STAGES=8,FRAME_T=16,PAIRS=8;
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
  wire [26:0] packed_roots;
  merged_stream27_root_ct_aw8_p16_f1_s0_v1_bf_outreg_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[0+:28]),.v(row_data[28+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[28+:28]));
  assign pair_error[0]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[56+:28]),.v(row_data[84+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[56+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[112+:28]),.v(row_data[140+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[140+:28]));
  assign pair_error[2]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[168+:28]),.v(row_data[196+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[168+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[224+:28]),.v(row_data[252+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[252+:28]));
  assign pair_error[4]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[280+:28]),.v(row_data[308+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[280+:28]),.y1(bf_data[308+:28]));
  assign pair_error[5]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[336+:28]),.v(row_data[364+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[336+:28]),.y1(bf_data[364+:28]));
  assign pair_error[6]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[392+:28]),.v(row_data[420+:28]),.root_delayed(packed_roots[0+:27]),
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
  wire [53:0] packed_roots;
  merged_stream27_root_ct_aw8_p16_f1_s1_v1_bf_outreg_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[0+:28]),.v(row_data[56+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[56+:28]));
  assign pair_error[0]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[28+:28]),.v(row_data[84+:28]),.root_delayed(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[112+:28]),.v(row_data[168+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[140+:28]),.v(row_data[196+:28]),.root_delayed(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[140+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[224+:28]),.v(row_data[280+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[280+:28]));
  assign pair_error[4]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[252+:28]),.v(row_data[308+:28]),.root_delayed(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[252+:28]),.y1(bf_data[308+:28]));
  assign pair_error[5]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[336+:28]),.v(row_data[392+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[336+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[364+:28]),.v(row_data[420+:28]),.root_delayed(packed_roots[27+:27]),
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
  wire [107:0] packed_roots;
  merged_stream27_root_ct_aw8_p16_f1_s2_v1_bf_outreg_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[0+:28]),.v(row_data[112+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[112+:28]));
  assign pair_error[0]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[28+:28]),.v(row_data[140+:28]),.root_delayed(packed_roots[54+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[140+:28]));
  assign pair_error[1]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[56+:28]),.v(row_data[168+:28]),.root_delayed(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[56+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[84+:28]),.v(row_data[196+:28]),.root_delayed(packed_roots[81+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[84+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[224+:28]),.v(row_data[336+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[336+:28]));
  assign pair_error[4]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[252+:28]),.v(row_data[364+:28]),.root_delayed(packed_roots[54+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[252+:28]),.y1(bf_data[364+:28]));
  assign pair_error[5]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[280+:28]),.v(row_data[392+:28]),.root_delayed(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[280+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[308+:28]),.v(row_data[420+:28]),.root_delayed(packed_roots[81+:27]),
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
  wire [215:0] packed_roots;
  merged_stream27_root_ct_aw8_p16_f1_s3_v1_bf_outreg_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[0+:28]),.v(row_data[224+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[224+:28]));
  assign pair_error[0]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[28+:28]),.v(row_data[252+:28]),.root_delayed(packed_roots[108+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[252+:28]));
  assign pair_error[1]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[56+:28]),.v(row_data[280+:28]),.root_delayed(packed_roots[54+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[56+:28]),.y1(bf_data[280+:28]));
  assign pair_error[2]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[84+:28]),.v(row_data[308+:28]),.root_delayed(packed_roots[162+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[84+:28]),.y1(bf_data[308+:28]));
  assign pair_error[3]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[112+:28]),.v(row_data[336+:28]),.root_delayed(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[112+:28]),.y1(bf_data[336+:28]));
  assign pair_error[4]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[140+:28]),.v(row_data[364+:28]),.root_delayed(packed_roots[135+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[140+:28]),.y1(bf_data[364+:28]));
  assign pair_error[5]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[168+:28]),.v(row_data[392+:28]),.root_delayed(packed_roots[81+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[168+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[196+:28]),.v(row_data[420+:28]),.root_delayed(packed_roots[189+:27]),
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
  genefer_stream27_mdc_commutator_shared_packed_faultlocal_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(8),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[4]),.frame_start(start[4]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[4]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [215:0] packed_roots;
  merged_stream27_root_ct_aw8_p16_f1_s4_v1_bf_outreg_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[0+:28]),.v(row_data[28+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[28+:28]));
  assign pair_error[0]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[56+:28]),.v(row_data[84+:28]),.root_delayed(packed_roots[108+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[56+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[112+:28]),.v(row_data[140+:28]),.root_delayed(packed_roots[54+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[140+:28]));
  assign pair_error[2]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[168+:28]),.v(row_data[196+:28]),.root_delayed(packed_roots[162+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[168+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[224+:28]),.v(row_data[252+:28]),.root_delayed(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[252+:28]));
  assign pair_error[4]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[280+:28]),.v(row_data[308+:28]),.root_delayed(packed_roots[135+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[280+:28]),.y1(bf_data[308+:28]));
  assign pair_error[5]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[336+:28]),.v(row_data[364+:28]),.root_delayed(packed_roots[81+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[336+:28]),.y1(bf_data[364+:28]));
  assign pair_error[6]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[392+:28]),.v(row_data[420+:28]),.root_delayed(packed_roots[189+:27]),
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
  genefer_stream27_mdc_commutator_shared_packed_faultlocal_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(4),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[5]),.frame_start(start[5]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[5]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [215:0] packed_roots;
  merged_stream27_root_ct_aw8_p16_f1_s5_v1_bf_outreg_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[0+:28]),.v(row_data[56+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[56+:28]));
  assign pair_error[0]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[28+:28]),.v(row_data[84+:28]),.root_delayed(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[84+:28]));
  assign pair_error[1]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[112+:28]),.v(row_data[168+:28]),.root_delayed(packed_roots[108+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[112+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[140+:28]),.v(row_data[196+:28]),.root_delayed(packed_roots[135+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[140+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[224+:28]),.v(row_data[280+:28]),.root_delayed(packed_roots[54+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[280+:28]));
  assign pair_error[4]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[252+:28]),.v(row_data[308+:28]),.root_delayed(packed_roots[81+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[252+:28]),.y1(bf_data[308+:28]));
  assign pair_error[5]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[336+:28]),.v(row_data[392+:28]),.root_delayed(packed_roots[162+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[336+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[364+:28]),.v(row_data[420+:28]),.root_delayed(packed_roots[189+:27]),
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
  genefer_stream27_mdc_commutator_shared_packed_faultlocal_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(2),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[6]),.frame_start(start[6]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[6]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [215:0] packed_roots;
  merged_stream27_root_ct_aw8_p16_f1_s6_v1_bf_outreg_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[0+:28]),.v(row_data[112+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[112+:28]));
  assign pair_error[0]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[28+:28]),.v(row_data[140+:28]),.root_delayed(packed_roots[54+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[140+:28]));
  assign pair_error[1]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[56+:28]),.v(row_data[168+:28]),.root_delayed(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[56+:28]),.y1(bf_data[168+:28]));
  assign pair_error[2]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[84+:28]),.v(row_data[196+:28]),.root_delayed(packed_roots[81+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[84+:28]),.y1(bf_data[196+:28]));
  assign pair_error[3]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[224+:28]),.v(row_data[336+:28]),.root_delayed(packed_roots[108+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[224+:28]),.y1(bf_data[336+:28]));
  assign pair_error[4]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[252+:28]),.v(row_data[364+:28]),.root_delayed(packed_roots[162+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[252+:28]),.y1(bf_data[364+:28]));
  assign pair_error[5]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[280+:28]),.v(row_data[392+:28]),.root_delayed(packed_roots[135+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[280+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[308+:28]),.v(row_data[420+:28]),.root_delayed(packed_roots[189+:27]),
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
  genefer_stream27_mdc_commutator_shared_packed_faultlocal_v1 #(.PAIRS(8),.DATA_W(28),.PAYLOAD_W(1),
   .GEN_W(GEN_W),.DEPTH(1),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (
   .clk,.rst_n,.in_slot_valid(slot[7]),.frame_start(start[7]),.quarantine(stop),
   .upper_in(shared_upper_in),.lower_in(shared_lower_in),
   .upper_payload(8'b0),.lower_payload(8'b0),.context_in(1'b0),
   .generation_in(generation[7]),.context_enabled,.live_generations(live_generation),
   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),
   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),
   .upper_out(shared_upper_out),.lower_out(shared_lower_out),
   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));
  wire [215:0] packed_roots;
  merged_stream27_root_ct_aw8_p16_f1_s7_v1_bf_outreg_v1 roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf0 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[0+:28]),.v(row_data[224+:28]),.root_delayed(packed_roots[0+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[0]),.y0(bf_data[0+:28]),.y1(bf_data[224+:28]));
  assign pair_error[0]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf1 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[28+:28]),.v(row_data[252+:28]),.root_delayed(packed_roots[108+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[1]),.y0(bf_data[28+:28]),.y1(bf_data[252+:28]));
  assign pair_error[1]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf2 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[56+:28]),.v(row_data[280+:28]),.root_delayed(packed_roots[54+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[2]),.y0(bf_data[56+:28]),.y1(bf_data[280+:28]));
  assign pair_error[2]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf3 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[84+:28]),.v(row_data[308+:28]),.root_delayed(packed_roots[162+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[3]),.y0(bf_data[84+:28]),.y1(bf_data[308+:28]));
  assign pair_error[3]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf4 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[112+:28]),.v(row_data[336+:28]),.root_delayed(packed_roots[27+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[4]),.y0(bf_data[112+:28]),.y1(bf_data[336+:28]));
  assign pair_error[4]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf5 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[140+:28]),.v(row_data[364+:28]),.root_delayed(packed_roots[135+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[5]),.y0(bf_data[140+:28]),.y1(bf_data[364+:28]));
  assign pair_error[5]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf6 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[168+:28]),.v(row_data[392+:28]),.root_delayed(packed_roots[81+:27]),
   .in_tag(1'b0),.out_tag(),
   .out_valid(bf_valid[6]),.y0(bf_data[168+:28]),.y1(bf_data[392+:28]));
  assign pair_error[6]=1'b0;
  genefer_stream27_lazy28_rootregistered_butterfly_v1 #(.P(32'd69206017),.Q(32'd4225761281),.TAG_W(1)) bf7 (
   .clk,.rst_n,.in_valid(accept),.gs(1'b0),
   .u(row_data[196+:28]),.v(row_data[420+:28]),.root_delayed(packed_roots[189+:27]),
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
