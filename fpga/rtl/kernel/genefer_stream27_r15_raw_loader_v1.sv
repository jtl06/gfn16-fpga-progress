// Private R15 raw cold-load control. N words go DIRECTLY to retained image RAM;
// only two small headers and 32 correction words/context are stored here.
// This core-clock leaf is not the PCIe/CDC wrapper. No hardware profile import:
// upper192 profile bits MUST be zero, original START/PROFILE does real setup.
module genefer_stream27_r15_raw_loader_v1 #(parameter int AW=8,P=16)(
 input logic clk,rst_n,link_drained,
 input logic [1:0] core_idle,
 input logic [15:0] core_generation,
 input logic [31:0] core_next_epoch,
 input logic core_error,
 input logic begin_valid,cancel,commit_valid,word_valid,context_in,
 input logic [55:0] owner,
 input logic [31:0] session,lease,count,double_mask,current_session,
 input logic [2:0] mode,
 input logic [255:0] profile,
 input logic [AW+1:0] word_index,
 input logic [31:0] word_data,
 input logic transport_empty,
 output logic word_ready,active,error,
 output logic [31:0] next_lease,
 output logic [1:0] loaded,invalidate,
 output logic image_write,image_context,
 output logic [AW-1:0] image_address,
 output logic [31:0] image_data,
 input logic image_ready,image_ack,
 output logic [63:0] saved_base,saved_count,saved_mask,
 output logic [1:0] saved_batch,saved_feed,saved_double,
 output logic [2*P*32-1:0] saved_c0,saved_c1,
 output logic [111:0] saved_owner,
 input logic [1:0] requested_start,
 output logic [1:0] admitted_start,
 output logic [AW+2:0] applied_count
);
 localparam int N=1<<AW,K=2*N+24*P;
 localparam int MIN_B=(2*K+2)/3+1,MIN_BASE=2*N+5>MIN_B ? 2*N+5:MIN_B;
 logic held_context,local_error,guard_error,guard_publish;
 logic [31:0] sessions[0:1],leases[0:1];
 logic session_seen;
 logic [31:0] reset_session;
 logic [AW:0] ack_count;
 logic image_ack_expected;
 logic [55:0] expected_owner;
 logic [31:0] selected_count;
 logic selected_context,header_ok,begin_ok,cancel_ok,start_ok,command_bad;
 logic [7:0] next_gen;
 logic [15:0] final_epoch;
 logic guard_bank_write,guard_bank_context,published_context;
 logic [AW+1:0] guard_bank_index;
 logic [31:0] guard_bank_data;
 logic [55:0] guard_bank_owner,published_owner;
 logic [255:0] published_profile;
 logic [31:0] selected_base;
 logic [2:0] selected_mode;
 wire stop=local_error || guard_error || core_error;
 assign error=stop;
 always_comb begin
  selected_context=active ? held_context:context_in;
  selected_count=active ? saved_count[selected_context*32+:32]:count;
  selected_base=active ? saved_base[selected_context*32+:32]:profile[31:0];
  selected_mode=active ? {saved_double[selected_context],saved_feed[selected_context],saved_batch[selected_context]}:mode;
  next_gen=core_generation[selected_context*8+:8]+8'd1;
  final_epoch=core_next_epoch[selected_context*16+:16]+16'(selected_count-32'd1);
  expected_owner={selected_count-32'd1,final_epoch,next_gen};
  header_ok=selected_count!=0 && selected_base>=32'(MIN_BASE) && selected_base<=32'd1000000000 &&
   core_generation[selected_context*8+:8]!=8'hff &&
   (!selected_mode[1] || selected_mode[0]) &&
   (selected_mode[0] || selected_count==1) &&
   (selected_mode[1] || selected_count<=32);
  if(!active)header_ok=header_ok && profile[255:64]==0 &&
    profile[63:40]==0 && profile[39:32]==next_gen;
  if(!active)header_ok=header_ok && session==current_session && lease==next_lease && next_lease!=0;
  else header_ok=header_ok && sessions[held_context]==current_session;
  begin_ok=rst_n && link_drained && !stop && begin_valid && !active && !guard_publish &&
   !cancel && !commit_valid && !word_valid && core_idle[context_in] && header_ok && owner==expected_owner;
  cancel_ok=cancel && session==current_session && owner==saved_owner[context_in*56+:56] &&
   session==sessions[context_in] && lease==leases[context_in] &&
   ((!active && loaded[context_in]) || (active && context_in==held_context));
  command_bad=(cancel && (!cancel_ok || begin_valid || word_valid || commit_valid)) ||
   (begin_valid && !begin_ok) ||
   (session_seen && current_session!=reset_session);
  invalidate=0;
  if(begin_ok)invalidate[context_in]=1;
  if(cancel_ok)invalidate[context_in]=1;
  start_ok=!stop && !command_bad && link_drained && transport_empty && (&core_idle) && !active && !guard_publish &&
   !begin_valid && !word_valid && !commit_valid && !cancel &&
   ((requested_start & ~loaded)==0) && ((requested_start & ~core_idle)==0);
  admitted_start=start_ok ? requested_start:2'b0;
 end
 assign image_write=guard_bank_write && int'(guard_bank_index)<N && !stop;
 assign image_context=active ? held_context:context_in;
 assign image_address=word_index[AW-1:0];
 assign image_data=guard_bank_data;
 genefer_stream27_r15_direct_write_guard_v1 #(.AW(AW)) guard(
  .clk,.rst_n,.link_drained(link_drained && !stop && !command_bad && (!active || sessions[held_context]==current_session)),.cancel(cancel_ok),
  .begin_valid(begin_valid && !guard_publish),.begin_context(context_in),.begin_owner(owner),.expected_owner,
  .begin_session(session),.begin_lease(lease),.begin_profile(profile),
  .core_idle(core_idle[selected_context]),.lease_safe(core_idle[selected_context]),
  .profile_ok(header_ok),.word_valid,.word_context(context_in),.word_owner(owner),
  .word_session(session),.word_lease(lease),.word_index,.word_data,
  .bank_grant(int'(word_index)>=N || image_ready),.peer_port_busy(1'b0),
  .word_ready,.bank_write(guard_bank_write),.bank_index(guard_bank_index),
  .bank_data(guard_bank_data),.bank_context(guard_bank_context),.bank_owner(guard_bank_owner),
  .commit_valid,.transport_empty(transport_empty && ack_count==(AW+1)'(N) && !image_ack_expected),
  .commit_session(session),.commit_lease(lease),.commit_owner(owner),.commit_context(context_in),
  .active,.error(guard_error),.publish(guard_publish),.published_context,
  .published_owner,.published_profile,.applied_count
 );
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   local_error<=0;held_context<=0;loaded<=0;ack_count<=0;image_ack_expected<=0;next_lease<=1;
   session_seen<=0;reset_session<=0;
   saved_base<=0;saved_count<=0;saved_mask<=0;saved_batch<=0;saved_feed<=0;saved_double<=0;saved_owner<=0;
   sessions[0]<=0;sessions[1]<=0;leases[0]<=0;leases[1]<=0;
  end else begin
   if(link_drained && !session_seen)begin session_seen<=1;reset_session<=current_session;end
   // Transport session changes require the common core/FIFO reset. A mere
   // MMIO epoch change cannot make retained publication authoritative again.
   if(session_seen && (!link_drained || current_session!=reset_session))local_error<=1;
   image_ack_expected<=image_write;
   if(!link_drained || core_error)begin loaded<=0;ack_count<=0;image_ack_expected<=0;end
   else if(!stop)begin
    if(command_bad)local_error<=1;
    if(cancel && !cancel_ok)local_error<=1;
    if(begin_valid && guard_publish)local_error<=1;
    if(active && sessions[held_context]!=current_session)local_error<=1;
    if((|requested_start) && !start_ok)local_error<=1;
    if(active && !cancel_ok && image_ack!=image_ack_expected)local_error<=1;
    if(active && image_ack && !cancel_ok)ack_count<=ack_count+(AW+1)'(1);
    if(begin_ok)begin
     held_context<=context_in;loaded[context_in]<=0;ack_count<=0;image_ack_expected<=0;
     next_lease<=next_lease+32'd1;
     saved_base[context_in*32+:32]<=profile[31:0];saved_count[context_in*32+:32]<=count;
     saved_mask[context_in*32+:32]<=double_mask;saved_batch[context_in]<=mode[0];
     saved_feed[context_in]<=mode[1];saved_double[context_in]<=mode[2];
     saved_owner[context_in*56+:56]<=owner;sessions[context_in]<=session;leases[context_in]<=lease;
    end
    if(cancel_ok)begin loaded[context_in]<=0;ack_count<=0;image_ack_expected<=0;end
    if(guard_publish)loaded[published_context]<=1;
    if(|admitted_start)loaded<=loaded & ~admitted_start;
   end
  end
 end
 // No reset on correction payload: only complete loaded+header authority may
 // read it, and every new transaction overwrites all32 values before COMMIT.
 always_ff @(posedge clk)if(guard_bank_write && !stop)begin
  if(int'(guard_bank_index)>=N && int'(guard_bank_index)<N+P)
   saved_c0[guard_bank_context*P*32+(int'(guard_bank_index)-N)*32+:32]<=guard_bank_data;
  else if(int'(guard_bank_index)>=N+P && int'(guard_bank_index)<N+2*P)
   saved_c1[guard_bank_context*P*32+(int'(guard_bank_index)-N-P)*32+:32]<=guard_bank_data;
 end
 // synthesis translate_off
 initial if(P!=16 || AW<5 || AW>16)$fatal(1,"R15_RAW_LOADER_GEOMETRY");
 // synthesis translate_on
endmodule
