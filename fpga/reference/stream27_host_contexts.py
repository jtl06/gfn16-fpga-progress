"""Two-context host assembly with real shared arithmetic and finalization.

Initial jobs are accepted as a joint batch (one or both contexts); a new batch
waits for both previous jobs to publish. Each context's final raw image reuses
its unpublished shadow. One canonical scratch serializes stopped jobs while
the other arithmetic context can continue. No per-square canonical barrier.
This explicit API is not the frozen one-context scalar command ABI.
"""
import hashlib
from . import stream27_warm_contexts as warm
from . import s4_two_context_model_v1 as calendar
from . import stream27_contexts_diet_schedule as diet_calendar

ROOT = warm.ROOT
SELF = 'reference/stream27_host_contexts.py'
SHADOW = 'rtl/kernel/genefer_stream27_host_image_rowwrite_v1.sv'
CANONICAL = 'rtl/kernel/genefer_stream27_canonical_image_pipe_v1.sv'
DESCRIPTOR = 'rtl/kernel/genefer_stream27_descriptor_fifo_ff_v1.sv'
RAM = 'rtl/kernel/genefer_sdp_ram32.sv'


def source(n, p, child, g,*,plan=None):
    plan = calendar.schedule(n, p) if plan is None else plan
    cold_second = next(c['accept'] for c in plan['correction'] if c['tag'][0] == 1 and c['tag'][3] == 0)
    top = f'genefer_stream27_host_contexts_aw{n.bit_length()-1}_p{p}_v1'
    s = r'''// Joint two-context jobs, final-only canonical scratch, independent shadow publication.
module @TOP@ #(parameter int AW=@AW@,P=@P@,CONTEXTS=2,
 parameter int unsigned EPOCH_SEED0=0,EPOCH_SEED1=0) (
 input logic clk,rst_n,host_context,load_we,read_en,
 input logic [AW-1:0] host_addr,input logic signed [31:0] write_data,
 input logic [1:0] start_contexts,batch_mode,feed_mode,double_bit,
 input logic [63:0] base,warm_count,double_mask,
 input logic [2*P*32-1:0] initial_c0,initial_c1,
 input logic command_context,command_valid,command_double,
 input logic [31:0] command_index,input logic [7:0] command_generation,
 output logic command_ready,command_accept,
 output logic [1:0] operation_accept,busy,done,canonical_ready,warm_done,
 output logic [63:0] completed_squares,operations_started,
 output logic [15:0] accepted_generation,output logic [5:0] feed_level,
 output logic read_valid,read_context,output logic [55:0] read_owner,output logic signed [95:0] read_data,
 output logic error,output logic [63:0] cycles,
 output logic [127:0] canonical_cycles,image_copy_cycles,
 output logic [1:0] waiting_final,output logic [63:0] final_image_rows);
 localparam int N=1<<AW,ROW_W=AW-$clog2(P),ROWS=1<<ROW_W,K=2*N+24*P;
 localparam int MIN_PROOF=(2*K+2)/3+1,MIN_BASE=(2*N+5)>MIN_PROOF ? 2*N+5 : MIN_PROOF;
 localparam int CONTEXT_OFFSET=@OFFSET@,SECOND_CORRECTION=@SECOND_CORRECTION@;
 typedef enum logic[3:0] {IDLE,PROFILE,COLD_PENDING,COLD_ACTIVE,RUN,RAW_READY,CANON_LOAD,CANON_WAIT,COPY,COPY_DRAIN} phase_t;
 phase_t phase[0:1];
 logic local_error;logic [1:0] jobs,job_feed,job_double,published,done_q;
 logic [31:0] job_base[0:1],job_count[0:1],job_mask[0:1],next_index[0:1];
 logic [7:0] job_generation[0:1];logic [15:0] job_epoch[0:1],next_epoch[0:1];
 logic [P*32-1:0] cold_c0[0:1],cold_c1[0:1],final_c0[0:1],final_c1[0:1];
 logic [ROW_W:0] raw_rows[0:1];logic [63:0] context_canonical_cycles[0:1],context_copy_cycles[0:1];
 wire [111:0] live_owner={ {job_count[1]-32'd1,16'(job_epoch[1]+16'(job_count[1]-32'd1)),job_generation[1]},
  {job_count[0]-32'd1,16'(job_epoch[0]+16'(job_count[0]-32'd1)),job_generation[0]} };
 wire [1:0] owner_enabled=jobs;
 wire [2:0] levels[0:1];wire [31:0] head_index[0:1];wire [7:0] head_generation[0:1];wire [1:0] head_double;
 wire [1:0] feed_pop,feed_push;
 wire command_state=phase[command_context]==PROFILE || phase[command_context]==COLD_PENDING ||
  phase[command_context]==COLD_ACTIVE || phase[command_context]==RUN;
 assign command_ready=job_feed[command_context] && command_state && !error &&
  (levels[command_context]<3'd4 || feed_pop[command_context]);
 wire ingress_bad=command_valid && command_ready &&
  (command_generation!=job_generation[command_context] || command_index!=next_index[command_context] ||
   command_index==0 || command_index>=job_count[command_context]);
 assign feed_push[0]=command_valid && command_ready && !ingress_bad && !command_context;
 assign feed_push[1]=command_valid && command_ready && !ingress_bad && command_context;
 assign command_accept=|feed_push;assign operation_accept=feed_pop;
 assign accepted_generation={job_generation[1],job_generation[0]};assign feed_level={levels[1],levels[0]};
 for(genvar c=0;c<2;c=c+1)begin: descriptors
  genefer_stream27_descriptor_fifo_ff_v1 fifo (
   .clk,.rst_n,.clear(start_contexts[c] && !(|busy)),.push(feed_push[c]),.pop(feed_pop[c]),
   .push_index(command_index),.push_generation(command_generation),.push_double(command_double),
   .head_index(head_index[c]),.head_generation(head_generation[c]),.head_double(head_double[c]),.level(levels[c]));
  assign busy[c]=phase[c]!=IDLE && !error;
  assign waiting_final[c]=phase[c]==RAW_READY && !error;
 end
 logic setup_inflight,setup_context;
 wire begin_setup=!error && !setup_inflight && (phase[0]==PROFILE || phase[1]==PROFILE);
 wire selected_setup_context=phase[0]!=PROFILE;
 wire [1:0] config_valid;wire setup_done,setup_done_context,child_error,child_pending;
 logic anchor_valid,anchor_context;logic [31:0] anchor_cycle;
 wire all_profiles_ready=phase[0]!=PROFILE && phase[1]!=PROFILE;
 wire cold_pending=phase[0]==COLD_PENDING || phase[1]==COLD_PENDING;
 wire first_cold_context=phase[0]!=COLD_PENDING;
 logic cold_reader,cold_context;logic [ROW_W-1:0] cold_row;
 logic source_valid,source_context;logic [ROW_W-1:0] source_row;
 logic [P*32-1:0] source_data;
 wire cold_start_request=!cold_reader && all_profiles_ready && cold_pending &&
  (!anchor_valid || 32'(cycles[31:0]-anchor_cycle)==32'(CONTEXT_OFFSET-3));
 wire selected_cold_context=anchor_valid ? !anchor_context : first_cold_context;
 wire source_start=source_valid && source_row==0;
 wire cold_second_correction=anchor_valid && jobs[!anchor_context] &&
  32'(cycles[31:0]-anchor_cycle)==32'(SECOND_CORRECTION);
 wire cold_first_correction=source_start && (!anchor_valid || source_context==anchor_context);
 wire cold_correction=cold_first_correction || cold_second_correction;
 wire cold_correction_context=cold_second_correction ? !anchor_context : source_context;
 wire [1:0] child_active,child_warm_done,child_cancelled;
 wire [63:0] child_completed,child_started;
 wire child_frame_accept,child_correction_accept,internal_frame_accept,internal_correction_accept;
 wire final_valid,final_context,final_boundary_valid,boundary_context;
 wire [55:0] final_owner;wire [ROW_W-1:0] digit_row;
 wire [P*32-1:0] digit_data,next_c0,next_c1;
 wire [31:0] boundary_sequence;
 wire [15:0] boundary_epoch;wire [7:0] boundary_generation;
 wire capture_bad=final_valid && (phase[final_context]!=RUN ||
  final_owner!=live_owner[final_context*56+:56] || raw_rows[final_context]>=(ROW_W+1)'(ROWS) ||
  digit_row!=raw_rows[final_context][ROW_W-1:0]);
 wire capture_fire=final_valid && !capture_bad && !error;
 logic capture_req_d;
 logic canonical_owner,canonical_owned;logic [ROW_W-1:0] load_row;logic [ROW_W:0] load_requested;
 logic [AW:0] copy_requested,copy_issued,copy_committed;
 logic row_kind_d,row_context_d;logic [ROW_W-1:0] row_address_d;
 wire shadow_row_request=!error && (cold_reader || (canonical_owned && phase[canonical_owner]==CANON_LOAD && load_requested<(ROW_W+1)'(ROWS)));
 wire shadow_row_context=cold_reader ? cold_context : canonical_owner;
 wire [ROW_W-1:0] shadow_row_address=cold_reader ? cold_row : load_row;
 wire shadow_row_valid,shadow_response_context,shadow_commit_ack,shadow_capture_ack,shadow_rejected;
 wire [55:0] shadow_response_owner;wire [P*32-1:0] shadow_row_data;
 wire shadow_scalar_valid,shadow_scalar_context;wire signed [95:0] shadow_scalar_data;wire [55:0] shadow_scalar_owner;
 wire response_bad=shadow_row_valid && (shadow_response_context!=row_context_d ||
  shadow_response_owner!=live_owner[row_context_d*56+:56]);
 wire canonical_load=shadow_row_valid && !row_kind_d && !response_bad && !error;
 wire canonical_begin=canonical_owned && phase[canonical_owner]==CANON_WAIT && !canon_busy && !canon_image_valid && !error;
 wire canon_busy,canon_done,canon_error,canon_image_valid,canon_read_valid;
 wire [7:0] canon_error_code;wire [63:0] canon_cycles;
 wire signed [95:0] canon_data;wire [AW-1:0] canon_address;
 wire canonical_read=canonical_owned && phase[canonical_owner]==COPY && copy_requested<(AW+1)'(N) && !error;
 wire copy_bad=canon_read_valid && (copy_issued>=(AW+1)'(N) || canon_address!=copy_issued[AW-1:0] ||
  canon_data[95:32]!={64{canon_data[31]}});
 wire copy_fire=canon_read_valid && canonical_owned &&
  (phase[canonical_owner]==COPY || phase[canonical_owner]==COPY_DRAIN) && !copy_bad && !error;
 assign error=local_error || child_error || canon_error;
 assign canonical_ready=published & {2{!error}};assign done=done_q & {2{!error}};
 assign read_valid=shadow_scalar_valid && canonical_ready[shadow_scalar_context] && !error;
 assign read_context=shadow_scalar_context;assign read_owner=shadow_scalar_owner;assign read_data=shadow_scalar_data;
 assign completed_squares=child_completed;assign operations_started=child_started;assign warm_done=child_warm_done;
 assign canonical_cycles={context_canonical_cycles[1],context_canonical_cycles[0]};
 assign image_copy_cycles={context_copy_cycles[1],context_copy_cycles[0]};
 assign final_image_rows={32'(raw_rows[1]),32'(raw_rows[0])};
 genefer_stream27_host_image_rowwrite_v1 #(.AW(AW),.P(P),.CONTEXTS(2),.OWNER_W(56)) shadows (
  .clk,.rst_n,.quarantine(error),.owner_enabled,.live_owner,
  .host_access(phase[host_context]==IDLE && !start_contexts[host_context] && !error),
  .load_we,.read_en,.host_context,.host_addr,.write_data,
  .row_read_req(shadow_row_request),.row_read_context(shadow_row_context),.row_read_address(shadow_row_address),
  .row_read_owner(live_owner[shadow_row_context*56+:56]),
  .commit_we(copy_fire),.commit_context(canonical_owner),.commit_address(canon_address),.commit_word(canon_data[31:0]),
  .commit_owner(live_owner[canonical_owner*56+:56]),
  .row_write_req(capture_fire),.row_write_context(final_context),.row_write_address(digit_row),
  .row_write_data(digit_data),.row_write_owner(final_owner),
  .read_valid(shadow_scalar_valid),.read_context(shadow_scalar_context),.read_data(shadow_scalar_data),.read_owner(shadow_scalar_owner),
  .row_read_valid(shadow_row_valid),.row_response_context(shadow_response_context),.row_read_data(shadow_row_data),
  .row_response_owner(shadow_response_owner),.commit_ack(shadow_commit_ack),.row_write_ack(shadow_capture_ack),.rejected(shadow_rejected));
 genefer_stream27_canonical_image_pipe_v1 #(.AW(AW),.P(P)) scratch (
  .clk,.rst_n,.load_valid(canonical_load),.load_row(row_address_d),.load_data(shadow_row_data),
  .begin_canonical(canonical_begin),.base(job_base[canonical_owner]),
  .c0(final_c0[canonical_owner]),.c1(final_c1[canonical_owner]),
  .read_req(canonical_read),.read_address(copy_requested[AW-1:0]),.busy(canon_busy),.done(canon_done),
  .error(canon_error),.image_valid(canon_image_valid),.error_code(canon_error_code),.cycles(canon_cycles),
  .read_valid(canon_read_valid),.read_address_out(canon_address),.read_data(canon_data));
 @CHILD@ #(.AW(AW),.P(P),.CONTEXTS(2)) engine (
  .clk,.rst_n,.begin_setup,.setup_context(selected_setup_context),
  .in_slot_valid(source_valid && !error),.frame_start(source_start),.context_in(source_context),
  .correction_context(cold_correction_context),.double_in(job_double[source_context]),
  .context_enabled(jobs & {2{!error}}),.live_generation({job_generation[1],job_generation[0]}),
  .generation_in(begin_setup ? job_generation[selected_setup_context] : job_generation[source_context]),
  .base_in(begin_setup ? job_base[selected_setup_context] : job_base[source_context]),
  .epoch_in(job_epoch[source_context]),.correction_epoch(job_epoch[cold_correction_context]),
  .correction_valid(cold_correction && !error),.correction_generation(job_generation[cold_correction_context]),
  .data_in(source_data),.c0_in(cold_c0[cold_correction_context]),.c1_in(cold_c1[cold_correction_context]),
  .square_count(job_count[source_context]),.double_mask(job_mask[source_context]),.feed_mode(job_feed[source_context]),
  .command_valid({levels[1]!=0,levels[0]!=0}),.command_double(head_double),
  .command_index({head_index[1],head_index[0]}),.command_generation({head_generation[1],head_generation[0]}),
  .command_accept(feed_pop),.active(child_active),.warm_done(child_warm_done),.warm_cancelled(child_cancelled),
  .completed_frames(child_completed),.started_frames(child_started),.config_valid,.setup_done,.setup_done_context,
  .out_error(child_error),.fault_pending(child_pending),.frame_accept(child_frame_accept),.correction_accept(child_correction_accept),
  .internal_frame_accept,.internal_correction_accept,.coefficient_valid(),.coefficient_start(),.coefficient_context(),
  .coefficient_data(),.coefficient_row(),.digit_valid(),.digit_start(),.digit_eligible(),.digit_context(),
  .digit_data,.digit_row,.digit_epoch(),.digit_generation(),.digit_sequence(),.boundary_sequence,
  .boundary_valid(),.boundary_eligible(),.boundary_context,.next_c0,.next_c1,
  .next_epoch(boundary_epoch),.next_generation(boundary_generation),.frame_done(),.done_context(),.done_epoch(),
  .final_load_valid(final_valid),.final_load_context(final_context),.final_boundary_valid,.final_load_owner(final_owner));
 function automatic integer reverse_lane(input integer value);
  integer result;
  begin result=0;for(integer bit_index=0;bit_index<$clog2(P);bit_index=bit_index+1)begin
   result=(result<<1)|(value&1);value=value>>1;
  end reverse_lane=result;end
 endfunction
 for(genvar lane=0;lane<P;lane=lane+1)begin: natural_cold_route
  localparam int NATURAL=reverse_lane(lane);
  always_ff @(posedge clk)if(shadow_row_valid && row_kind_d && !response_bad && !error)
   source_data[32*lane+:32]<=shadow_row_data[32*NATURAL+:32];
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   local_error<=0;jobs<=0;job_feed<=0;job_double<=0;done_q<=0;published<=0;cycles<=0;
   setup_inflight<=0;setup_context<=0;anchor_valid<=0;anchor_context<=0;anchor_cycle<=0;
   cold_reader<=0;cold_context<=0;cold_row<=0;source_valid<=0;source_context<=0;source_row<=0;
   canonical_owner<=0;canonical_owned<=0;load_row<=0;load_requested<=0;copy_requested<=0;copy_issued<=0;copy_committed<=0;
   row_kind_d<=0;row_context_d<=0;row_address_d<=0;capture_req_d<=0;
   next_epoch[0]<=16'(EPOCH_SEED0);next_epoch[1]<=16'(EPOCH_SEED1);
   for(int c=0;c<2;c=c+1)begin
    phase[c]<=IDLE;job_base[c]<=2;job_count[c]<=0;job_mask[c]<=0;next_index[c]<=1;
    job_generation[c]<=0;job_epoch[c]<=0;raw_rows[c]<=0;context_canonical_cycles[c]<=0;context_copy_cycles[c]<=0;
   end
  end else begin
   done_q<=0;source_valid<=shadow_row_valid && row_kind_d && !response_bad && !error;
   capture_req_d<=capture_fire;
   if(|busy)cycles<=cycles+64'd1;
   if(ingress_bad || capture_bad || response_bad || copy_bad || shadow_rejected ||
    (capture_req_d && !shadow_capture_ack) || (|child_cancelled))local_error<=1;
   if(shadow_row_request)begin row_kind_d<=cold_reader;row_context_d<=shadow_row_context;row_address_d<=shadow_row_address;end
   if(shadow_row_valid && row_kind_d && !response_bad)begin source_context<=row_context_d;source_row<=row_address_d;end
   if((|start_contexts) && !(|busy) && !canonical_owned && !error)begin
    jobs<=start_contexts;cycles<=0;anchor_valid<=0;published<=published & ~start_contexts;
    for(int c=0;c<2;c=c+1)if(start_contexts[c])begin
     phase[c]<=PROFILE;job_base[c]<=base[c*32+:32];job_count[c]<=batch_mode[c] ? warm_count[c*32+:32] : 32'd1;
     job_mask[c]<=double_mask[c*32+:32];job_feed[c]<=batch_mode[c] && feed_mode[c];job_double[c]<=double_bit[c];
     job_generation[c]<=job_generation[c]+8'd1;job_epoch[c]<=next_epoch[c];next_index[c]<=1;raw_rows[c]<=0;
     cold_c0[c]<=initial_c0[c*P*32+:P*32];cold_c1[c]<=initial_c1[c*P*32+:P*32];
     context_canonical_cycles[c]<=0;context_copy_cycles[c]<=0;
     if(base[c*32+:32]<32'(MIN_BASE) || base[c*32+:32]>32'd1000000000 || job_generation[c]==8'hff ||
      (batch_mode[c] && (warm_count[c*32+:32]==0 || (!feed_mode[c] && warm_count[c*32+:32]>32'd32))))local_error<=1;
    end
   end
   if(load_we && phase[host_context]==IDLE)published[host_context]<=0;
   if(begin_setup)begin setup_inflight<=1;setup_context<=selected_setup_context;end
   if(setup_done)begin
    if(!setup_inflight || setup_done_context!=setup_context || !config_valid[setup_context])local_error<=1;
    else begin setup_inflight<=0;phase[setup_context]<=COLD_PENDING;end
   end
   if(cold_start_request)begin cold_reader<=1;cold_context<=selected_cold_context;cold_row<=0;phase[selected_cold_context]<=COLD_ACTIVE;end
   if(cold_reader && shadow_row_request)begin
    if(cold_row==ROW_W'(ROWS-1))cold_reader<=0;else cold_row<=cold_row+ROW_W'(1);
   end
   if(child_frame_accept && source_start)begin
    phase[source_context]<=RUN;
    if(!anchor_valid)begin anchor_valid<=1;anchor_context<=source_context;anchor_cycle<=cycles[31:0];end
   end
   for(int c=0;c<2;c=c+1)if(feed_push[c])next_index[c]<=next_index[c]+32'd1;
   if(capture_fire)raw_rows[final_context]<=raw_rows[final_context]+(ROW_W+1)'(1);
   if(final_boundary_valid)begin
    if(boundary_sequence!=job_count[boundary_context]-32'd1 ||
     {boundary_sequence,16'(boundary_epoch-16'd1),boundary_generation}!=live_owner[boundary_context*56+:56])local_error<=1;
    final_c0[boundary_context]<=next_c0;final_c1[boundary_context]<=next_c1;
   end
   for(int c=0;c<2;c=c+1)if(child_warm_done[c])begin
    if(raw_rows[c]!=(ROW_W+1)'(ROWS) || child_completed[c*32+:32]!=job_count[c])local_error<=1;
    else phase[c]<=RAW_READY;
   end
   if(!canonical_owned && (phase[0]==RAW_READY || phase[1]==RAW_READY) && !error)begin
    canonical_owner<=phase[0]!=RAW_READY;canonical_owned<=1;load_row<=0;load_requested<=0;
    phase[phase[0]!=RAW_READY]<=CANON_LOAD;
   end
   if(canonical_owned && phase[canonical_owner]==CANON_LOAD && shadow_row_request && !cold_reader)begin
    load_requested<=load_requested+(ROW_W+1)'(1);
    if(load_row!=ROW_W'(ROWS-1))load_row<=load_row+ROW_W'(1);
   end
   if(canonical_load && row_address_d==ROW_W'(ROWS-1))phase[canonical_owner]<=CANON_WAIT;
   if(canon_done && canonical_owned && phase[canonical_owner]==CANON_WAIT)begin
    context_canonical_cycles[canonical_owner]<=canon_cycles;phase[canonical_owner]<=COPY;
    copy_requested<=0;copy_issued<=0;copy_committed<=0;
   end
   if(canonical_read)begin
    copy_requested<=copy_requested+(AW+1)'(1);
    if(copy_requested==(AW+1)'(N-1))phase[canonical_owner]<=COPY_DRAIN;
   end
   if(copy_fire)copy_issued<=copy_issued+(AW+1)'(1);
   if(canonical_owned && (phase[canonical_owner]==COPY || phase[canonical_owner]==COPY_DRAIN))
    context_copy_cycles[canonical_owner]<=context_copy_cycles[canonical_owner]+64'd1;
   if(shadow_commit_ack && canonical_owned)begin
    copy_committed<=copy_committed+(AW+1)'(1);
    if(copy_committed==(AW+1)'(N-1))begin
     if(copy_issued!=(AW+1)'(N) || copy_requested!=(AW+1)'(N))local_error<=1;
     else begin
      published[canonical_owner]<=1;done_q[canonical_owner]<=1;phase[canonical_owner]<=IDLE;canonical_owned<=0;
      next_epoch[canonical_owner]<=job_epoch[canonical_owner]+16'(job_count[canonical_owner]);
     end
    end
   end
  end
 end
 // synthesis translate_off
 initial if(AW!=@AW@ || P!=@P@ || CONTEXTS!=2 || EPOCH_SEED0>32'd65535 || EPOCH_SEED1>32'd65535)
  $fatal(1,"S4_CONTEXT_HOST_EXPLICIT_GEOMETRY");
 always @(posedge clk)if(rst_n && !error)begin
  if(capture_fire && copy_fire && final_context==canonical_owner)$fatal(1,"S4_CONTEXT_CAPTURE_COPY_ALIAS");
  if((|done) && (!(&((~done)|canonical_ready))))$fatal(1,"S4_CONTEXT_DONE_PUBLICATION");
 end
 // synthesis translate_on
endmodule
'''
    for token, value in {'TOP':top, 'AW':n.bit_length()-1, 'P':p, 'CHILD':child,
                         'OFFSET':g['warm_interval']//2, 'SECOND_CORRECTION':cold_second}.items():
        s = s.replace('@'+token+'@', str(value))
    return top, s


def cold_fence_source(top,text):
    new=top+'_cold_fence_v1'
    text=warm.arithmetic.once(text,'module '+top+' #','module '+new+' #')
    text=warm.arithmetic.once(text,'CONTEXTS=2','CONTEXTS=2,COLD_LAUNCH_FENCE=1')
    text=warm.arithmetic.once(text,'CONTEXTS!=2','CONTEXTS!=2 || COLD_LAUNCH_FENCE!=1')
    text=warm.arithmetic.once(text,'logic anchor_valid,anchor_context;logic [31:0] anchor_cycle;',
        'logic anchor_valid,anchor_context,first_cold_inflight;logic [31:0] anchor_cycle;')
    text=warm.arithmetic.once(text,'(!anchor_valid || 32\'(cycles[31:0]-anchor_cycle)==32\'(CONTEXT_OFFSET-3));',
        "((!anchor_valid && !first_cold_inflight) || (anchor_valid && 32'(cycles[31:0]-anchor_cycle)==32'(CONTEXT_OFFSET-3)));")
    text=warm.arithmetic.once(text,'anchor_valid<=0;anchor_context<=0;anchor_cycle<=0;',
        'anchor_valid<=0;anchor_context<=0;anchor_cycle<=0;first_cold_inflight<=0;')
    text=warm.arithmetic.once(text,'jobs<=start_contexts;cycles<=0;anchor_valid<=0;',
        'jobs<=start_contexts;cycles<=0;anchor_valid<=0;first_cold_inflight<=0;')
    text=warm.arithmetic.once(text,'if(cold_start_request)begin cold_reader<=1;',
        'if(cold_start_request)begin if(!anchor_valid)first_cold_inflight<=1;cold_reader<=1;')
    text=warm.arithmetic.once(text,'if(!anchor_valid)begin anchor_valid<=1;',
        'if(!anchor_valid)begin first_cold_inflight<=0;anchor_valid<=1;')
    return new,text


def prepare(n=32, p=8, *, contexts=2, allow_full_constants=False, ram_closure=1,
            corr_serial_bfs=0,mont_factored=0,cold_launch_fence=0,explicit_net_declarations=0,
            comm_tag_compact=0):
    if type(ram_closure) is not int or ram_closure not in (0,1):
        raise ValueError('S4_CONTEXT_HOST_RAM_CLOSURE_FLAG')
    if type(cold_launch_fence) is not int or cold_launch_fence not in (0,1):
        raise ValueError('S4_CONTEXT_COLD_LAUNCH_FENCE_FLAG')
    if type(explicit_net_declarations) is not int or explicit_net_declarations not in (0,1):
        raise ValueError('S4_CONTEXT_EXPLICIT_NET_DECLARATIONS_FLAG')
    if type(comm_tag_compact) is not int or comm_tag_compact not in (0,1):
        raise ValueError('S4_CONTEXT_COMM_TAG_COMPACT_FLAG')
    if comm_tag_compact and (p!=16 or corr_serial_bfs!=2 or mont_factored!=1 or
                            cold_launch_fence!=1 or explicit_net_declarations!=1):
        raise ValueError('S4_CONTEXT_COMM_TAG_COMPACT_REQUIRES_EXPLICIT_P16_DIET')
    if (corr_serial_bfs or mont_factored) and cold_launch_fence!=1:
        raise ValueError('S4_CONTEXT_DIET_REQUIRES_EXPLICIT_COLD_FENCE')
    b = warm.prepare(n, p, contexts=contexts, allow_full_constants=allow_full_constants,
                     corr_serial_bfs=corr_serial_bfs,mont_factored=mont_factored)
    plan=diet_calendar.schedule(n,p) if corr_serial_bfs else None
    if plan is not None:
        for key in ('rows','pointwise_accept','sink_accept','first_digit','carry_done','warm_interval',
                    'correction_cache_latency','feedback_delay','input_delay'):
            if plan['geometry'][key]!=b['geometry'][key]:raise ValueError('S4_CONTEXT_DIET_PORT_CALENDAR_JOIN:'+key)
    top, text = source(n, p, b['top'], b['geometry'],plan=plan)
    top,text=warm.arithmetic.diet_source(top,text,corr_serial_bfs,mont_factored)
    if cold_launch_fence:top,text=cold_fence_source(top,text)
    components=[SHADOW,CANONICAL,DESCRIPTOR]
    if ram_closure:
        new=top+'_closed_ram_v2';text=text.replace('module '+top+' #','module '+new+' #',1);top=new
        components.append(RAM)
    for path in components:
        b['files'][path.rsplit('/', 1)[1]] = (ROOT / path).read_text()
    b['files'][top+'.sv'] = text; b['top'] = top
    b['source_dependencies'] = list(dict.fromkeys(b['source_dependencies'] +
        [SELF, *components, 'reference/s4_two_context_model_v1.py']))
    b['source_sha256'] = {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in b['source_dependencies']}
    b['rtl_sources'] = [name for name in b['files'] if name.endswith('.sv')]
    b['generated_sha256'] = {name: hashlib.sha256(text.encode()).hexdigest() for name,text in b['files'].items()}
    b['host_contract'] = dict(api='Explicit two-context joint start mask, independent scalar host selector, per-context base/count/mask/initial c0/c1 and bounded4-entry descriptor FIFOs; frozen one-context ABI unchanged.',
        cold='Two E98 profile snapshots before balanced cold launch; RAM E0/source FF E1/arithmetic E2. Cold second correction outside all earlier PW root windows.',
        waiting='Dense naturalP-row raw capture into each unpublished context shadow; same storage later overwritten by ordered canonical scalar commits.',
        publication='Shared scratch final-only9N/10N; T-row load+drain, N actual acknowledged scalar copies, per-context ready/done only after last committed copy.',
        overlap='Distinct-context raw capture and canonical copy may coincide; a context waiting for scratch does not stall the other arithmetic chain.',
        range='Full32 feed counts; mask mode1..32; at most255 accepted jobs per context per reset to prevent full-owner generation reuse.',
        new_jobs='Joint batch admission only while both prior jobs are idle/published; busy host requests ignored. Completed-context reads allowed while its peer continues.',
        reset='RAM payload retained, all ownership/response/publication eligibility revoked; failed shared job requires reset and reload.')
    b['scope'] = 'Actual assembled two-context host RTL SOURCE only; no native readback, interleave performance, physical resource/clock or promotion claim until gates.'
    if cold_launch_fence:b['parameters']=dict(b['parameters'],COLD_LAUNCH_FENCE=1)
    if plan is not None:
        b['two_context_schedule']=plan
        b['source_dependencies']=list(dict.fromkeys(b['source_dependencies']+[diet_calendar.SELF]))
        b['source_sha256'][diet_calendar.SELF]=hashlib.sha256((ROOT/diet_calendar.SELF).read_bytes()).hexdigest()
    if explicit_net_declarations:
        from . import stream27_contexts_explicit_nets as declarations
        b=declarations.bind(b)
    if comm_tag_compact:
        from . import stream27_context_tagcompact_bind as tags
        b=tags.bind(b)
    return b
