// Canonical 27x27 pointwise square only, accepted k -> output k+3.
module genefer_stream27_square_p8_f2_v1 (
 input logic clk,rst_n,in_slot_valid,frame_start,quarantine,
 input logic [7:0] generation_in,input logic [215:0] data_in,
 output logic out_slot_valid,out_frame_start,out_error,fault_pending,
 output logic [7:0] generation_out,output logic [215:0] data_out);
 logic [7:0] lane_valid;logic [3:0] slot_pipe,start_pipe;
 logic [7:0] generation_pipe[0:3];
 wire mismatch=lane_valid!={8{slot_pipe[3]}};
 assign fault_pending=out_error || (!quarantine && mismatch);
 assign out_slot_valid=slot_pipe[3] && (&lane_valid) && !quarantine && !out_error;
 assign out_frame_start=start_pipe[3] && out_slot_valid;assign generation_out=generation_pipe[3];
 for(genvar lane=0;lane<8;lane=lane+1)begin: square_lane
  wire [31:0] result;
  genefer_montgomery_mul27_sparse_pipe #(.P(32'd67239937),.Q(32'd4227727361)) multiplier (
   .clk,.rst_n,.in_valid(in_slot_valid && !quarantine),
   .lhs({5'b0,data_in[lane*27+:27]}),.rhs({5'b0,data_in[lane*27+:27]}),
   .out_valid(lane_valid[lane]),.result(result));
  assign data_out[lane*27+:27]=result[26:0];
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin slot_pipe<=0;start_pipe<=0;out_error<=0;end
  else begin
   if(!quarantine && mismatch)out_error<=1;
   if(quarantine || out_error)begin slot_pipe<=0;start_pipe<=0;end
   else begin
    slot_pipe<={slot_pipe[2:0],in_slot_valid};start_pipe<={start_pipe[2:0],in_slot_valid && frame_start};
    generation_pipe[0]<=generation_in;
    for(int k=1;k<4;k=k+1)generation_pipe[k]<=generation_pipe[k-1];
   end
  end
 end
endmodule
