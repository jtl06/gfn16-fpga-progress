// Isolated two-context lease extension. Frozen epoch_protocol_v5 is unchanged.
// Full tuples are carried payloads; calendar lookup independently checks gaps.
module genefer_stream27_epoch_protocol_contexts_v1_payload_lookahead_v1 #(
 parameter int unsigned ROWS=8192,POINTWISE_FIRST=8308,SINK_FIRST=16618,
 parameter int unsigned EPOCH_W=16,CONTEXTS=1,BANKS=2
) (
 input logic clk,rst_n,quarantine,external_fault_pending,
 input logic frame_begin,frame_context,
 input logic [EPOCH_W-1:0] frame_epoch,
 input logic [7:0] frame_generation,
 input logic [31:0] frame_base,
 input logic correction_valid,correction_context,
 input logic [EPOCH_W-1:0] correction_epoch,
 input logic [7:0] correction_generation,
 input logic cache_ready,cache_context,
 input logic [EPOCH_W-1:0] cache_epoch,
 input logic [7:0] cache_generation,
 input logic pointwise_slot,pointwise_frame_start,pointwise_context,
 input logic [EPOCH_W-1:0] pointwise_epoch_in,
 input logic [7:0] pointwise_generation,
 input logic sink_slot,sink_frame_start,sink_context,
 input logic [EPOCH_W-1:0] sink_epoch_in,
 input logic [7:0] sink_generation,
 input logic [CONTEXTS-1:0] context_enabled,
 input logic [CONTEXTS*8-1:0] live_generation,
 output logic frame_accept,correction_accept,
 output logic [31:0] correction_base,
 output logic pointwise_accept,commit_enable,
 output logic [EPOCH_W-1:0] pointwise_epoch,sink_epoch,
 output logic [$clog2(ROWS)-1:0] pointwise_row,sink_row,
 output logic [1:0] correction_bank,pointwise_bank,sink_bank,
 output logic [$clog2(BANKS+1)-1:0] owner_count,
 output logic out_error,fault_pending,
 output logic [26:0] pointwise_payload_owner_next,
 output logic [$clog2(ROWS)-1:0] pointwise_payload_row_next
);
 localparam int ROW_W=$clog2(ROWS),BANK_W=$clog2(BANKS),OWNER_W=$clog2(BANKS+1);
 logic [BANKS-1:0] valid,received,ready,owner;
 logic [EPOCH_W-1:0] epoch[0:BANKS-1];
 logic [7:0] generation[0:BANKS-1];
 logic [31:0] base[0:BANKS-1],pw_first[0:BANKS-1],sink_first[0:BANKS-1];
 logic [31:0] pw_age[0:BANKS-1],sink_age[0:BANKS-1],cycle_count;
 logic [CONTEXTS-1:0] sequence_initialized;
 logic [EPOCH_W-1:0] next_epoch[0:CONTEXTS-1],next_completed[0:CONTEXTS-1];
 logic bad,free_found,frame_owner_exists,corr_found,cache_found,pw_found,sink_found;
 logic [BANK_W-1:0] free_index,corr_index,cache_index,pw_index,sink_index;
 logic [BANKS-1:0] corr_matches,cache_matches,pw_matches,sink_matches;
 logic corr_multiple,cache_multiple,pw_multiple,sink_multiple;
 logic frame_context_valid,pw_tuple_ok,sink_tuple_ok,sink_order_ok;
 logic [7:0] sink_live_generation;
 logic sink_enabled;
 wire stop=quarantine || out_error;
 // These indices never address outside a CONTEXTS=1 instance.
 wire frame_ci=(CONTEXTS==2) && frame_context;
 wire sink_ci=(CONTEXTS==2) && owner[sink_index];
 assign frame_context_valid=(CONTEXTS==2) || !frame_context;
 assign corr_multiple=(corr_matches & (corr_matches-BANKS'(1)))!='0;
 assign cache_multiple=(cache_matches & (cache_matches-BANKS'(1)))!='0;
 assign pw_multiple=(pw_matches & (pw_matches-BANKS'(1)))!='0;
 assign sink_multiple=(sink_matches & (sink_matches-BANKS'(1)))!='0;
 always_comb begin
  owner_count='0;
  for(int i=0;i<BANKS;i=i+1)owner_count=owner_count+OWNER_W'(valid[i]);
 end
 // Data-only next-edge lookup; not used by accept/pending/commit logic.
 logic [31:0] payload_age_next[0:BANKS-1];
 always_comb begin
  pointwise_payload_owner_next='0;pointwise_payload_row_next='0;
  for(int i=0;i<BANKS;i=i+1)begin
   payload_age_next[i]=(cycle_count+32'd1)-pw_first[i];
   if(valid[i] && payload_age_next[i]<32'(ROWS))begin
    pointwise_payload_owner_next={2'(i),owner[i],epoch[i],generation[i]};
    pointwise_payload_row_next=ROW_W'(payload_age_next[i]);
   end
  end
 end
 // synthesis translate_off
 initial if(EPOCH_W!=16 || POINTWISE_FIRST<=1 || SINK_FIRST<POINTWISE_FIRST+ROWS)
  $fatal(1,"C2_LOOKAHEAD_NONOVERLAP_GEOMETRY");
 // synthesis translate_on
 // Pure lookup: no accept/fault signal can feed prospective base selection.
 always_comb begin: lookup_values
  free_found=0;free_index='0;frame_owner_exists=0;
  corr_found=0;corr_index='0;cache_found=0;cache_index='0;
  pw_found=0;pw_index='0;sink_found=0;sink_index='0;
  corr_matches='0;cache_matches='0;pw_matches='0;sink_matches='0;
  correction_base='0;pointwise_epoch='0;sink_epoch='0;pointwise_row='0;sink_row='0;
  for(int i=0;i<BANKS;i=i+1)begin
   pw_age[i]=cycle_count-pw_first[i];sink_age[i]=cycle_count-sink_first[i];
   if(!valid[i] && !free_found)begin free_found=1;free_index=BANK_W'(i);end
   if(valid[i])begin
    if(frame_begin && frame_context==owner[i] && frame_epoch==epoch[i])frame_owner_exists=1;
    if(correction_valid && correction_context==owner[i] && correction_epoch==epoch[i] && correction_generation==generation[i])begin
     corr_matches[i]=1;corr_found=1;corr_index=BANK_W'(i);correction_base=base[i];
    end
    if(cache_ready && cache_context==owner[i] && cache_epoch==epoch[i] && cache_generation==generation[i])begin
     cache_matches[i]=1;cache_found=1;cache_index=BANK_W'(i);
    end
    if(pw_age[i]<32'(ROWS))begin
     pw_matches[i]=1;pw_found=1;pw_index=BANK_W'(i);pointwise_epoch=epoch[i];pointwise_row=ROW_W'(pw_age[i]);
    end
    if(sink_age[i]<32'(ROWS))begin
     sink_matches[i]=1;sink_found=1;sink_index=BANK_W'(i);sink_epoch=epoch[i];sink_row=ROW_W'(sink_age[i]);
    end
   end
  end
  if(correction_valid && !corr_found && frame_begin && free_found && frame_context_valid &&
   correction_context==frame_context && correction_epoch==frame_epoch && correction_generation==frame_generation)begin
   corr_found=1;corr_index=free_index;correction_base=frame_base;
  end
 end
 assign correction_bank=2'(corr_index);
 assign pointwise_bank=2'(pw_index);
 assign sink_bank=2'(sink_index);
 assign pw_tuple_ok=pointwise_context==owner[pw_index] && pointwise_epoch_in==epoch[pw_index] && pointwise_generation==generation[pw_index];
 assign sink_tuple_ok=sink_context==owner[sink_index] && sink_epoch_in==epoch[sink_index] && sink_generation==generation[sink_index];
 assign sink_order_ok=sequence_initialized[sink_ci] && sink_epoch==next_completed[sink_ci];
 assign sink_live_generation=8'(live_generation>>(sink_ci*8));
 assign sink_enabled=context_enabled[sink_ci];
 always_comb begin: protocol_checks
  bad=0;
  for(int i=0;i<BANKS;i=i+1)if(valid[i])begin
   if(corr_matches[i] && received[i])bad=1;
   if(cache_matches[i] && (!received[i] || ready[i]))bad=1;
   if(pw_matches[i] && pointwise_slot && (!ready[i] ||
    pointwise_context!=owner[i] || pointwise_epoch_in!=epoch[i] || pointwise_generation!=generation[i] ||
    pointwise_frame_start!=(pw_age[i]==0)))bad=1;
   if(sink_matches[i] && sink_slot &&
    (sink_context!=owner[i] || sink_epoch_in!=epoch[i] || sink_generation!=generation[i] ||
     sink_frame_start!=(sink_age[i]==0) || !sink_order_ok))bad=1;
   if(frame_begin && frame_context==owner[i] && frame_epoch==epoch[i])bad=1;
  end
  if(frame_begin && (!frame_context_valid || !free_found ||
    (sequence_initialized[frame_ci] && frame_epoch!=next_epoch[frame_ci])))bad=1;
  if(correction_valid && !corr_found)bad=1;
  if(cache_ready && !cache_found)bad=1;
  if(corr_multiple || cache_multiple || pw_multiple || sink_multiple)bad=1;
  if(pointwise_slot!=pw_found || sink_slot!=sink_found)bad=1;
  if(!pointwise_slot && pointwise_frame_start)bad=1;
  if(!sink_slot && sink_frame_start)bad=1;
 end
 assign fault_pending=out_error || (!stop && (bad || external_fault_pending));
 assign frame_accept=rst_n && frame_begin && frame_context_valid && free_found && !frame_owner_exists && !stop &&
  (!sequence_initialized[frame_ci] || frame_epoch==next_epoch[frame_ci]);
 assign correction_accept=rst_n && correction_valid && corr_found && !stop &&
  ((valid[corr_index] && !received[corr_index]) || (!valid[corr_index] && frame_accept));
 assign pointwise_accept=rst_n && pointwise_slot && pw_found && !pw_multiple && !stop && ready[pw_index] &&
  pw_tuple_ok && pointwise_frame_start==(pw_age[pw_index]==0);
 assign commit_enable=rst_n && sink_slot && sink_found && !sink_multiple && sink_enabled && !stop &&
  sink_tuple_ok && sink_order_ok && sink_generation==sink_live_generation && sink_frame_start==(sink_age[sink_index]==0);
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   valid<='0;received<='0;ready<='0;cycle_count<='0;sequence_initialized<='0;out_error<=0;
  end else begin
   cycle_count<=cycle_count+32'd1;
   if(!stop && (bad || external_fault_pending))out_error<=1;
   if(!stop)begin
    if(frame_accept)begin
     valid[free_index]<=1;received[free_index]<=0;ready[free_index]<=0;owner[free_index]<=frame_context;
     epoch[free_index]<=frame_epoch;generation[free_index]<=frame_generation;base[free_index]<=frame_base;
     pw_first[free_index]<=cycle_count+32'(POINTWISE_FIRST);sink_first[free_index]<=cycle_count+32'(SINK_FIRST);
     next_epoch[frame_ci]<=frame_epoch+EPOCH_W'(1);
     if(!sequence_initialized[frame_ci])next_completed[frame_ci]<=frame_epoch;
     sequence_initialized[frame_ci]<=1;
    end
    if(correction_accept)received[corr_index]<=1;
    if(cache_ready && cache_found && received[cache_index] && !ready[cache_index])ready[cache_index]<=1;
    // Retirement observes raw occupancy, not live-generation commit eligibility.
    if(sink_slot && sink_found && !sink_multiple && sink_tuple_ok && sink_order_ok &&
     sink_frame_start==(sink_age[sink_index]==0) && sink_row==ROW_W'(ROWS-1))begin
     valid[sink_index]<=0;received[sink_index]<=0;ready[sink_index]<=0;
     next_completed[sink_ci]<=sink_epoch+EPOCH_W'(1);
    end
   end
  end
 end
 // synthesis translate_off
 initial if(ROWS<2 || (ROWS&(ROWS-1))!=0 || POINTWISE_FIRST<1 || SINK_FIRST<=POINTWISE_FIRST ||
  EPOCH_W<2 || EPOCH_W>24 || !((CONTEXTS==1 && BANKS==2)||(CONTEXTS==2 && BANKS==4)))
  $fatal(1,"EPOCH_CONTEXTS_PARAMETERS");
 // synthesis translate_on
endmodule
