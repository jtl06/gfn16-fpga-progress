// SOURCE-ONLY generated transform: genefer_stream27_dif_aw3_p8_f0; no RTL/clock qualification.
// Payload is constant zero. Physical slot/frame tags survive cancellation.
// Root files must all exist before this source can be staged for HDL.
module genefer_stream27_dif_aw3_p8_f0_shared_registered_v1 #(parameter int GEN_W=8) (
  input logic clk,rst_n,in_slot_valid,frame_start,quarantine,context_enabled,
  input logic [GEN_W-1:0] generation_in,live_generation,
  input logic [215:0] data_in,
  output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,
  output logic [GEN_W-1:0] generation_out,
  output logic [215:0] data_out);
  localparam int STAGES=3, FRAME_T=1;
  logic [STAGES:0] slot,start;
  logic [GEN_W-1:0] generation[0:STAGES];
  logic [215:0] data[0:STAGES];
  logic [STAGES-1:0] stage_error,stage_pending;
  wire stop=quarantine || (|stage_error);
  assign slot[0]=in_slot_valid; assign start[0]=frame_start;
  assign generation[0]=generation_in; assign data[0]=data_in;
  assign out_error=|stage_error; assign fault_pending=|stage_pending;
  assign out_slot_valid=slot[STAGES] && !stop;
  assign out_frame_start=start[STAGES] && out_slot_valid;
  assign generation_out=generation[STAGES];
  assign out_eligible=out_slot_valid && context_enabled && generation_out==live_generation;
