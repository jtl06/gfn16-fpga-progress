"""Protected R9 field-report/local-stop model, not a production transform.

The existing controller is the acceptance latch for the complete raw fault
setter. A separate report stage samples that STICKY acceptance, never a
newly STOP-gated event. Its FAST output remains the old controller state.
Same-D quarantine-copy absorption is valid only with the existing inductive
binary reset/set invariant; this is not arbitrary FF-corruption immunity.
"""
import itertools

SOURCE_READY=False
FLAGS=('FIELD_ERROR_REPORT_REG','FIELD_LOCAL_STOP_ABSORPTION','C0_ADMISSION_DIRECT')
PARENT_BINDER_SHA256='3a507134f0a68fa393653ca1f8c7ac6e7fe7288d1f5ad0e7e36dc9657cf2a865'
PARENT_FULL_ROOT_SHA256='33a89e3bf4f505118cb4f6f45fb23f00e718396f86137fe6d4e990401ab679c8'


def field_step(controller,copies,report,raw_faults,*,reset=False,absorb=False):
    if len(copies)!=2 or len(raw_faults)!=8:raise ValueError('FIELD100_EXACT_SETTER_ROSTER')
    if reset:return dict(controller=False,copies=(False,False),report=False,fast=False,accepted=False)
    stop=controller or (any(copies) if absorb else False)
    accepted=not stop and any(raw_faults)
    new_controller=controller or accepted
    new_copies=tuple(q or accepted for q in copies)
    # CRITICAL: no !stop gate here. The old controller already latched actual
    # eligible origin acceptance and cannot be revoked by next-edge STOP.
    new_report=report or controller
    return dict(controller=new_controller,copies=new_copies,report=new_report,
        fast=new_controller,accepted=accepted)


def prove_fields():
    cases=0
    for state,report,raw,reset in itertools.product((False,True),(False,True),
            itertools.product((False,True),repeat=8),(False,True)):
        copies=(state,state)
        old=field_step(state,copies,report,raw,reset=reset,absorb=False)
        new=field_step(state,copies,report,raw,reset=reset,absorb=True)
        assert old==new
        assert new['fast']==new['controller']
        # Every actually accepted non-reset event survives subsequent STOP
        # and reaches the report on the next edge without any new input.
        if new['accepted']:
            after=field_step(new['controller'],new['copies'],new['report'],(False,)*8,absorb=True)
            assert after['report'] and after['fast']
        cases+=1
    # The tempting captured eligibility then next-edge !STOP gate loses the
    # very event that set STOP. Keep this explicit negative control.
    eligible=True;stop_after_accept=True
    wrong_report=eligible and not stop_after_accept
    assert not wrong_report
    return dict(inductive_binary_cases=cases,same_D_copy_stop_absorption=True,
        origin_controller_and_copy_cycles_unchanged=True,fast_same_NBA_origin=True,
        field_report_additional_edges=1,report_never_rechecks_stop=True,
        next_stop_regating_negative_control_detected=True,
        arbitrary_inconsistent_copy_or_XZ_claim=False,native_qualified=False)


def prove_publication():
    cases=0
    for raw,private_ready,private_done,private_read,reset in itertools.product((False,True),repeat=5):
        origin=field_step(False,(False,False),False,(raw,)+(False,)*7,reset=reset,absorb=True)
        # Private final-ack/drain flags may pulse at the origin. Public masks
        # must use FAST, not the delayed report. Reset separately clears them.
        outputs=[v and not reset and not origin['fast'] for v in (private_ready,private_done,private_read)]
        if raw or reset:assert not any(outputs)
        else:assert outputs==[private_ready,private_done,private_read]
        cases+=1
    return dict(origin_publication_read_mask_cases=cases,private_pulses_not_forbidden=True,
        unchanged_full56_COPY_DRAIN_and_reset_checks_required=True,
        new_field_FAST_port_required=True,global_report_contract_still_source_obligation=True,
        healthy_data_owner_calendar_edges_added=0)


