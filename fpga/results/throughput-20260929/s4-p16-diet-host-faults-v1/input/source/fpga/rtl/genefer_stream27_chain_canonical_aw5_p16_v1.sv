module genefer_stream27_chain_canonical_aw5_p16_v1 #(parameter int AW=5,P=16,CONTEXTS=1) (
 input logic clk,rst_n,begin_setup,in_slot_valid,frame_start,context_enabled,double_in,
 input logic [7:0] generation_in,live_generation,input logic [31:0] base_in,
 input logic [15:0] epoch_in,correction_epoch,input logic correction_valid,
 input logic [7:0] correction_generation,input logic [P*32-1:0] data_in,c0_in,c1_in,
 input logic [31:0] square_count,double_mask,
 output logic config_valid,setup_done,out_error,fault_pending,frame_accept,correction_accept,
 output logic internal_frame_accept,internal_correction_accept,
 output logic active,warm_done,warm_cancelled,output logic [31:0] completed_frames,
 output logic coefficient_valid,coefficient_start,output logic signed [P*96-1:0] coefficient_data,
 output logic [AW-5:0] coefficient_row,output logic digit_valid,digit_start,digit_eligible,
 output logic [P*32-1:0] digit_data,output logic [AW-5:0] digit_row,
 output logic [15:0] digit_epoch,output logic [7:0] digit_generation,
 output logic boundary_valid,boundary_eligible,output logic [P*32-1:0] next_c0,next_c1,
 output logic [15:0] next_epoch,output logic [7:0] next_generation,
 input logic feed_mode,command_valid,command_double,
 input logic [31:0] command_index,input logic [7:0] command_generation,
 output logic command_accept,output logic [31:0] started_frames,digit_sequence,boundary_sequence,
 output logic [3:0] chain_error_code,
 output logic frame_done,output logic [15:0] done_epoch,
 input logic read_req,input logic [AW-1:0] read_address,
 output logic busy,done,cancelled,canonical_ready,read_valid,
 output logic [AW-1:0] read_address_out,output logic signed [95:0] read_data,
 output logic final_load_valid,output logic [31:0] final_load_sequence,
 output logic [63:0] canonical_cycles);
 localparam int ROW_W=AW-4;
 wire warm_error,warm_pending,canonical_busy,canonical_done,canonical_error,canonical_image_valid,canonical_read_valid;
 wire [7:0] canonical_error_code;logic controller_error,finalizing,metadata_ready;
 logic [31:0] final_sequence;logic [15:0] final_epoch;logic [7:0] chain_generation;logic [31:0] chain_base;
 logic [P*32-1:0] final_c0,final_c1;
 genefer_stream27_warm_chain_aw5_p16_v1 #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) recurrence (.out_error(warm_error),.fault_pending(warm_pending),.*);
 assign out_error=warm_error || canonical_error || controller_error;
 assign fault_pending=out_error || warm_pending || (warm_done && !warm_cancelled && !metadata_ready);
 wire publish_ok=!cancelled && context_enabled && chain_generation==live_generation;
 wire final_row=digit_valid && digit_eligible && digit_sequence==final_sequence && digit_epoch==final_epoch && digit_generation==chain_generation;
 assign final_load_valid=final_row && !out_error;
 assign final_load_sequence=digit_sequence;
 wire canonical_request=warm_done && !warm_cancelled && publish_ok && metadata_ready && !out_error;
 // warm_done is a drained arithmetic diagnostic, not host completion. Busy
 // bridges it through the actual once-per-chain materialization. No idle gap.
 assign busy=(active || finalizing || warm_done) && !canonical_done && !out_error;
 assign done=canonical_done && publish_ok && !out_error;
 assign canonical_ready=canonical_image_valid && !busy && publish_ok && !out_error;
 assign read_valid=canonical_read_valid && publish_ok && !out_error;
 genefer_stream27_canonical_image_pipe_v1 #(.AW(AW),.P(P),.ROW_W(ROW_W)) final_image (
  .clk,.rst_n,.load_valid(final_row && !out_error),.load_row(digit_row),.load_data(digit_data),
  .begin_canonical(canonical_request),.base(chain_base),.c0(final_c0),.c1(final_c1),
  .read_req(read_req && canonical_ready),.read_address,.busy(canonical_busy),.done(canonical_done),
  .error(canonical_error),.error_code(canonical_error_code),.image_valid(canonical_image_valid),
  .cycles(canonical_cycles),.read_valid(canonical_read_valid),.read_address_out,.read_data);
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin controller_error<=0;finalizing<=0;metadata_ready<=0;cancelled<=0;
   final_sequence<=0;final_epoch<=0;chain_generation<=0;chain_base<=0;final_c0<=0;final_c1<=0;end
  else begin
   if(busy && (!context_enabled || chain_generation!=live_generation))cancelled<=1;
   if(frame_accept)begin
    final_sequence<=square_count-32'd1;final_epoch<=epoch_in+16'(square_count-32'd1);chain_generation<=generation_in;chain_base<=base_in;
    metadata_ready<=0;cancelled<=0;
   end
   if(boundary_valid && boundary_sequence==final_sequence && next_epoch==final_epoch+16'd1 && next_generation==chain_generation)begin
    final_c0<=next_c0;final_c1<=next_c1;metadata_ready<=1;
   end
   if(warm_done)begin
    if(warm_cancelled || !publish_ok)cancelled<=1;
    else if(!metadata_ready)controller_error<=1;
    else finalizing<=1;
   end
   if(canonical_done)finalizing<=0;
  end
 end
 // synthesis translate_off
 initial if(AW!=5 || P!=16 || CONTEXTS!=1)$fatal(1,"S4_FINAL_IMAGE_GEOMETRY");
 always @(posedge clk)if(rst_n && done && (busy || !canonical_ready || out_error))$fatal(1,"S4_CANONICAL_DONE_PUBLICATION");
 // synthesis translate_on
endmodule