// Recheck current generation and fault_pending at the external commit edge.
  if (1) begin : stage0
    logic row_slot,row_start;
    logic [GEN_W-1:0] row_generation;
    logic [215:0] row_data;
    logic local_fault,shuffle_fault,shuffle_pending;
    logic [5:0] slot_pipe,start_pipe;
    logic [GEN_W-1:0] generation_pipe[0:5];
    logic [3:0] bf_valid;
    logic [215:0] bf_data;
    localparam int COUNT_W=$clog2(FRAME_T+1);
    logic [COUNT_W-1:0] remaining;
    logic [GEN_W-1:0] owner_generation;
    wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
      (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
      (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
    wire accept=row_slot && !stop && !local_fault;
    assign stage_error[0]=local_fault || shuffle_fault;
    assign stage_pending[0]=local_fault || shuffle_pending ||
      (!stop && (cadence_bad || bf_valid!={4{slot_pipe[5]}}));
    assign row_slot=slot[0]; assign row_start=start[0];
    assign row_generation=generation[0]; assign row_data=data[0];
    assign shuffle_fault=1'b0; assign shuffle_pending=1'b0;
    wire [26:0] root0;
    genefer_stream27_root_rom_prefetch #(.PERIOD(1),
      .FIRST_ROOT(27'd100663256),.HEX_FILE("")) root_source0 (
      .clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(root0));
    wire [26:0] root1;
    genefer_stream27_root_rom_prefetch #(.PERIOD(1),
      .FIRST_ROOT(27'd81453865),.HEX_FILE("")) root_source1 (
      .clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(root1));
    wire [26:0] root2;
    genefer_stream27_root_rom_prefetch #(.PERIOD(1),
      .FIRST_ROOT(27'd63333991),.HEX_FILE("")) root_source2 (
      .clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(root2));
    wire [26:0] root3;
    genefer_stream27_root_rom_prefetch #(.PERIOD(1),
      .FIRST_ROOT(27'd54638355),.HEX_FILE("")) root_source3 (
      .clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(root3));
    wire [31:0] y0_0,y1_0;
    genefer_ntt_difdit_butterfly27 #(.P(32'd104857601),.Q(32'd4190109697)) bf0 (
      .clk,.rst_n,.in_valid(accept),.dif(1'b1),
      .u({5'b0,row_data[0+:27]}),.v({5'b0,row_data[27+:27]}),
      .w({5'b0,root0}),.out_valid(bf_valid[0]),.y0(y0_0),.y1(y1_0));
    assign bf_data[0+:27]=y0_0[26:0];
    assign bf_data[27+:27]=y1_0[26:0];
    wire [31:0] y0_1,y1_1;
    genefer_ntt_difdit_butterfly27 #(.P(32'd104857601),.Q(32'd4190109697)) bf1 (
      .clk,.rst_n,.in_valid(accept),.dif(1'b1),
      .u({5'b0,row_data[54+:27]}),.v({5'b0,row_data[81+:27]}),
      .w({5'b0,root2}),.out_valid(bf_valid[1]),.y0(y0_1),.y1(y1_1));
    assign bf_data[54+:27]=y0_1[26:0];
    assign bf_data[81+:27]=y1_1[26:0];
    wire [31:0] y0_2,y1_2;
    genefer_ntt_difdit_butterfly27 #(.P(32'd104857601),.Q(32'd4190109697)) bf2 (
      .clk,.rst_n,.in_valid(accept),.dif(1'b1),
      .u({5'b0,row_data[108+:27]}),.v({5'b0,row_data[135+:27]}),
      .w({5'b0,root1}),.out_valid(bf_valid[2]),.y0(y0_2),.y1(y1_2));
    assign bf_data[108+:27]=y0_2[26:0];
    assign bf_data[135+:27]=y1_2[26:0];
    wire [31:0] y0_3,y1_3;
    genefer_ntt_difdit_butterfly27 #(.P(32'd104857601),.Q(32'd4190109697)) bf3 (
      .clk,.rst_n,.in_valid(accept),.dif(1'b1),
      .u({5'b0,row_data[162+:27]}),.v({5'b0,row_data[189+:27]}),
      .w({5'b0,root3}),.out_valid(bf_valid[3]),.y0(y0_3),.y1(y1_3));
    assign bf_data[162+:27]=y0_3[26:0];
    assign bf_data[189+:27]=y1_3[26:0];
    assign slot[1]=slot_pipe[5] && (&bf_valid) && !stop;
    assign start[1]=start_pipe[5];
    assign generation[1]=generation_pipe[5]; assign data[1]=bf_data;
    always_ff @(posedge clk or negedge rst_n) begin
      if(!rst_n) begin slot_pipe<='0; start_pipe<='0; local_fault<=0; remaining<='0; end
      else begin
        if(!stop && (cadence_bad || shuffle_pending ||
          (bf_valid!={4{slot_pipe[5]}}))) local_fault<=1;
        if(stop) begin slot_pipe<='0; start_pipe<='0; end
        else begin
          slot_pipe<={slot_pipe[4:0],accept}; start_pipe<={start_pipe[4:0],accept && row_start};
          generation_pipe[0]<=row_generation;
          for(int k=1;k<6;k=k+1) generation_pipe[k]<=generation_pipe[k-1];
          if(accept) begin
            if(row_start) begin remaining<=COUNT_W'(FRAME_T-1); owner_generation<=row_generation; end
            else remaining<=remaining-COUNT_W'(1);
          end
        end
      end
    end
  end
  if (1) begin : stage1
    logic row_slot,row_start;
    logic [GEN_W-1:0] row_generation;
    logic [215:0] row_data;
    logic local_fault,shuffle_fault,shuffle_pending;
    logic [5:0] slot_pipe,start_pipe;
    logic [GEN_W-1:0] generation_pipe[0:5];
    logic [3:0] bf_valid;
    logic [215:0] bf_data;
    localparam int COUNT_W=$clog2(FRAME_T+1);
    logic [COUNT_W-1:0] remaining;
    logic [GEN_W-1:0] owner_generation;
    wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
      (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
      (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
    wire accept=row_slot && !stop && !local_fault;
    assign stage_error[1]=local_fault || shuffle_fault;
    assign stage_pending[1]=local_fault || shuffle_pending ||
      (!stop && (cadence_bad || bf_valid!={4{slot_pipe[5]}}));
    assign row_slot=slot[1]; assign row_start=start[1];
    assign row_generation=generation[1]; assign row_data=data[1];
    assign shuffle_fault=1'b0; assign shuffle_pending=1'b0;
    wire [26:0] root0;
    genefer_stream27_root_rom_prefetch #(.PERIOD(1),
      .FIRST_ROOT(27'd100663256),.HEX_FILE("")) root_source0 (
      .clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(root0));
    wire [26:0] root1;
    genefer_stream27_root_rom_prefetch #(.PERIOD(1),
      .FIRST_ROOT(27'd63333991),.HEX_FILE("")) root_source1 (
      .clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(root1));
    wire [31:0] y0_0,y1_0;
    genefer_ntt_difdit_butterfly27 #(.P(32'd104857601),.Q(32'd4190109697)) bf0 (
      .clk,.rst_n,.in_valid(accept),.dif(1'b1),
      .u({5'b0,row_data[0+:27]}),.v({5'b0,row_data[54+:27]}),
      .w({5'b0,root0}),.out_valid(bf_valid[0]),.y0(y0_0),.y1(y1_0));
    assign bf_data[0+:27]=y0_0[26:0];
    assign bf_data[54+:27]=y1_0[26:0];
    wire [31:0] y0_1,y1_1;
    genefer_ntt_difdit_butterfly27 #(.P(32'd104857601),.Q(32'd4190109697)) bf1 (
      .clk,.rst_n,.in_valid(accept),.dif(1'b1),
      .u({5'b0,row_data[27+:27]}),.v({5'b0,row_data[81+:27]}),
      .w({5'b0,root0}),.out_valid(bf_valid[1]),.y0(y0_1),.y1(y1_1));
    assign bf_data[27+:27]=y0_1[26:0];
    assign bf_data[81+:27]=y1_1[26:0];
    wire [31:0] y0_2,y1_2;
    genefer_ntt_difdit_butterfly27 #(.P(32'd104857601),.Q(32'd4190109697)) bf2 (
      .clk,.rst_n,.in_valid(accept),.dif(1'b1),
      .u({5'b0,row_data[108+:27]}),.v({5'b0,row_data[162+:27]}),
      .w({5'b0,root1}),.out_valid(bf_valid[2]),.y0(y0_2),.y1(y1_2));
    assign bf_data[108+:27]=y0_2[26:0];
    assign bf_data[162+:27]=y1_2[26:0];
    wire [31:0] y0_3,y1_3;
    genefer_ntt_difdit_butterfly27 #(.P(32'd104857601),.Q(32'd4190109697)) bf3 (
      .clk,.rst_n,.in_valid(accept),.dif(1'b1),
      .u({5'b0,row_data[135+:27]}),.v({5'b0,row_data[189+:27]}),
      .w({5'b0,root1}),.out_valid(bf_valid[3]),.y0(y0_3),.y1(y1_3));
    assign bf_data[135+:27]=y0_3[26:0];
    assign bf_data[189+:27]=y1_3[26:0];
    assign slot[2]=slot_pipe[5] && (&bf_valid) && !stop;
    assign start[2]=start_pipe[5];
    assign generation[2]=generation_pipe[5]; assign data[2]=bf_data;
    always_ff @(posedge clk or negedge rst_n) begin
      if(!rst_n) begin slot_pipe<='0; start_pipe<='0; local_fault<=0; remaining<='0; end
      else begin
        if(!stop && (cadence_bad || shuffle_pending ||
          (bf_valid!={4{slot_pipe[5]}}))) local_fault<=1;
        if(stop) begin slot_pipe<='0; start_pipe<='0; end
        else begin
          slot_pipe<={slot_pipe[4:0],accept}; start_pipe<={start_pipe[4:0],accept && row_start};
          generation_pipe[0]<=row_generation;
          for(int k=1;k<6;k=k+1) generation_pipe[k]<=generation_pipe[k-1];
          if(accept) begin
            if(row_start) begin remaining<=COUNT_W'(FRAME_T-1); owner_generation<=row_generation; end
            else remaining<=remaining-COUNT_W'(1);
          end
        end
      end
    end
  end
  if (1) begin : stage2
    logic row_slot,row_start;
    logic [GEN_W-1:0] row_generation;
    logic [215:0] row_data;
    logic local_fault,shuffle_fault,shuffle_pending;
    logic [5:0] slot_pipe,start_pipe;
    logic [GEN_W-1:0] generation_pipe[0:5];
    logic [3:0] bf_valid;
    logic [215:0] bf_data;
    localparam int COUNT_W=$clog2(FRAME_T+1);
    logic [COUNT_W-1:0] remaining;
    logic [GEN_W-1:0] owner_generation;
    wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||
      (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||
      (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);
    wire accept=row_slot && !stop && !local_fault;
    assign stage_error[2]=local_fault || shuffle_fault;
    assign stage_pending[2]=local_fault || shuffle_pending ||
      (!stop && (cadence_bad || bf_valid!={4{slot_pipe[5]}}));
    assign row_slot=slot[2]; assign row_start=start[2];
    assign row_generation=generation[2]; assign row_data=data[2];
    assign shuffle_fault=1'b0; assign shuffle_pending=1'b0;
    wire [26:0] root0;
    genefer_stream27_root_rom_prefetch #(.PERIOD(1),
      .FIRST_ROOT(27'd100663256),.HEX_FILE("")) root_source0 (
      .clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(root0));
    wire [31:0] y0_0,y1_0;
    genefer_ntt_difdit_butterfly27 #(.P(32'd104857601),.Q(32'd4190109697)) bf0 (
      .clk,.rst_n,.in_valid(accept),.dif(1'b1),
      .u({5'b0,row_data[0+:27]}),.v({5'b0,row_data[108+:27]}),
      .w({5'b0,root0}),.out_valid(bf_valid[0]),.y0(y0_0),.y1(y1_0));
    assign bf_data[0+:27]=y0_0[26:0];
    assign bf_data[108+:27]=y1_0[26:0];
    wire [31:0] y0_1,y1_1;
    genefer_ntt_difdit_butterfly27 #(.P(32'd104857601),.Q(32'd4190109697)) bf1 (
      .clk,.rst_n,.in_valid(accept),.dif(1'b1),
      .u({5'b0,row_data[27+:27]}),.v({5'b0,row_data[135+:27]}),
      .w({5'b0,root0}),.out_valid(bf_valid[1]),.y0(y0_1),.y1(y1_1));
    assign bf_data[27+:27]=y0_1[26:0];
    assign bf_data[135+:27]=y1_1[26:0];
    wire [31:0] y0_2,y1_2;
    genefer_ntt_difdit_butterfly27 #(.P(32'd104857601),.Q(32'd4190109697)) bf2 (
      .clk,.rst_n,.in_valid(accept),.dif(1'b1),
      .u({5'b0,row_data[54+:27]}),.v({5'b0,row_data[162+:27]}),
      .w({5'b0,root0}),.out_valid(bf_valid[2]),.y0(y0_2),.y1(y1_2));
    assign bf_data[54+:27]=y0_2[26:0];
    assign bf_data[162+:27]=y1_2[26:0];
    wire [31:0] y0_3,y1_3;
    genefer_ntt_difdit_butterfly27 #(.P(32'd104857601),.Q(32'd4190109697)) bf3 (
      .clk,.rst_n,.in_valid(accept),.dif(1'b1),
      .u({5'b0,row_data[81+:27]}),.v({5'b0,row_data[189+:27]}),
      .w({5'b0,root0}),.out_valid(bf_valid[3]),.y0(y0_3),.y1(y1_3));
    assign bf_data[81+:27]=y0_3[26:0];
    assign bf_data[189+:27]=y1_3[26:0];
    assign slot[3]=slot_pipe[5] && (&bf_valid) && !stop;
    assign start[3]=start_pipe[5];
    assign generation[3]=generation_pipe[5]; assign data[3]=bf_data;
    always_ff @(posedge clk or negedge rst_n) begin
      if(!rst_n) begin slot_pipe<='0; start_pipe<='0; local_fault<=0; remaining<='0; end
      else begin
        if(!stop && (cadence_bad || shuffle_pending ||
          (bf_valid!={4{slot_pipe[5]}}))) local_fault<=1;
        if(stop) begin slot_pipe<='0; start_pipe<='0; end
        else begin
          slot_pipe<={slot_pipe[4:0],accept}; start_pipe<={start_pipe[4:0],accept && row_start};
          generation_pipe[0]<=row_generation;
          for(int k=1;k<6;k=k+1) generation_pipe[k]<=generation_pipe[k-1];
          if(accept) begin
            if(row_start) begin remaining<=COUNT_W'(FRAME_T-1); owner_generation<=row_generation; end
            else remaining<=remaining-COUNT_W'(1);
          end
        end
      end
    end
  end
  assign data_out[0+:27]=data[STAGES][0+:27];
  assign data_out[27+:27]=data[STAGES][108+:27];
  assign data_out[54+:27]=data[STAGES][54+:27];
  assign data_out[81+:27]=data[STAGES][162+:27];
  assign data_out[108+:27]=data[STAGES][27+:27];
  assign data_out[135+:27]=data[STAGES][135+:27];
  assign data_out[162+:27]=data[STAGES][81+:27];
  assign data_out[189+:27]=data[STAGES][189+:27];
endmodule
