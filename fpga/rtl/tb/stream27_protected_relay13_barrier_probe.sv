// Native-only observation shell. Production sources remain retained verbatim;
// the private diagnostic clones add raw predicate ORs, not barrier/FF forces.
@HEADER@
@CANDIDATE@
 assign probe_barrier=candidate.safety_error;
 assign probe_child_barrier=candidate.child_error_barrier;
 assign probe_local_q=candidate.engine.arithmetic.local_fault_q;
 assign probe_field_q={candidate.engine.arithmetic.field2.out_error_fast,
                       candidate.engine.arithmetic.field1.out_error_fast,
                       candidate.engine.arithmetic.field0.out_error_fast};
 assign probe_field_report={candidate.engine.arithmetic.field2.controller_error,candidate.engine.arithmetic.field1.controller_error,candidate.engine.arithmetic.field0.controller_error};
 assign probe_field_stop={candidate.engine.arithmetic.field2.stop,candidate.engine.arithmetic.field1.stop,candidate.engine.arithmetic.field0.stop};
 assign probe_field_copies={candidate.engine.arithmetic.field2.transform_quarantine,candidate.engine.arithmetic.field1.transform_quarantine,candidate.engine.arithmetic.field0.transform_quarantine};
 assign probe_arith_report=candidate.engine.arithmetic.out_error;
 // Low three bits are forward, next three matched term, high three inverse.
 // Full25 generation and data remain unreset/private; only valid/start
 // authority is required to clear on the real asynchronous reset.
 assign probe_relay_slots={candidate.engine.arithmetic.field2.inverse_slot_q,
  candidate.engine.arithmetic.field1.inverse_slot_q,candidate.engine.arithmetic.field0.inverse_slot_q,
  candidate.engine.arithmetic.field2.pair_slot_q,candidate.engine.arithmetic.field1.pair_slot_q,
  candidate.engine.arithmetic.field0.pair_slot_q,candidate.engine.arithmetic.field2.forward_slot_q,
  candidate.engine.arithmetic.field1.forward_slot_q,candidate.engine.arithmetic.field0.forward_slot_q};
 assign probe_relay_starts={candidate.engine.arithmetic.field2.inverse_start_q,
  candidate.engine.arithmetic.field1.inverse_start_q,candidate.engine.arithmetic.field0.inverse_start_q,
  candidate.engine.arithmetic.field2.pair_start_q,candidate.engine.arithmetic.field1.pair_start_q,
  candidate.engine.arithmetic.field0.pair_start_q,candidate.engine.arithmetic.field2.forward_start_q,
  candidate.engine.arithmetic.field1.forward_start_q,candidate.engine.arithmetic.field0.forward_start_q};
 assign probe_proposal=candidate.shadow_commit_ack && candidate.canonical_owned &&
                       candidate.copy_committed==(AW+1)'((1<<AW)-1);
 assign probe_pending=candidate.publish_pending;
 assign probe_private_ready=candidate.published;
 assign probe_private_done=candidate.done_q;
 assign probe_owned=candidate.canonical_owned;
 assign probe_publish_owner=candidate.publish_owner;
 assign probe_live_owner=candidate.live_owner[candidate.canonical_owner*56+:56];
 assign probe_publish_context=candidate.publish_context;
 assign probe_canonical_owner=candidate.canonical_owner;
 assign probe_counts={candidate.copy_requested,candidate.copy_issued,candidate.copy_committed};
 assign probe_host_controls={candidate.capture_fire,candidate.copy_fire,candidate.canonical_load,
   candidate.canonical_begin,candidate.canonical_read,candidate.shadow_row_request,
   candidate.child_frame_accept,candidate.child_correction_accept};
 assign probe_arith_controls={candidate.engine.arithmetic.coefficient_valid,
   candidate.engine.arithmetic.digit_valid,candidate.engine.arithmetic.boundary_valid,
   candidate.engine.arithmetic.frame_done};
 assign probe_newjob=start_contexts!=0 && busy==0 && !candidate.canonical_owned && !candidate.safety_error;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin probe_proposals<=0;probe_drains<=0;end
  else begin
   if(probe_proposal)probe_proposals<=probe_proposals+32'd1;
   if(probe_pending)probe_drains<=probe_drains+32'd1;
  end
 end
endmodule
