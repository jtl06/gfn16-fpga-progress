// Native-only dual twin: actual OFF parent and actual ON branch.
// All observations are passive; no payload, owner or authority substitution.
@HEADER@
@TWINS@
 assign dbg_setup_done=twin.protected_parent.candidate.setup_done;
 assign dbg_setup_context=twin.protected_parent.candidate.setup_done_context;
 assign dbg_config_valid=twin.protected_parent.candidate.config_valid;
 assign dbg_base={twin.protected_parent.candidate.engine.arithmetic.profile_base[1],twin.protected_parent.candidate.engine.arithmetic.profile_base[0]};
 assign dbg_reciprocal={twin.protected_parent.candidate.engine.arithmetic.profile_reciprocal[1],twin.protected_parent.candidate.engine.arithmetic.profile_reciprocal[0]};
 assign dbg_limit={twin.protected_parent.candidate.engine.arithmetic.profile_limit[1],twin.protected_parent.candidate.engine.arithmetic.profile_limit[0]};
 assign dbg_generation={twin.protected_parent.candidate.engine.arithmetic.profile_generation[1],twin.protected_parent.candidate.engine.arithmetic.profile_generation[0]};
 assign eq_twin_raw_valid=twin.protected_parent.candidate.final_valid;
 assign eq_twin_capture=twin.protected_parent.candidate.capture_fire;
 assign eq_twin_context=twin.protected_parent.candidate.final_context;
 assign eq_twin_row=twin.protected_parent.candidate.digit_row;
 assign eq_twin_data=twin.protected_parent.candidate.digit_data;
 assign eq_twin_owner=twin.protected_parent.candidate.final_owner;
 assign eq_twin_live=twin.protected_parent.candidate.live_owner[eq_twin_context*56+:56];
 assign eq_twin_boundary=twin.protected_parent.candidate.final_boundary_valid;
 assign eq_twin_boundary_context=twin.protected_parent.candidate.boundary_context;
 assign eq_twin_boundary_owner={twin.protected_parent.candidate.boundary_sequence,
  16'(twin.protected_parent.candidate.boundary_epoch-16'd1),
  twin.protected_parent.candidate.boundary_generation};
 assign eq_twin_boundary_live=twin.protected_parent.candidate.live_owner[eq_twin_boundary_context*56+:56];
 assign eq_twin_c0=twin.protected_parent.candidate.next_c0;
 assign eq_twin_c1=twin.protected_parent.candidate.next_c1;
endmodule