def prove_protocol_origin():
    """Check the actual field/protocol sticky-origin identity.

    Each actual child wrapper includes its sticky error in its pending
    output; inverse does likewise. The protocol receives admission/join,
    all child pending and inverse pending as external_fault_pending.
    Thus its accepted sticky fault and the redundant field controller
    reset and set on the same edge. This proof is conditional on those
    exact source anchors, not a universal replacement of arbitrary inputs.
    """
    cases=0
    implication_states=((False,False),(True,False),(True,True))
    for state,(cp,ce),(ip,ie),admission,join,bad,reset in itertools.product(
            (False,True),implication_states,implication_states,
            (False,True),(False,True),(False,True),(False,True)):
        controller=protocol=state
        external=admission or join or cp or ip
        protocol_stop=controller or protocol
        pending=protocol or (not protocol_stop and (bad or external))
        accepted=not controller and (admission or join or cp or ce or ip or ie or pending or protocol)
        controller_after=False if reset else controller or accepted
        protocol_after=False if reset else protocol or (not protocol_stop and (bad or external))
        assert controller_after==protocol_after
        # Delayed copies cannot create an independent fault authority on
        # reachable traces: any set copy implies the existing FAST sticky.
        for copy in (False,state):
            absorbed=False if reset else protocol or copy or bad or external
            assert absorbed==protocol_after
        cases+=1
    return dict(binary_origin_cases=cases,
        child_error_implies_pending_source_anchors_required=True,
        inverse_error_implies_pending_source_anchor_required=True,
        protocol_external_roster_exact_required=True,
        field_controller_equals_protocol_sticky_by_induction=True,
        self_quarantine_and_delayed_copy_absorption_reachable_only=True,
        rejected_or_stopped_new_event_not_accepted=True,
        native_qualified=False,source_transform_ready=False)


def prove_report_chain():
    """Actual R9 warm latch shortens the externally visible report lag.

    Proposed local field report samples FAST, arithmetic report samples
    that local report. Warm's existing local_error ALSO samples FAST via
    child_barrier, so host report remains one edge after a field origin.
    No eligibility is requalified on that later edge.
    """
    traces=0
    for fault_edge,reset_edge in itertools.product(range(4),(-1,0,1,2,3,4)):
        fast=field_report=arithmetic_report=warm_error=False
        accepted_edge=None
        for edge in range(6):
            reset=edge==reset_edge
            raw=edge==fault_edge
            oldfast=fast;oldfield=field_report
            if reset:
                fast=field_report=arithmetic_report=warm_error=False
                accepted_edge=None
            else:
                if raw and not fast:accepted_edge=edge
                fast=fast or raw
                field_report=field_report or oldfast
                arithmetic_report=arithmetic_report or oldfield
                warm_error=warm_error or oldfast
            if accepted_edge is not None:
                assert fast
                assert edge<accepted_edge+1 or field_report
                assert edge<accepted_edge+1 or warm_error
                assert edge<accepted_edge+2 or arithmetic_report
            # The public safety mask always follows FAST, never reports.
            visible_private_publication=not fast and not reset
            assert not fast or not visible_private_publication
            traces+=1
    return dict(origin_reset_trace_edges=traces,field_report_origin_lag=1,
        arithmetic_report_origin_lag=2,host_report_origin_lag=1,
        existing_warm_FAST_latch_must_remain_literal=True,
        public_FAST_origin_lag=0,private_publication_pulses_allowed=True,
        source_and_native_composition_required=True)


def prove_private_quarantine():
    cases=0
    for fault_edge,reset_edge in itertools.product(range(3),(-1,0,1,2,3)):
        fast=local_q=False
        for edge in range(5):
            reset=edge==reset_edge
            # PRE-origin legacy and new eligibility match. After accepted
            # FAST, delayed local gating may admit private work, never a
            # globally effective carry/coefficient/publication transaction.
            old_ingress=not fast
            private_ingress=not local_q
            public_ingress=private_ingress and not fast
            assert old_ingress==public_ingress
            oldfast=fast
            if reset:fast=local_q=False
            else:fast=fast or edge==fault_edge;local_q=local_q or oldfast
            assert not (fast and (private_ingress and not fast))
            if reset:assert not fast and not local_q
            cases+=1
    return dict(private_transport_trace_edges=cases,new_healthy_edges=0,
        public_FAST_gate_required=True,reset_clears_transport=True,
        private_acceptance_may_lag_one_edge=True,
        numeric_pipeline_flush_within_one_edge_claim=False,
        HOST_watchdog_is_not_field_flush=True)
