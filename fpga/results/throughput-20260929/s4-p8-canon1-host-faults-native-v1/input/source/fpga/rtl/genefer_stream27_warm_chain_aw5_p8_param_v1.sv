module genefer_stream27_warm_chain_aw5_p8_param_v1 #(parameter int AW=5,P=8,CONTEXTS=1) (
 input logic clk,rst_n,begin_setup,in_slot_valid,frame_start,context_enabled,double_in,
 input logic [7:0] generation_in,live_generation,input logic [31:0] base_in,
 input logic [15:0] epoch_in,correction_epoch,input logic correction_valid,
 input logic [7:0] correction_generation,input logic [P*32-1:0] data_in,c0_in,c1_in,
 input logic [31:0] square_count,double_mask,
 output logic config_valid,setup_done,out_error,fault_pending,frame_accept,correction_accept,
 output logic internal_frame_accept,internal_correction_accept,
 output logic active,warm_done,warm_cancelled,output logic [31:0] completed_frames,
 output logic coefficient_valid,coefficient_start,output logic signed [P*96-1:0] coefficient_data,
 output logic [AW-$clog2(P)-1:0] coefficient_row,output logic digit_valid,digit_start,digit_eligible,
 output logic [P*32-1:0] digit_data,output logic [AW-$clog2(P)-1:0] digit_row,
 output logic [15:0] digit_epoch,output logic [7:0] digit_generation,
 output logic boundary_valid,boundary_eligible,output logic [P*32-1:0] next_c0,next_c1,
 output logic [15:0] next_epoch,output logic [7:0] next_generation,
 input logic feed_mode,command_valid,command_double,
 input logic [31:0] command_index,input logic [7:0] command_generation,
 output logic command_accept,output logic [31:0] started_frames,digit_sequence,boundary_sequence,
 output logic [3:0] chain_error_code,
 output logic frame_done,output logic [15:0] done_epoch);
 localparam int ROW_W=AW-$clog2(P),ROWS=1<<ROW_W;
 logic local_error,initial_correction_seen,carry_feedback_enabled,cancel_seen;
 logic [ROW_W:0] cold_remaining;
 logic [31:0] remaining,launched,latched_mask,latched_count,result_sequence;
 logic latched_feed_mode,current_feedback_double;
 logic [7:0] chain_generation;logic [31:0] chain_base;
 wire cold_slot=in_slot_valid && (!active || cold_remaining!=0) && !local_error;
 wire cold_correction=correction_valid && (!initial_correction_seen || !active) && !local_error;
 // Intrinsic physical carry rows are preserved on cancellation. Eligibility
 // remains live-qualified in the arithmetic child; a cancelled chain drains
 // without a canonical publication, never reuses its tags early.
 wire need_feedback=digit_start ? remaining!=0 : carry_feedback_enabled;
 wire feedback_issue=digit_valid && need_feedback && !local_error;
 wire auto_correction=boundary_valid && carry_feedback_enabled && !local_error;
 wire feedback_slot,feedback_start;wire [P*32-1:0] feedback_data,permuted_digit;
 wire [23:0] feedback_owner;
 // Four explicit accepted-edge pipeline rows: carry output k -> field accept k+5.
 logic [3:0] fifo_valid,fifo_start;logic [P*32-1:0] fifo_data[0:3];
 logic [23:0] fifo_owner[0:3];
 assign feedback_slot=fifo_valid[3] && !local_error;
 assign feedback_start=fifo_start[3];assign feedback_data=fifo_data[3];assign feedback_owner=fifo_owner[3];
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin fifo_valid<=0;fifo_start<=0;end
  else if(local_error)begin fifo_valid<=0;fifo_start<=0;end
  else begin
   fifo_valid<={fifo_valid[2:0],feedback_issue};fifo_start<={fifo_start[2:0],digit_start};
   if(feedback_issue)begin fifo_data[0]<=permuted_digit;fifo_owner[0]<={digit_epoch+16'd1,digit_generation};end
   for(int d=1;d<4;d=d+1)if(fifo_valid[d-1])begin fifo_data[d]<=fifo_data[d-1];fifo_owner[d]<=fifo_owner[d-1];end
  end
 end

 for(genvar lane=0;lane<P;lane=lane+1)begin: input_route
  localparam int NATURAL=((lane&1)<<2)|((lane&2))|((lane&4)>>2);
  assign permuted_digit[32*lane+:32]=digit_data[32*NATURAL+:32];
 end
 wire child_error,child_pending,child_frame_accept,child_correction_accept;
 wire arithmetic_coefficient_valid,arithmetic_coefficient_start,arithmetic_digit_valid,arithmetic_digit_start;
 wire arithmetic_digit_eligible,arithmetic_boundary_valid,arithmetic_boundary_eligible,arithmetic_frame_done;
 wire command_needed=latched_feed_mode && feedback_slot && feedback_start && !local_error;
 // Intrinsic head eligibility, not generic fault_pending gating. An empty or
 // wrong head never supplies an old/zero bit to an accepted first warm row.
 wire command_bad=command_needed && (!command_valid || command_index!=launched || command_generation!=chain_generation);
 wire child_slot=(feedback_slot || cold_slot) && !command_bad;
 wire child_start=(feedback_slot ? feedback_start : frame_start) && !command_bad;
 wire child_correction=auto_correction || cold_correction;
 assign out_error=local_error || child_error;
 assign coefficient_valid=arithmetic_coefficient_valid && !local_error;
 assign coefficient_start=arithmetic_coefficient_start && coefficient_valid;
 assign digit_valid=arithmetic_digit_valid && !local_error;assign digit_start=arithmetic_digit_start && digit_valid;
 assign digit_eligible=arithmetic_digit_eligible && !local_error;
 assign boundary_valid=arithmetic_boundary_valid && !local_error;assign boundary_eligible=arithmetic_boundary_eligible && !local_error;
 assign frame_done=arithmetic_frame_done && !local_error;
 assign frame_accept=cold_slot && frame_start && child_frame_accept;
 assign correction_accept=cold_correction && child_correction_accept;
 assign internal_frame_accept=feedback_slot && feedback_start && child_frame_accept;
 assign internal_correction_accept=auto_correction && child_correction_accept;
 wire count_bad=cold_slot && frame_start && (square_count==0 || (!feed_mode && square_count>32'd32));
 wire collision=(cold_slot && feedback_slot) || (cold_correction && auto_correction);
 assign fault_pending=out_error || child_pending || count_bad || collision || command_bad;
 assign command_accept=internal_frame_accept && latched_feed_mode && !command_bad;
 assign started_frames=launched;
 // Physical carry blocks never overlap: previous done precedes next first
 // digit. This producer's completed counter is therefore its full ordinal,
 // captured intrinsically on first digit and held through the boundary pair.
 assign digit_sequence=digit_start ? completed_frames : result_sequence;
 assign boundary_sequence=result_sequence;
 genefer_stream27_threefield_carry_aw5_p8_param_v1_signed #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) arithmetic (
  .clk,.rst_n,.begin_setup(begin_setup && !active),.in_slot_valid(child_slot && !local_error),
  .frame_start(child_start),.context_enabled,.double_in(feedback_slot ? (feedback_start ? (latched_feed_mode ? command_double : latched_mask[launched[4:0]]) : current_feedback_double) : double_in),
  .generation_in(feedback_slot ? feedback_owner[7:0] : generation_in),.live_generation,
  .base_in(feedback_slot ? chain_base : base_in),.epoch_in(feedback_slot ? feedback_owner[23:8] : epoch_in),
  .correction_epoch(auto_correction ? next_epoch : correction_epoch),.correction_valid(child_correction && !local_error),
  .correction_generation(auto_correction ? next_generation : correction_generation),
  .data_in(feedback_slot ? feedback_data : data_in),.c0_in(auto_correction ? next_c0 : c0_in),
  .c1_in(auto_correction ? next_c1 : c1_in),.config_valid,.setup_done,
  .out_error(child_error),.fault_pending(child_pending),.frame_accept(child_frame_accept),.correction_accept(child_correction_accept),
  .coefficient_valid(arithmetic_coefficient_valid),.coefficient_start(arithmetic_coefficient_start),.coefficient_data,.coefficient_row,
  .digit_valid(arithmetic_digit_valid),.digit_start(arithmetic_digit_start),.digit_eligible(arithmetic_digit_eligible),.digit_data,.digit_row,.digit_epoch,.digit_generation,
  .boundary_valid(arithmetic_boundary_valid),.boundary_eligible(arithmetic_boundary_eligible),.next_c0,.next_c1,.next_epoch,.next_generation,
  .frame_done(arithmetic_frame_done),.done_epoch);
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   local_error<=0;active<=0;warm_done<=0;warm_cancelled<=0;completed_frames<=0;
   remaining<=0;launched<=0;latched_count<=0;latched_mask<=0;cold_remaining<=0;
   result_sequence<=0;latched_feed_mode<=0;current_feedback_double<=0;chain_error_code<=0;
   initial_correction_seen<=0;carry_feedback_enabled<=0;cancel_seen<=0;chain_generation<=0;chain_base<=0;
  end else begin
   warm_done<=0;
   if(count_bad || collision || child_error || command_bad)local_error<=1;
   if(chain_error_code==0)begin
    if(command_bad)chain_error_code<=!command_valid ? 4'd1 : (command_generation!=chain_generation ? 4'd2 : 4'd3);
    else if(count_bad)chain_error_code<=4'd4;
    else if(collision)chain_error_code<=4'd5;
    else if(child_error)chain_error_code<=4'd6;
   end
   if(digit_valid && digit_start)result_sequence<=completed_frames;
   if(active && (!context_enabled || chain_generation!=live_generation))cancel_seen<=1;
   if(frame_accept)begin
    active<=1;remaining<=square_count-32'd1;launched<=1;latched_count<=square_count;latched_mask<=double_mask;latched_feed_mode<=feed_mode;result_sequence<=0;
    cold_remaining<=(ROW_W+1)'(ROWS-1);chain_generation<=generation_in;chain_base<=base_in;
    completed_frames<=0;warm_cancelled<=0;cancel_seen<=0;initial_correction_seen<=0;
   end else if(cold_slot && cold_remaining!=0)cold_remaining<=cold_remaining-(ROW_W+1)'(1);
   if(correction_accept)initial_correction_seen<=1;
   if(digit_valid && digit_start)carry_feedback_enabled<=remaining!=0;
   if(internal_frame_accept)begin remaining<=remaining-32'd1;launched<=launched+32'd1;current_feedback_double<=latched_feed_mode ? command_double : latched_mask[launched[4:0]];end
   if(frame_done && active)begin
    completed_frames<=completed_frames+32'd1;
    if(completed_frames+32'd1==latched_count)begin
     active<=0;warm_done<=1;warm_cancelled<=cancel_seen || !context_enabled || chain_generation!=live_generation;
    end
   end
   if(local_error || child_error)begin active<=0;warm_done<=0;warm_cancelled<=1;end
  end
 end
 // synthesis translate_off
 initial if(AW!=5 || P!=8 || CONTEXTS!=1)$fatal(1,"S4_FINITE_FEEDBACK_GEOMETRY");
 // synthesis translate_on
endmodule
