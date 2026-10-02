// Real S4-b arithmetic intermediate. Canonical host/readback gate is separate.
module genefer_stream27_threefield_carry_aw5_p8_param_v1_signed #(parameter int AW=5,P=8,CONTEXTS=1) (
 input logic clk,rst_n,begin_setup,in_slot_valid,frame_start,context_enabled,double_in,
 input logic [7:0] generation_in,live_generation,
 input logic [31:0] base_in,
 input logic [15:0] epoch_in,correction_epoch,
 input logic correction_valid,input logic [7:0] correction_generation,
 input logic [P*32-1:0] data_in,c0_in,c1_in,
 output logic config_valid,setup_done,out_error,fault_pending,frame_accept,correction_accept,
 output logic coefficient_valid,coefficient_start,
 output logic signed [P*96-1:0] coefficient_data,
 output logic [AW-$clog2(P)-1:0] coefficient_row,
 output logic digit_valid,digit_start,digit_eligible,
 output logic [P*32-1:0] digit_data,
 output logic [AW-$clog2(P)-1:0] digit_row,
 output logic [15:0] digit_epoch,output logic [7:0] digit_generation,
 output logic boundary_valid,boundary_eligible,
 output logic [P*32-1:0] next_c0,next_c1,
 output logic [15:0] next_epoch,output logic [7:0] next_generation,
 output logic frame_done,output logic [15:0] done_epoch);
 localparam int ROW_W=AW-$clog2(P),ROWS=1<<ROW_W,TAG_W=24+ROW_W;
 function automatic integer reverse_lane(input integer value);
  integer result;
  begin result=0;for(integer bit_index=0;bit_index<$clog2(P);bit_index=bit_index+1)begin
   result=(result<<1)|(value&1);value=value>>1;
  end reverse_lane=result;end
 endfunction
 wire [2:0] field_valid,field_start,field_eligible,field_error,field_pending;
 wire [2:0] field_frame_accept,field_correction_accept;
 wire [P*27-1:0] field_data[0:2];wire [ROW_W-1:0] field_row[0:2];
 wire [15:0] field_epoch[0:2];wire [7:0] field_generation[0:2];wire [1:0] field_owners[0:2];
 logic [15:0] bank_epoch[0:1];logic [7:0] bank_generation[0:1];logic bank_double[0:1];
 logic [31:0] bank_base[0:1];
 wire setup_error,setup_busy;wire [31:0] qualified_base,qualified_generation;
 wire [95:0] reciprocal;wire [76:0] coefficient_limit;
 genefer_stream27_blockcarry_setup_param_v1 #(.AW(AW),.P(P)) shared_setup (
  .clk,.rst_n,.begin_setup,.cancel(out_error),.base(base_in),.generation({24'd0,generation_in}),
  .busy(setup_busy),.done(setup_done),.error(setup_error),.config_valid,
  .accepted_base(qualified_base),.out_generation(qualified_generation),.coefficient_limit,.reciprocal);
 genefer_stream27_shared_warm_aw5_p8_f0_v2_signed_host_v3_valid_start_v4 #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) field0 (
  .clk,.rst_n,.in_slot_valid(in_slot_valid && !out_error),.frame_start,
  .context_enabled(context_enabled && !out_error),.generation_in,.live_generation,.base_in,
  .epoch_in,.correction_epoch,.correction_valid(correction_valid && !out_error),.correction_generation,
  .data_in,.c0_in,.c1_in,.out_slot_valid(field_valid[0]),.out_frame_start(field_start[0]),
  .out_eligible(field_eligible[0]),.out_error(field_error[0]),.fault_pending(field_pending[0]),
  .generation_out(field_generation[0]),.data_out(field_data[0]),.out_epoch(field_epoch[0]),
  .commit_valid(),.commit_frame_start(),.commit_generation(),.commit_epoch(),.commit_data(),
  .owner_count(field_owners[0]),.frame_accept(field_frame_accept[0]),
  .correction_accept(field_correction_accept[0]),.output_row(field_row[0]),.cycle_count(),.frame_count());
 genefer_stream27_shared_warm_aw5_p8_f1_v2_signed_host_v3_valid_start_v4 #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) field1 (
  .clk,.rst_n,.in_slot_valid(in_slot_valid && !out_error),.frame_start,
  .context_enabled(context_enabled && !out_error),.generation_in,.live_generation,.base_in,
  .epoch_in,.correction_epoch,.correction_valid(correction_valid && !out_error),.correction_generation,
  .data_in,.c0_in,.c1_in,.out_slot_valid(field_valid[1]),.out_frame_start(field_start[1]),
  .out_eligible(field_eligible[1]),.out_error(field_error[1]),.fault_pending(field_pending[1]),
  .generation_out(field_generation[1]),.data_out(field_data[1]),.out_epoch(field_epoch[1]),
  .commit_valid(),.commit_frame_start(),.commit_generation(),.commit_epoch(),.commit_data(),
  .owner_count(field_owners[1]),.frame_accept(field_frame_accept[1]),
  .correction_accept(field_correction_accept[1]),.output_row(field_row[1]),.cycle_count(),.frame_count());
 genefer_stream27_shared_warm_aw5_p8_f2_v2_signed_host_v3_valid_start_v4 #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) field2 (
  .clk,.rst_n,.in_slot_valid(in_slot_valid && !out_error),.frame_start,
  .context_enabled(context_enabled && !out_error),.generation_in,.live_generation,.base_in,
  .epoch_in,.correction_epoch,.correction_valid(correction_valid && !out_error),.correction_generation,
  .data_in,.c0_in,.c1_in,.out_slot_valid(field_valid[2]),.out_frame_start(field_start[2]),
  .out_eligible(field_eligible[2]),.out_error(field_error[2]),.fault_pending(field_pending[2]),
  .generation_out(field_generation[2]),.data_out(field_data[2]),.out_epoch(field_epoch[2]),
  .commit_valid(),.commit_frame_start(),.commit_generation(),.commit_epoch(),.commit_data(),
  .owner_count(field_owners[2]),.frame_accept(field_frame_accept[2]),
  .correction_accept(field_correction_accept[2]),.output_row(field_row[2]),.cycle_count(),.frame_count());
 assign frame_accept=&field_frame_accept;assign correction_accept=&field_correction_accept;
 wire joined=&field_valid;
 wire join_start=&field_start;
 wire bank=field_epoch[0][0];
 wire begin_carry=joined && join_start && !out_error;
 wire [P-1:0] crt_valid,crt_ready,lane_busy,lane_done,lane_error,lane_digit_valid,lane_boundary_valid;
 wire [3:0] lane_error_code[0:P-1];wire signed [95:0] crt_coefficient[0:P-1];
 wire [31:0] lane_digit[0:P-1],lane_low[0:P-1];wire signed [31:0] lane_high[0:P-1];
 wire [AW-1:0] lane_offset[0:P-1];
 logic [TAG_W-1:0] crt_tag[0:15];logic crt_double[0:15];
 logic doubled_valid,doubled_start;logic [ROW_W-1:0] doubled_row;
 logic [P*96-1:0] doubled_data;
 logic [15:0] carry_epoch;logic [7:0] carry_generation;
 logic join_bad,carry_bad,admission_bad;
 assign coefficient_valid=doubled_valid && !out_error;assign coefficient_start=doubled_start && coefficient_valid;
 assign coefficient_data=$signed(doubled_data);assign coefficient_row=doubled_row;
 assign digit_valid=(&lane_digit_valid) && !out_error;assign digit_row=lane_offset[0][ROW_W-1:0];
 assign digit_start=digit_valid && lane_offset[0]==0;
 assign digit_epoch=carry_epoch;assign digit_generation=carry_generation;
 assign digit_eligible=digit_valid && context_enabled && carry_generation==live_generation;
 assign boundary_valid=(&lane_boundary_valid) && !out_error;
 assign boundary_eligible=boundary_valid && context_enabled && carry_generation==live_generation;
 assign next_epoch=carry_epoch+16'd1;assign next_generation=carry_generation;
 assign frame_done=(&lane_done) && !out_error;assign done_epoch=carry_epoch;
 assign fault_pending=out_error || setup_error || (|field_error) || (|field_pending) ||
  (|lane_error) || join_bad || carry_bad || admission_bad;
 always_comb begin
  join_bad=(|field_valid) && !joined;
  if(joined)begin
   for(int f=1;f<3;f=f+1)if(field_start[f]!=field_start[0] || field_row[f]!=field_row[0] ||
    field_epoch[f]!=field_epoch[0] || field_generation[f]!=field_generation[0] ||
    field_eligible[f]!=field_eligible[0])join_bad=1;
   if(!config_valid || bank_base[bank]!=qualified_base || bank_epoch[bank]!=field_epoch[0] ||
    bank_generation[bank]!=field_generation[0])join_bad=1;
  end
  carry_bad=((|crt_valid) && !(&crt_valid)) || ((|lane_digit_valid) && !(&lane_digit_valid)) ||
   ((|lane_boundary_valid) && !(&lane_boundary_valid)) || ((|lane_done) && !(&lane_done));
  if(begin_carry && (|lane_busy))carry_bad=1;
  for(int b=1;b<P;b=b+1)if(digit_valid && lane_offset[b]!=lane_offset[0])carry_bad=1;
  admission_bad=(in_slot_valid && frame_start && (!config_valid || base_in!=qualified_base)) ||
   (begin_setup && (in_slot_valid || correction_valid || (|lane_busy) || (|field_owners[0])));
 end
 for(genvar b=0;b<P;b=b+1)begin: arithmetic
  // Static inverse physical lane reverse(b,log2(P)) -> natural block b.
  localparam int PHYSICAL=reverse_lane(b);
  genefer_crt3_27_mont_pipe crt (
   .clk,.rst_n,.in_valid(joined && !out_error),
   .r1({5'd0,field_data[0][27*PHYSICAL+:27]}),
   .r2({5'd0,field_data[1][27*PHYSICAL+:27]}),
   .r3({5'd0,field_data[2][27*PHYSICAL+:27]}),
   .ready(crt_ready[b]),.out_valid(crt_valid[b]),.coefficient(crt_coefficient[b]));
  genefer_stream27_blockcarry_lane_param_v1 #(.AW(AW),.P(P)) carry (
   .clk,.rst_n,.begin_block(begin_carry),.in_valid(coefficient_valid),
   .block_start(doubled_start),.block_end(doubled_row==ROW_W'(ROWS-1)),
   .base(qualified_base),.reciprocal,.coefficient_limit,
   .coefficient($signed(doubled_data[96*b+:96])),.offset(AW'(doubled_row)),
   .busy(lane_busy[b]),.done(lane_done[b]),.error(lane_error[b]),.error_code(lane_error_code[b]),
   .digit_valid(lane_digit_valid[b]),.digit(lane_digit[b]),.digit_offset(lane_offset[b]),
   .boundary_valid(lane_boundary_valid[b]),.boundary_low(lane_low[b]),.boundary_high(lane_high[b]));
  assign digit_data[32*b+:32]=lane_digit[b];
  if(b==0)begin: signed_wrap
   wire signed [32:0] signed_low=$signed({1'b0,lane_low[P-1]});
   wire signed [32:0] signed_high=$signed({lane_high[P-1][31],lane_high[P-1]});
   assign next_c0[0+:32]=32'(-signed_low);assign next_c1[0+:32]=32'(-signed_high);
  end else begin: rotate
   assign next_c0[32*b+:32]=lane_low[b-1];assign next_c1[32*b+:32]=lane_high[b-1];
  end
 end
 always_ff @(posedge clk)begin
  if(joined)begin crt_tag[0]<={field_epoch[0],field_generation[0],field_row[0]};crt_double[0]<=bank_double[bank];end
  for(int d=1;d<16;d=d+1)begin crt_tag[d]<=crt_tag[d-1];crt_double[d]<=crt_double[d-1];end
  if(&crt_valid)begin
   for(int b=0;b<P;b=b+1)doubled_data[96*b+:96]<=crt_double[15] ? crt_coefficient[b]<<<1 : crt_coefficient[b];
   doubled_row<=crt_tag[15][ROW_W-1:0];doubled_start<=crt_tag[15][ROW_W-1:0]==0;
  end
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin out_error<=0;doubled_valid<=0;carry_epoch<=0;carry_generation<=0;end
  else begin
   if(fault_pending)out_error<=1;
   doubled_valid<=(&crt_valid) && !out_error;
   if(frame_accept && in_slot_valid && frame_start)begin
    bank_epoch[epoch_in[0]]<=epoch_in;bank_generation[epoch_in[0]]<=generation_in;
    bank_base[epoch_in[0]]<=base_in;bank_double[epoch_in[0]]<=double_in;
   end
   if(begin_carry)begin carry_epoch<=field_epoch[0];carry_generation<=field_generation[0];end
  end
 end
 // synthesis translate_off
 initial if(AW!=5 || P!=8 || CONTEXTS!=1)$fatal(1,"S4_THREEFIELD_EXPLICIT_GEOMETRY");
 // synthesis translate_on
endmodule
