// Joint two-context jobs, final-only canonical scratch, independent shadow publication.
module genefer_stream27_host_contexts_aw16_p16_protected_field100_v1 #(parameter int AW=16,P=16,CONTEXTS=2,CARRY_QUARANTINE_LOCAL=1,CANONICAL_FOLD_PAYLOAD_REG=1,C0_ADMISSION_DIRECT=1,AUTO_CORRECTION_INGRESS_REG=1,FEEDBACK_INGRESS_REG=1,DATAPATH_QUARANTINE_REG=1,FIELD_ERROR_REPORT_REG=1,FIELD_PROTOCOL_ORIGIN_FAST=1,CANONICAL_BEGIN_PAYLOAD_SPLIT=1,CANONICAL_PROFILE_SNAPSHOT=1,TERM_SELECT_TOKEN=1,CARRY_LOCALBASE=1,CANONICAL_LOCALBASE=1,FINAL_GS_INPUTREG=1,COLD_SECOND_ONESHOT=1,COMM_OWNER_COMPARE_LOCAL=1,CANONICAL_C0_DIRECT=1,ERROR_AGGREGATION_REGISTERED=1,CANONICAL_LOAD_LOCAL=1,CANONICAL_READ_LOCAL=1,QUARANTINE_REPLICAS=1,BOUNDARY_INPUTREG=1,EXPLICIT_NET_DECLARATIONS=1,COLD_LAUNCH_FENCE=1,CORR_SERIAL_BFS=2,MONT_FACTORED=1,COMM_STAGE_SHARED_MLAB=1,
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
 wire child_error_barrier,safety_error;
 wire canon_busy,canon_done,canon_error,canon_image_valid,canon_read_valid;
 localparam int N=1<<AW,ROW_W=AW-$clog2(P),ROWS=1<<ROW_W,K=2*N+24*P;
 localparam int MIN_PROOF=(2*K+2)/3+1,MIN_BASE=(2*N+5)>MIN_PROOF ? 2*N+5 : MIN_PROOF;
 localparam int CONTEXT_OFFSET=4230,SECOND_CORRECTION=8232;
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
 assign command_ready=job_feed[command_context] && command_state && !safety_error &&
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
  assign busy[c]=phase[c]!=IDLE && !safety_error;
  assign waiting_final[c]=phase[c]==RAW_READY && !safety_error;
 end
 logic setup_inflight,setup_context;
 wire begin_setup=!safety_error && !setup_inflight && (phase[0]==PROFILE || phase[1]==PROFILE);
 wire selected_setup_context=phase[0]!=PROFILE;
 wire [1:0] config_valid;wire setup_done,setup_done_context,child_error,child_pending;
 logic anchor_valid,anchor_context,first_cold_inflight;logic [31:0] anchor_cycle;
 logic second_correction_sent,second_correction_pending;
 wire all_profiles_ready=phase[0]!=PROFILE && phase[1]!=PROFILE;
 wire cold_pending=phase[0]==COLD_PENDING || phase[1]==COLD_PENDING;
 wire first_cold_context=phase[0]!=COLD_PENDING;
 logic cold_reader,cold_context;logic [ROW_W-1:0] cold_row;
 logic source_valid,source_context;logic [ROW_W-1:0] source_row;
 logic [P*32-1:0] source_data;
 wire cold_start_request=!cold_reader && all_profiles_ready && cold_pending &&
  ((!anchor_valid && !first_cold_inflight) || (anchor_valid && 32'(cycles[31:0]-anchor_cycle)==32'(CONTEXT_OFFSET-3)));
 wire selected_cold_context=anchor_valid ? !anchor_context : first_cold_context;
 wire source_start=source_valid && source_row==0;
  // Cold-only transaction: do not reissue when the low cycle counter wraps.
  // Pending retains a genuine due proposal until actual child acceptance.
  wire cold_second_due=anchor_valid && jobs[!anchor_context] &&
   32'(cycles[31:0]-anchor_cycle)==32'(SECOND_CORRECTION);
  wire cold_second_correction=anchor_valid && jobs[!anchor_context] &&
   !second_correction_sent && (second_correction_pending || cold_second_due);
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
 wire capture_fire=final_valid && !capture_bad && !safety_error;
 logic capture_req_d;
 logic publish_pending,publish_context;logic [55:0] publish_owner;
 logic canonical_owner,canonical_owned;logic [ROW_W-1:0] load_row;logic [ROW_W:0] load_requested;
 logic [AW:0] copy_requested,copy_issued,copy_committed;
 logic row_kind_d,row_context_d;logic [ROW_W-1:0] row_address_d;
 wire shadow_row_request=!safety_error && (cold_reader || (canonical_owned && phase[canonical_owner]==CANON_LOAD && load_requested<(ROW_W+1)'(ROWS)));
 wire shadow_row_context=cold_reader ? cold_context : canonical_owner;
 wire [ROW_W-1:0] shadow_row_address=cold_reader ? cold_row : load_row;
 wire shadow_row_valid,shadow_response_context,shadow_commit_ack,shadow_capture_ack,shadow_rejected;
 wire [55:0] shadow_response_owner;wire [P*32-1:0] shadow_row_data;
 wire shadow_scalar_valid,shadow_scalar_context;wire signed [95:0] shadow_scalar_data;wire [55:0] shadow_scalar_owner;
 wire response_bad=shadow_row_valid && (shadow_response_context!=row_context_d ||
  shadow_response_owner!=live_owner[row_context_d*56+:56]);
 wire canonical_load=shadow_row_valid && !row_kind_d && !response_bad && !safety_error;
 wire canonical_begin=canonical_owned && phase[canonical_owner]==CANON_WAIT && !canon_busy && !canon_image_valid && !safety_error;
 wire [7:0] canon_error_code;wire [63:0] canon_cycles;
 wire signed [95:0] canon_data;wire [AW-1:0] canon_address;
 wire canonical_read=canonical_owned && phase[canonical_owner]==COPY && copy_requested<(AW+1)'(N) && !safety_error;
 wire copy_bad=canon_read_valid && (copy_issued>=(AW+1)'(N) || canon_address!=copy_issued[AW-1:0] ||
  canon_data[95:32]!={64{canon_data[31]}});
 wire copy_fire=canon_read_valid && canonical_owned &&
  (phase[canonical_owner]==COPY || phase[canonical_owner]==COPY_DRAIN) && !copy_bad && !safety_error;
 assign error=local_error || child_error || canon_error;
 assign safety_error=local_error || child_error_barrier || canon_error;
 assign canonical_ready=published & {2{!safety_error}};assign done=done_q & {2{!safety_error}};
 assign read_valid=shadow_scalar_valid && canonical_ready[shadow_scalar_context] && !safety_error;
 assign read_context=shadow_scalar_context;assign read_owner=shadow_scalar_owner;assign read_data=shadow_scalar_data;
 assign completed_squares=child_completed;assign operations_started=child_started;assign warm_done=child_warm_done;
 assign canonical_cycles={context_canonical_cycles[1],context_canonical_cycles[0]};
 assign image_copy_cycles={context_copy_cycles[1],context_copy_cycles[0]};
 assign final_image_rows={32'(raw_rows[1]),32'(raw_rows[0])};
 genefer_stream27_host_image_rowwrite_v1 #(.AW(AW),.P(P),.CONTEXTS(2),.OWNER_W(56)) shadows (
  .clk,.rst_n,.quarantine(safety_error),.owner_enabled,.live_owner,
  .host_access(phase[host_context]==IDLE && !start_contexts[host_context] && !safety_error),
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
 logic canonical_config_valid;logic [31:0] canonical_config_base;
 logic [55:0] canonical_config_owner;
 wire canonical_config_bad=(canonical_load || canonical_begin || canonical_read || publish_pending) &&
  (!canonical_config_valid || canonical_config_owner!=live_owner[canonical_owner*56+:56]);
 genefer_stream27_canonical_image_foldpayload100_v1 #(.AW(AW),.P(P)) scratch (
  .clk,.rst_n,.load_valid(canonical_load),.load_row(row_address_d),.load_data(shadow_row_data),
  .begin_canonical(canonical_begin),.base(canonical_config_base),
  .c0(final_c0[canonical_owner]),.c1(final_c1[canonical_owner]),
  .read_req(canonical_read),.read_address(copy_requested[AW-1:0]),.busy(canon_busy),.done(canon_done),
  .error(canon_error),.image_valid(canon_image_valid),.error_code(canon_error_code),.cycles(canon_cycles),
  .read_valid(canon_read_valid),.read_address_out(canon_address),.read_data(canon_data));
 genefer_stream27_warm_contexts_aw16_p16_registered_error_v1_protected_field100_v1 #(.AW(AW),.P(P),.CONTEXTS(2)) engine (
  .clk,.rst_n,.begin_setup,.setup_context(selected_setup_context),
  .in_slot_valid(source_valid && !safety_error),.frame_start(source_start),.context_in(source_context),
  .correction_context(cold_correction_context),.double_in(job_double[source_context]),
  .context_enabled(jobs & {2{!safety_error}}),.live_generation({job_generation[1],job_generation[0]}),
  .generation_in(begin_setup ? job_generation[selected_setup_context] : job_generation[source_context]),
  .base_in(begin_setup ? job_base[selected_setup_context] : job_base[source_context]),
  .epoch_in(job_epoch[source_context]),.correction_epoch(job_epoch[cold_correction_context]),
  .correction_valid(cold_correction && !safety_error),.correction_generation(job_generation[cold_correction_context]),
  .data_in(source_data),.c0_in(cold_c0[cold_correction_context]),.c1_in(cold_c1[cold_correction_context]),
  .square_count(job_count[source_context]),.double_mask(job_mask[source_context]),.feed_mode(job_feed[source_context]),
  .command_valid({levels[1]!=0,levels[0]!=0}),.command_double(head_double),
  .command_index({head_index[1],head_index[0]}),.command_generation({head_generation[1],head_generation[0]}),
  .command_accept(feed_pop),.active(child_active),.warm_done(child_warm_done),.warm_cancelled(child_cancelled),
  .completed_frames(child_completed),.started_frames(child_started),.config_valid,.setup_done,.setup_done_context,
  .out_error(child_error),.fault_pending(child_pending),.error_barrier(child_error_barrier),.frame_accept(child_frame_accept),.correction_accept(child_correction_accept),
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
  always_ff @(posedge clk)if(shadow_row_valid && row_kind_d && !response_bad && !safety_error)
   source_data[32*lane+:32]<=shadow_row_data[32*NATURAL+:32];
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   local_error<=0;jobs<=0;job_feed<=0;job_double<=0;done_q<=0;published<=0;cycles<=0;
   publish_pending<=0;publish_context<=0;publish_owner<=0;
   setup_inflight<=0;setup_context<=0;anchor_valid<=0;anchor_context<=0;anchor_cycle<=0;first_cold_inflight<=0;
    second_correction_sent<=0;second_correction_pending<=0;
   cold_reader<=0;cold_context<=0;cold_row<=0;source_valid<=0;source_context<=0;source_row<=0;
   canonical_config_valid<=0;canonical_config_base<=2;canonical_config_owner<=0;
   canonical_owner<=0;canonical_owned<=0;load_row<=0;load_requested<=0;copy_requested<=0;copy_issued<=0;copy_committed<=0;
   row_kind_d<=0;row_context_d<=0;row_address_d<=0;capture_req_d<=0;
   next_epoch[0]<=16'(EPOCH_SEED0);next_epoch[1]<=16'(EPOCH_SEED1);
   for(int c=0;c<2;c=c+1)begin
    phase[c]<=IDLE;job_base[c]<=2;job_count[c]<=0;job_mask[c]<=0;next_index[c]<=1;
    job_generation[c]<=0;job_epoch[c]<=0;raw_rows[c]<=0;context_canonical_cycles[c]<=0;context_copy_cycles[c]<=0;
   end
  end else begin
   done_q<=0;source_valid<=shadow_row_valid && row_kind_d && !response_bad && !safety_error;
   capture_req_d<=capture_fire;
   if(canonical_config_bad)local_error<=1;
   if(safety_error)canonical_config_valid<=0;
   if(|busy)cycles<=cycles+64'd1;
   if(ingress_bad || capture_bad || response_bad || copy_bad || shadow_rejected ||
    (capture_req_d && !shadow_capture_ack) || (|child_cancelled))local_error<=1;
   if(shadow_row_request)begin row_kind_d<=cold_reader;row_context_d<=shadow_row_context;row_address_d<=shadow_row_address;end
   if(shadow_row_valid && row_kind_d && !response_bad)begin source_context<=row_context_d;source_row<=row_address_d;end
   if((|start_contexts) && !(|busy) && !canonical_owned && !safety_error)begin
    jobs<=start_contexts;cycles<=0;anchor_valid<=0;first_cold_inflight<=0;published<=published & ~start_contexts;
    publish_pending<=0;publish_context<=0;publish_owner<=0;canonical_config_valid<=0;
     second_correction_sent<=0;second_correction_pending<=0;
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
   if(cold_start_request)begin if(!anchor_valid)first_cold_inflight<=1;cold_reader<=1;cold_context<=selected_cold_context;cold_row<=0;phase[selected_cold_context]<=COLD_ACTIVE;end
   if(cold_reader && shadow_row_request)begin
    if(cold_row==ROW_W'(ROWS-1))cold_reader<=0;else cold_row<=cold_row+ROW_W'(1);
   end
   if(child_frame_accept && source_start)begin
    phase[source_context]<=RUN;
    if(!anchor_valid)begin first_cold_inflight<=0;anchor_valid<=1;anchor_context<=source_context;anchor_cycle<=cycles[31:0];end
   end
    if(cold_second_correction && !safety_error)begin
     if(child_correction_accept)begin second_correction_sent<=1;second_correction_pending<=0;end
     else second_correction_pending<=1;
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
   if(!canonical_owned && (phase[0]==RAW_READY || phase[1]==RAW_READY) && !safety_error)begin
    canonical_owner<=phase[0]!=RAW_READY;canonical_owned<=1;load_row<=0;load_requested<=0;
    canonical_config_valid<=1;canonical_config_base<=job_base[phase[0]!=RAW_READY];
    canonical_config_owner<=live_owner[(phase[0]!=RAW_READY)*56+:56];
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
   // Hold the scratch lease through one coherent publication fence edge.
   if(publish_pending)begin
    publish_pending<=0;
    if(!canonical_owned || canonical_owner!=publish_context || phase[publish_context]!=COPY_DRAIN ||
     publish_owner!=live_owner[publish_context*56+:56] || copy_requested!=(AW+1)'(N) ||
     copy_issued!=(AW+1)'(N) || copy_committed!=(AW+1)'(N) || shadow_commit_ack)local_error<=1;
    else if(!safety_error)begin
     published[publish_context]<=1;done_q[publish_context]<=1;phase[publish_context]<=IDLE;canonical_owned<=0;
     next_epoch[publish_context]<=job_epoch[publish_context]+16'(job_count[publish_context]);
    end
   end
   if(shadow_commit_ack && canonical_owned)begin
    copy_committed<=copy_committed+(AW+1)'(1);
    if(copy_committed==(AW+1)'(N-1))begin
     if(copy_issued!=(AW+1)'(N) || copy_requested!=(AW+1)'(N))local_error<=1;
     else begin
      publish_pending<=1;publish_context<=canonical_owner;
      publish_owner<=live_owner[canonical_owner*56+:56];
     end
    end
   end
  end
 end
 // synthesis translate_off
 initial if(AW!=16 || P!=16 || CONTEXTS!=2 || EXPLICIT_NET_DECLARATIONS!=1 || COLD_LAUNCH_FENCE!=1 || CORR_SERIAL_BFS!=2 || MONT_FACTORED!=1 || COMM_STAGE_SHARED_MLAB!=1 || EPOCH_SEED0>32'd65535 || EPOCH_SEED1>32'd65535)
  $fatal(1,"S4_CONTEXT_HOST_EXPLICIT_GEOMETRY");
 always @(posedge clk)if(rst_n && !safety_error)begin
  if(capture_fire && copy_fire && final_context==canonical_owner)$fatal(1,"S4_CONTEXT_CAPTURE_COPY_ALIAS");
  if((|done) && (!(&((~done)|canonical_ready))))$fatal(1,"S4_CONTEXT_DONE_PUBLICATION");
 end
 // synthesis translate_on
endmodule
