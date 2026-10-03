// Real S4-b arithmetic intermediate. Canonical host/readback gate is separate.
module genefer_stream27_threefield_carry_aw16_p16_registered_error_v1_protected_field100_v1_host_offload_field100_v1 #(parameter int AW=16,P=16,CONTEXTS=2,CORR_SERIAL_BFS=2,MONT_FACTORED=1,COMM_STAGE_SHARED_MLAB=1) (
 input logic clk,rst_n,begin_setup,setup_context,in_slot_valid,frame_start,context_in,correction_context,double_in,
 input logic [1:0] context_enabled,
 input logic [7:0] generation_in,input logic [15:0] live_generation,
 input logic [31:0] base_in,
 input logic [15:0] epoch_in,correction_epoch,
 input logic correction_valid,input logic [7:0] correction_generation,
 input logic off_cold_slot,off_cold_correction,
 input logic [3*P*32-1:0] off_planes,off_lows,off_highs,
 input logic [95:0] off_expected_reciprocal,off_expected_limit,
 output logic off_profile_good,
 input logic [P*32-1:0] data_in,c0_in,c1_in,
 output logic [1:0] config_valid,output logic setup_done,setup_done_context,out_error,fault_pending,error_barrier,frame_accept,correction_accept,
 output logic coefficient_valid,coefficient_start,coefficient_context,
 output logic signed [P*96-1:0] coefficient_data,
 output logic [AW-$clog2(P)-1:0] coefficient_row,
 output logic digit_valid,digit_start,digit_eligible,digit_context,
 output logic [P*32-1:0] digit_data,
 output logic [AW-$clog2(P)-1:0] digit_row,
 output logic [15:0] digit_epoch,output logic [7:0] digit_generation,
 output logic boundary_valid,boundary_eligible,boundary_context,
 output logic [P*32-1:0] next_c0,next_c1,
 output logic [15:0] next_epoch,output logic [7:0] next_generation,
 output logic frame_done,done_context,output logic [15:0] done_epoch);
 wire frame_profile_ok,field_input_valid;
 localparam int ROW_W=AW-$clog2(P),ROWS=1<<ROW_W,TAG_W=25+ROW_W;
 function automatic integer reverse_lane(input integer value);
  integer result;
  begin result=0;for(integer bit_index=0;bit_index<$clog2(P);bit_index=bit_index+1)begin
   result=(result<<1)|(value&1);value=value>>1;
  end reverse_lane=result;end
 endfunction
 wire [2:0] field_valid,field_start,field_eligible,field_error,field_pending,field_fast;
 wire [2:0] field_frame_accept,field_correction_accept;
 wire [P*27-1:0] field_data[0:2];wire [ROW_W-1:0] field_row[0:2];
 wire [15:0] field_epoch[0:2];wire [7:0] field_generation[0:2];wire [2:0] field_owners[0:2];
 wire [2:0] field_context;wire [1:0] field_correction_bank[0:2],field_pointwise_bank[0:2],field_sink_bank[0:2];
 logic [15:0] bank_epoch[0:3];logic [7:0] bank_generation[0:3];logic bank_double[0:3],bank_context[0:3];
 logic [31:0] bank_base[0:3];logic [3:0] bank_live;
 logic [1:0] metadata_free;logic metadata_free_found,setup_owner_busy;
 always_comb begin
  metadata_free='0;metadata_free_found=0;setup_owner_busy=0;
  for(int i=0;i<4;i=i+1)begin
   if(!bank_live[i] && !metadata_free_found)begin metadata_free=2'(i);metadata_free_found=1;end
   if(bank_live[i] && bank_context[i]==setup_context)setup_owner_busy=1;
  end
 end
 logic setup_context_q;
 logic [31:0] profile_base[0:1];logic [95:0] profile_reciprocal[0:1];
 logic [76:0] profile_limit[0:1];logic [7:0] profile_generation[0:1];
 wire unit_config_valid,unit_setup_done;
 wire setup_error,setup_busy;wire [31:0] qualified_base,qualified_generation;
 wire [95:0] reciprocal;wire [76:0] coefficient_limit;
 genefer_stream27_blockcarry_setup_param_v1 #(.AW(AW),.P(P)) shared_setup (
  .clk,.rst_n,.begin_setup,.cancel(error_barrier),.base(base_in),.generation({24'd0,generation_in}),
  .busy(setup_busy),.done(unit_setup_done),.error(setup_error),.config_valid(unit_config_valid),
  .accepted_base(qualified_base),.out_generation(qualified_generation),.coefficient_limit,.reciprocal);
 genefer_stream27_shared_warm_aw16_p16_f0_storage_combo_quarantine_v1_timing10_v1_protected_field100_v1_host_offload_field100_v1 #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) field0 (
  .clk,.rst_n,.in_slot_valid(field_input_valid),.frame_start(frame_start && frame_profile_ok),
  .context_enabled(context_enabled & {2{!error_barrier}}),.context_in,.correction_context,.generation_in,.live_generation,.base_in,
  .epoch_in,.correction_epoch,.correction_valid(correction_valid && !error_barrier && (!frame_start || frame_profile_ok)),.correction_generation,
  .off_cold_slot,.off_cold_correction,.off_plane(off_planes[0*P*32+:P*32]),
  .off_low(off_lows[0*P*32+:P*32]),.off_high(off_highs[0*P*32+:P*32]),
  .data_in,.c0_in,.c1_in,.out_slot_valid(field_valid[0]),.out_frame_start(field_start[0]),
  .out_eligible(field_eligible[0]),.out_error(field_error[0]),.out_error_fast(field_fast[0]),.fault_pending(field_pending[0]),
  .generation_out(field_generation[0]),.out_context(field_context[0]),.commit_context(),.data_out(field_data[0]),.out_epoch(field_epoch[0]),
  .commit_valid(),.commit_frame_start(),.commit_generation(),.commit_epoch(),.commit_data(),
  .owner_count(field_owners[0]),.correction_bank(field_correction_bank[0]),
  .pointwise_bank(field_pointwise_bank[0]),.sink_bank(field_sink_bank[0]),.frame_accept(field_frame_accept[0]),
  .correction_accept(field_correction_accept[0]),.output_row(field_row[0]),.cycle_count(),.frame_count());
 genefer_stream27_shared_warm_aw16_p16_f1_storage_combo_quarantine_v1_timing10_v1_protected_field100_v1_host_offload_field100_v1 #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) field1 (
  .clk,.rst_n,.in_slot_valid(field_input_valid),.frame_start(frame_start && frame_profile_ok),
  .context_enabled(context_enabled & {2{!error_barrier}}),.context_in,.correction_context,.generation_in,.live_generation,.base_in,
  .epoch_in,.correction_epoch,.correction_valid(correction_valid && !error_barrier && (!frame_start || frame_profile_ok)),.correction_generation,
  .off_cold_slot,.off_cold_correction,.off_plane(off_planes[1*P*32+:P*32]),
  .off_low(off_lows[1*P*32+:P*32]),.off_high(off_highs[1*P*32+:P*32]),
  .data_in,.c0_in,.c1_in,.out_slot_valid(field_valid[1]),.out_frame_start(field_start[1]),
  .out_eligible(field_eligible[1]),.out_error(field_error[1]),.out_error_fast(field_fast[1]),.fault_pending(field_pending[1]),
  .generation_out(field_generation[1]),.out_context(field_context[1]),.commit_context(),.data_out(field_data[1]),.out_epoch(field_epoch[1]),
  .commit_valid(),.commit_frame_start(),.commit_generation(),.commit_epoch(),.commit_data(),
  .owner_count(field_owners[1]),.correction_bank(field_correction_bank[1]),
  .pointwise_bank(field_pointwise_bank[1]),.sink_bank(field_sink_bank[1]),.frame_accept(field_frame_accept[1]),
  .correction_accept(field_correction_accept[1]),.output_row(field_row[1]),.cycle_count(),.frame_count());
 genefer_stream27_shared_warm_aw16_p16_f2_storage_combo_quarantine_v1_timing10_v1_protected_field100_v1_host_offload_field100_v1 #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) field2 (
  .clk,.rst_n,.in_slot_valid(field_input_valid),.frame_start(frame_start && frame_profile_ok),
  .context_enabled(context_enabled & {2{!error_barrier}}),.context_in,.correction_context,.generation_in,.live_generation,.base_in,
  .epoch_in,.correction_epoch,.correction_valid(correction_valid && !error_barrier && (!frame_start || frame_profile_ok)),.correction_generation,
  .off_cold_slot,.off_cold_correction,.off_plane(off_planes[2*P*32+:P*32]),
  .off_low(off_lows[2*P*32+:P*32]),.off_high(off_highs[2*P*32+:P*32]),
  .data_in,.c0_in,.c1_in,.out_slot_valid(field_valid[2]),.out_frame_start(field_start[2]),
  .out_eligible(field_eligible[2]),.out_error(field_error[2]),.out_error_fast(field_fast[2]),.fault_pending(field_pending[2]),
  .generation_out(field_generation[2]),.out_context(field_context[2]),.commit_context(),.data_out(field_data[2]),.out_epoch(field_epoch[2]),
  .commit_valid(),.commit_frame_start(),.commit_generation(),.commit_epoch(),.commit_data(),
  .owner_count(field_owners[2]),.correction_bank(field_correction_bank[2]),
  .pointwise_bank(field_pointwise_bank[2]),.sink_bank(field_sink_bank[2]),.frame_accept(field_frame_accept[2]),
  .correction_accept(field_correction_accept[2]),.output_row(field_row[2]),.cycle_count(),.frame_count());
 assign frame_profile_ok=config_valid[context_in] && base_in==profile_base[context_in] &&
  generation_in==profile_generation[context_in] && metadata_free_found;
 assign field_input_valid=in_slot_valid && !error_barrier && (!frame_start || frame_profile_ok);
 assign frame_accept=&field_frame_accept;assign correction_accept=&field_correction_accept;
 wire joined=&field_valid;
 wire join_start=&field_start;
 wire [1:0] bank=field_sink_bank[0];
 wire begin_carry=joined && join_start && !error_barrier;
 wire [P-1:0] crt_valid,crt_ready,lane_busy,lane_done,lane_error,lane_digit_valid,lane_boundary_valid;
 wire [3:0] lane_error_code[0:P-1];wire signed [95:0] crt_coefficient[0:P-1];
 wire [31:0] lane_digit[0:P-1],lane_low[0:P-1];wire signed [31:0] lane_high[0:P-1];
 wire [AW-1:0] lane_offset[0:P-1];
 logic [TAG_W-1:0] crt_tag[0:15];logic crt_double[0:15];
 logic doubled_valid,doubled_start;logic [ROW_W-1:0] doubled_row;
 logic [P*96-1:0] doubled_data;
 logic [15:0] carry_epoch;logic [7:0] carry_generation;logic carry_context;
 logic doubled_context;
 logic join_bad,carry_bad,admission_bad;
 logic local_fault_q;
 wire local_fault_now=setup_error || (|lane_error) || join_bad || carry_bad || admission_bad;
 assign coefficient_valid=doubled_valid && !error_barrier;assign coefficient_start=doubled_start && coefficient_valid;
 assign coefficient_data=$signed(doubled_data);assign coefficient_row=doubled_row;assign coefficient_context=doubled_context;
 assign digit_valid=(&lane_digit_valid) && !error_barrier;assign digit_row=lane_offset[0][ROW_W-1:0];
 assign digit_start=digit_valid && lane_offset[0]==0;
 assign digit_epoch=carry_epoch;assign digit_generation=carry_generation;assign digit_context=carry_context;
 assign digit_eligible=digit_valid && context_enabled[carry_context] && carry_generation==8'(live_generation>>(carry_context*8));
 assign boundary_valid=(&lane_boundary_valid) && !error_barrier;
 assign boundary_context=carry_context;
 assign boundary_eligible=boundary_valid && context_enabled[carry_context] && carry_generation==8'(live_generation>>(carry_context*8));
 assign next_epoch=carry_epoch+16'd1;assign next_generation=carry_generation;
 assign frame_done=(&lane_done) && !error_barrier;assign done_epoch=carry_epoch;assign done_context=carry_context;
 // Every raw field_pending reaches its unchanged local controller on this edge.
 // Do not route its deep combinational cone into the global sticky report.
 assign error_barrier=out_error || (|field_fast) || local_fault_q;
 assign fault_pending=error_barrier;
 always_comb begin
  join_bad=(|field_valid) && !joined;
  if(joined)begin
   for(int f=1;f<3;f=f+1)if(field_start[f]!=field_start[0] || field_row[f]!=field_row[0] ||
    field_epoch[f]!=field_epoch[0] || field_generation[f]!=field_generation[0] ||
    field_eligible[f]!=field_eligible[0] || field_context[f]!=field_context[0] ||
    field_sink_bank[f]!=field_sink_bank[0])join_bad=1;
   if(!config_valid[field_context[0]] || !bank_live[bank] ||
    bank_base[bank]!=profile_base[field_context[0]] || bank_context[bank]!=field_context[0] ||
    bank_epoch[bank]!=field_epoch[0] || bank_generation[bank]!=field_generation[0])join_bad=1;
  end
  carry_bad=((|crt_valid) && !(&crt_valid)) || ((|lane_digit_valid) && !(&lane_digit_valid)) ||
   ((|lane_boundary_valid) && !(&lane_boundary_valid)) || ((|lane_done) && !(&lane_done));
  if(begin_carry && (|lane_busy))carry_bad=1;
  for(int b=1;b<P;b=b+1)if(digit_valid && lane_offset[b]!=lane_offset[0])carry_bad=1;
  admission_bad=(in_slot_valid && frame_start && (!config_valid[context_in] ||
    base_in!=profile_base[context_in] || generation_in!=profile_generation[context_in] || !metadata_free_found)) ||
   (begin_setup && (in_slot_valid || correction_valid || setup_busy || setup_owner_busy ||
    ((|lane_busy) && carry_context==setup_context)));
  if((|field_frame_accept) && !(&field_frame_accept))admission_bad=1;
  if((|field_correction_accept) && !(&field_correction_accept))admission_bad=1;
 end
 for(genvar b=0;b<P;b=b+1)begin: arithmetic
  (* preserve, dont_merge *) logic carry_quarantine_q;
  always_ff @(posedge clk or negedge rst_n)begin
   if(!rst_n)carry_quarantine_q<=0;
   else carry_quarantine_q<=carry_quarantine_q || error_barrier;
  end
  // Static inverse physical lane reverse(b,log2(P)) -> natural block b.
  localparam int PHYSICAL=reverse_lane(b);
  genefer_crt3_27_mont_pipe crt (
   .clk,.rst_n,.in_valid(joined && !error_barrier),
   .r1({5'd0,field_data[0][27*PHYSICAL+:27]}),
   .r2({5'd0,field_data[1][27*PHYSICAL+:27]}),
   .r3({5'd0,field_data[2][27*PHYSICAL+:27]}),
   .ready(crt_ready[b]),.out_valid(crt_valid[b]),.coefficient(crt_coefficient[b]));
  genefer_stream27_blockcarry_lane_localbase_v1 #(.AW(AW),.P(P)) carry (
   .clk,.rst_n,.begin_block(joined && join_start && !carry_quarantine_q),
   .in_valid(doubled_valid && !carry_quarantine_q),
   .block_start(doubled_start),.block_end(doubled_row==ROW_W'(ROWS-1)),
   .base(profile_base[field_context[0]]),.reciprocal(profile_reciprocal[field_context[0]]),.coefficient_limit(profile_limit[field_context[0]]),
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
  if(joined)begin crt_tag[0]<={field_context[0],field_epoch[0],field_generation[0],field_row[0]};crt_double[0]<=bank_double[bank];end
  for(int d=1;d<16;d=d+1)begin crt_tag[d]<=crt_tag[d-1];crt_double[d]<=crt_double[d-1];end
  if(&crt_valid)begin
   for(int b=0;b<P;b=b+1)doubled_data[96*b+:96]<=crt_double[15] ? crt_coefficient[b]<<<1 : crt_coefficient[b];
   doubled_row<=crt_tag[15][ROW_W-1:0];doubled_start<=crt_tag[15][ROW_W-1:0]==0;doubled_context<=crt_tag[15][TAG_W-1];
  end
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)local_fault_q<=0;
  else if(local_fault_now)local_fault_q<=1;
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin off_profile_good<=0; out_error<=0;doubled_valid<=0;carry_epoch<=0;carry_generation<=0;carry_context<=0;
   bank_live<=0;config_valid<=0;setup_done<=0;setup_done_context<=0;setup_context_q<=0;end
  else begin
   setup_done<=0;
   if(begin_setup && !setup_busy && !admission_bad && !error_barrier)begin
    setup_context_q<=setup_context;config_valid[setup_context]<=0;
   end
   if(unit_setup_done && unit_config_valid && !error_barrier)begin
    off_profile_good<=reciprocal==off_expected_reciprocal && {19'd0,coefficient_limit}==off_expected_limit;
    profile_base[setup_context_q]<=qualified_base;profile_reciprocal[setup_context_q]<=reciprocal;
    profile_limit[setup_context_q]<=coefficient_limit;profile_generation[setup_context_q]<=qualified_generation[7:0];
    config_valid[setup_context_q]<=1;setup_done<=1;setup_done_context<=setup_context_q;
   end
   if((|field_error) || local_fault_q)out_error<=1;
   doubled_valid<=(&crt_valid) && !error_barrier;
   if(frame_accept && in_slot_valid && frame_start)begin
    bank_live[metadata_free]<=1;bank_epoch[metadata_free]<=epoch_in;bank_generation[metadata_free]<=generation_in;
    bank_base[metadata_free]<=base_in;bank_double[metadata_free]<=double_in;bank_context[metadata_free]<=context_in;
   end
   if(joined && field_row[0]==ROW_W'(ROWS-1) && !join_bad && !error_barrier)bank_live[bank]<=0;
   if(begin_carry)begin carry_epoch<=field_epoch[0];carry_generation<=field_generation[0];carry_context<=field_context[0];end
  end
 end
 // synthesis translate_off
 initial if(AW!=16 || P!=16 || CONTEXTS!=2 || CORR_SERIAL_BFS!=2 || MONT_FACTORED!=1 || COMM_STAGE_SHARED_MLAB!=1)$fatal(1,"S4_THREEFIELD_EXPLICIT_GEOMETRY");
 // synthesis translate_on
endmodule
