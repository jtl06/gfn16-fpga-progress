// Same scalar digit/readback contract; explicit finite batch extension.
// Host done includes real canonicalization AND copying every signed32 word.
module genefer_stream27_host_chain_aw5_p16_diet_qualification_v1 #(parameter int CORR_SERIAL_BFS=2,COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1,parameter int CANONICAL_PIPE_STAGES=1,parameter int unsigned EPOCH_SEED=0,parameter int AW=5,P=16,CONTEXTS=1) (
 input logic clk,rst_n,load_we,read_en,start,
 input logic [AW-1:0] host_addr,input logic signed [31:0] write_data,
 input logic [31:0] base,input logic double_bit,
 input logic batch_mode,input logic [31:0] warm_count,double_mask,
 output logic read_valid,output logic signed [95:0] read_data,
 output logic busy,done,error,
 output logic [63:0] cycles,conversion_cycles,root_cycles,ntt_cycles,crt_cycles,carry_cycles,
 output logic [6:0] carry_passes,output logic profile_cache_valid,profile_loads,profile_hits,
 output logic [15:0] profile_words_loaded,output logic [63:0] seed_setup_cycles,
 output logic warm_done,output logic [31:0] completed_squares,
 output logic [63:0] canonical_cycles,image_copy_cycles,
 input logic feed_mode,command_valid,command_double,
 input logic [31:0] command_index,input logic [7:0] command_generation,
 output logic command_ready,command_accept,operation_accept,
 output logic [7:0] accepted_generation,output logic [2:0] feed_level,
 output logic [31:0] operations_started,commands_enqueued,commands_consumed,final_image_rows,
 output logic [3:0] feed_error_code,
 output logic canonical_ready);
 localparam int N=1<<AW,ROW_W=AW-4,ROWS=1<<ROW_W,K=2*N+384;
 localparam int MIN_PROOF=(2*K+2)/3+1,MIN_BASE=(2*N+5)>MIN_PROOF ? (2*N+5) : MIN_PROOF;
 typedef enum logic [3:0] {IDLE,SETUP,WAIT_SETUP,COLD,WARM,CANON_WAIT,COPY,COPY_DRAIN,FAILED} state_t;
 state_t state;
 logic [31:0] job_base,job_count,job_mask,cache_base;logic job_double;
 logic [7:0] job_generation;
 logic job_feed,first_operation_seen;
 logic [1:0] feed_read,feed_write;logic [2:0] feed_count;
 logic [31:0] feed_index[0:3],next_write_index;
 logic [7:0] feed_generation[0:3];logic feed_double[0:3];
 wire feed_pop,cold_accept,final_load_valid;wire [31:0] child_started,final_load_sequence;
 wire [3:0] child_feed_error;
 wire feed_state=state==SETUP || state==WAIT_SETUP || state==COLD || state==WARM;
 assign command_ready=job_feed && feed_state && !error && (feed_count<3'd4 || feed_pop);
 wire ingress_bad=command_valid && command_ready &&
  (command_generation!=job_generation || command_index!=next_write_index || command_index==0 || command_index>=job_count);
 wire feed_push=command_valid && command_ready && !ingress_bad;
 assign command_accept=feed_push;assign operation_accept=feed_pop;
 assign accepted_generation=job_generation;assign feed_level=feed_count;
 assign operations_started=first_operation_seen ? child_started : 32'd0;logic image_published;logic [15:0] job_epoch,next_cold_epoch;
 logic [ROW_W-1:0] cold_row,request_row_d,source_row;
 logic source_valid;logic [P*32-1:0] source_data;
 logic [AW:0] copy_requested,copy_committed;
 wire setup_done,config_valid,child_error,child_pending,child_done,child_busy,child_cancelled;
 wire child_read_valid,child_ready,child_warm_done;
 wire signed [95:0] child_read_data;wire [AW-1:0] child_read_address;
 wire [63:0] child_canonical_cycles;
 wire row_read_valid,scalar_read_valid;wire signed [95:0] scalar_read_data;
 wire [P*32-1:0] row_read_data;
 wire row_request=(state==COLD) && !error;
 wire source_start=source_valid && source_row==0;
 wire read_request=(state==COPY) && copy_requested<(AW+1)'(N) && !error;
 wire copy_bad=(state==COPY && child_read_valid) &&
  (copy_committed>=(AW+1)'(N) || child_read_address!=copy_committed[AW-1:0] ||
   child_read_data[95:32]!={64{child_read_data[31]}});
 wire copy_fire=(state==COPY) && child_read_valid && !copy_bad && !error && !child_error;
 wire completion_bad=(state==COPY_DRAIN || (state==CANON_WAIT && child_done)) && completed_squares!=job_count;
 wire request_bad=state==IDLE && start &&
  (base<32'(MIN_BASE) || base>32'd1000000000 || (batch_mode && (warm_count==0 || (!feed_mode && warm_count>32'd32))));
 assign busy=state!=IDLE && state!=FAILED;
 assign read_valid=scalar_read_valid && !busy && !error;
 assign read_data=scalar_read_data;
 assign profile_cache_valid=config_valid && !error;
 assign profile_words_loaded=0; // Static compiled roots, not runtime T5b root-bundle loads.
 assign crt_cycles=0; // CRT overlaps streaming NTT/carry; no double-counted phase sum.
 assign seed_setup_cycles=root_cycles;
 assign canonical_cycles=child_canonical_cycles;
 assign warm_done=child_warm_done && !error;
 assign canonical_ready=state==IDLE && image_published && child_ready && !error;
 genefer_stream27_host_image_ports_v1 #(.AW(AW),.P(P),.ROW_W(ROW_W)) host_image (
  .clk,.rst_n,.host_access(state==IDLE && !start && !error),.load_we,.read_en,.host_addr,.write_data,
  .row_read_req(row_request),.row_read_address(cold_row),
  .commit_we(copy_fire),.commit_address(child_read_address),.commit_word(child_read_data[31:0]),
  .read_valid(scalar_read_valid),.read_data(scalar_read_data),.row_read_valid,.row_read_data);
 // The actual synchronous row RAM q at E0 crosses one source FF at E1;
 // the common field accepts at E2. Natural block -> physical reverse4 is static.
 for(genvar lane=0;lane<P;lane=lane+1)begin: cold_route
  localparam int NATURAL=((lane&1)<<3)|((lane&2)<<1)|((lane&4)>>1)|((lane&8)>>3);
  always_ff @(posedge clk)if(row_read_valid)source_data[32*lane+:32]<=row_read_data[32*NATURAL+:32];
 end
 genefer_stream27_chain_canonical_aw5_p16_v1 #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) engine (
  .clk,.rst_n,.begin_setup(state==SETUP && !error),.in_slot_valid(source_valid && !error),
  .frame_start(source_start),.context_enabled(!error),.double_in(job_double),
  .generation_in(job_generation),.live_generation(job_generation),.base_in(job_base),
  .epoch_in(job_epoch),.correction_epoch(job_epoch),.correction_valid(source_start && !error),
  .correction_generation(job_generation),.data_in(source_data),.c0_in({(P*32){1'b0}}),.c1_in({(P*32){1'b0}}),
  .square_count(job_count),.double_mask(job_mask),.config_valid,.setup_done,
  .feed_mode(job_feed),.command_valid(feed_count!=0),.command_double(feed_double[feed_read]),
  .command_index(feed_index[feed_read]),.command_generation(feed_generation[feed_read]),
  .command_accept(feed_pop),.started_frames(child_started),.chain_error_code(child_feed_error),
  .digit_sequence(),.boundary_sequence(),.final_load_valid,.final_load_sequence,
  .out_error(child_error),.fault_pending(child_pending),.frame_accept(cold_accept),.correction_accept(),
  .internal_frame_accept(),.internal_correction_accept(),.active(),.warm_done(child_warm_done),
  .warm_cancelled(),.completed_frames(completed_squares),
  .coefficient_valid(),.coefficient_start(),.coefficient_data(),.coefficient_row(),
  .digit_valid(),.digit_start(),.digit_eligible(),.digit_data(),.digit_row(),.digit_epoch(),.digit_generation(),
  .boundary_valid(),.boundary_eligible(),.next_c0(),.next_c1(),.next_epoch(),.next_generation(),.frame_done(),.done_epoch(),
  .read_req(read_request),.read_address(copy_requested[AW-1:0]),.busy(child_busy),.done(child_done),
  .cancelled(child_cancelled),.canonical_ready(child_ready),.read_valid(child_read_valid),
  .read_address_out(child_read_address),.read_data(child_read_data),.canonical_cycles(child_canonical_cycles));
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   state<=IDLE;done<=0;error<=0;image_published<=0;job_base<=0;job_count<=0;job_mask<=0;job_double<=0;cache_base<=0;job_generation<=0;
   job_feed<=0;first_operation_seen<=0;feed_read<=0;feed_write<=0;feed_count<=0;next_write_index<=1;
   commands_enqueued<=0;commands_consumed<=0;final_image_rows<=0;feed_error_code<=0;job_epoch<=16'(EPOCH_SEED);next_cold_epoch<=16'(EPOCH_SEED);
   cold_row<=0;request_row_d<=0;source_row<=0;source_valid<=0;copy_requested<=0;copy_committed<=0;
   cycles<=0;conversion_cycles<=0;root_cycles<=0;ntt_cycles<=0;carry_cycles<=0;carry_passes<=0;
   profile_loads<=0;profile_hits<=0;image_copy_cycles<=0;
  end else begin
   done<=0;source_valid<=row_read_valid && !error;
   if(cold_accept)first_operation_seen<=1;
   if(final_load_valid)final_image_rows<=final_image_rows+32'd1;
   if(feed_push)begin
    feed_index[feed_write]<=command_index;feed_generation[feed_write]<=command_generation;feed_double[feed_write]<=command_double;
    feed_write<=feed_write+2'd1;next_write_index<=next_write_index+32'd1;commands_enqueued<=commands_enqueued+32'd1;
   end
   if(feed_pop)begin feed_read<=feed_read+2'd1;commands_consumed<=commands_consumed+32'd1;end
   case({feed_push,feed_pop})
    2'b10:feed_count<=feed_count+3'd1;
    2'b01:feed_count<=feed_count-3'd1;
    default:begin end
   endcase
   if(feed_error_code==0)begin
    if(ingress_bad)feed_error_code<=command_generation!=job_generation ? 4'd2 :
     ((command_index==0 || command_index>=job_count) ? 4'd4 : 4'd3);
    else if(child_feed_error!=0)feed_error_code<=child_feed_error;
   end
   if(state==IDLE && !start && load_we && !error)image_published<=0;
   if(row_request)request_row_d<=cold_row;
   if(row_read_valid)source_row<=request_row_d;
   if(busy)begin
    cycles<=cycles+64'd1;
    if(state==SETUP || state==WAIT_SETUP)root_cycles<=root_cycles+64'd1;
    if(state==COLD)conversion_cycles<=conversion_cycles+64'd1;
    if(state==WARM)ntt_cycles<=ntt_cycles+64'd1;
    if(state==CANON_WAIT || state==COPY || state==COPY_DRAIN)carry_cycles<=carry_cycles+64'd1;
    if(state==COPY || state==COPY_DRAIN)image_copy_cycles<=image_copy_cycles+64'd1;
   end
   case(state)
    IDLE:if(start)begin
     image_published<=0;job_base<=base;job_double<=double_bit;job_count<=batch_mode ? warm_count : 32'd1;
     job_mask<=batch_mode ? double_mask : 32'd0;
     job_feed<=batch_mode && feed_mode;first_operation_seen<=0;
     feed_read<=0;feed_write<=0;feed_count<=0;next_write_index<=1;
     commands_enqueued<=0;commands_consumed<=0;final_image_rows<=0;feed_error_code<=0;job_generation<=job_generation+8'd1;job_epoch<=next_cold_epoch;
     cycles<=0;conversion_cycles<=0;root_cycles<=0;ntt_cycles<=0;carry_cycles<=0;carry_passes<=0;image_copy_cycles<=0;
     cold_row<=0;copy_requested<=0;copy_committed<=0;profile_loads<=0;profile_hits<=0;
     if(config_valid && cache_base==base)begin state<=COLD;profile_hits<=1;end
     else begin state<=SETUP;profile_loads<=1;end
    end
    SETUP:state<=WAIT_SETUP;
    WAIT_SETUP:if(setup_done && config_valid && !child_error)begin cache_base<=job_base;state<=COLD;end
    COLD:if(row_request)begin
     if(cold_row==ROW_W'(ROWS-1))state<=WARM;else cold_row<=cold_row+ROW_W'(1);
    end
    WARM:if(child_warm_done)state<=CANON_WAIT;
    CANON_WAIT:if(child_done && child_ready && !child_cancelled)begin
     state<=COPY;copy_requested<=0;copy_committed<=0;
     carry_passes<=child_canonical_cycles==64'(7*N) ? 7'd4 : 7'd3;
    end
    COPY:begin
     if(read_request)copy_requested<=copy_requested+(AW+1)'(1);
     if(copy_fire)begin
      copy_committed<=copy_committed+(AW+1)'(1);
      if(copy_committed==(AW+1)'(N-1))state<=COPY_DRAIN;
     end
    end
    COPY_DRAIN:begin state<=IDLE;done<=1;image_published<=1;next_cold_epoch<=job_epoch+16'(job_count);end
    FAILED:begin end
    default:begin state<=FAILED;error<=1;done<=1;end
   endcase
   // Fault notification is a legacy done+error event, not canonical SUCCESS.
   // The frozen barrier itself never fabricates successful done on a fault.
   if(!error && (request_bad || child_error || copy_bad || child_cancelled || completion_bad || ingress_bad))begin
    state<=FAILED;error<=1;done<=1;source_valid<=0;image_published<=0;
   end
  end
 end
 // synthesis translate_off
 initial if(EPOCH_SEED>32'd65535 || AW!=5 || P!=16 || CONTEXTS!=1)$fatal(1,"S4_HOST_CORE_GEOMETRY");
 always @(posedge clk)if(rst_n && done && !error)begin
  if(busy || !canonical_ready || copy_committed!=(AW+1)'(N))$fatal(1,"S4_HOST_DONE_BEFORE_COPIED_IMAGE");
  if(final_image_rows!=32'(ROWS))$fatal(1,"S4_LONG_TRUE_LAST_IMAGE_ROW_COUNT");
  if(job_feed && (commands_enqueued!=job_count-32'd1 || commands_consumed!=job_count-32'd1 || feed_count!=0))$fatal(1,"S4_LONG_DONE_COMMAND_ACCOUNTING");
  if(cycles!=root_cycles+conversion_cycles+ntt_cycles+carry_cycles)$fatal(1,"S4_HOST_PHASE_ACCOUNTING");
 end
 always @(posedge clk)if(rst_n && !error)begin
  if(feed_count>3'd4 || (feed_pop && feed_count==0))$fatal(1,"S4_LONG_FIFO_ELIGIBILITY");
  if(final_load_valid && final_load_sequence!=job_count-32'd1)$fatal(1,"S4_LONG_PREMATURE_FINAL_IMAGE");
 end
 // synthesis translate_on
 // synthesis translate_off
 initial if(CORR_SERIAL_BFS!=2 || COMM_STAGE_SHARED_MLAB!=1 || MONT_FACTORED!=1 || CANONICAL_PIPE_STAGES!=1)$fatal(1,"S4_CANONICAL_PIPE_BUILD_FLAG");
 // synthesis translate_on
endmodule
