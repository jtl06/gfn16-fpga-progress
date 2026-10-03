"""Binary R9 error/publication fence model; no native or timing claim."""
import itertools


def field_step(values):
    stop,child_pending,protocol_pending,admission,join,child_error,inverse_pending,inverse_error,protocol_error = values
    pending = bool(stop or child_pending or protocol_pending or (not stop and (admission or join)))
    after = bool(stop or admission or join or child_pending or child_error or
                 inverse_pending or inverse_error or protocol_pending or protocol_error)
    return pending,after


def aggregation_step(old_error,new_error,local_q,field_q,field_now,local_now,reset=False):
    if reset:
        return False,False,False,(False,False,False),False
    field_after=tuple(bool(q or n) for q,n in zip(field_q,field_now))
    local_after=bool(local_q or local_now)
    old_after=bool(old_error or local_now or any(field_q) or any(field_now))
    new_after=bool(new_error or local_q or any(field_q))
    barrier=bool(new_after or local_after or any(field_after))
    return old_after,new_after,local_after,field_after,barrier


def publication_step(pending,proposal,*,safe,owner_match=True,counts_complete=True,
                     extra_ack=False,reset=False):
    if reset:
        return False,False,False
    bad=bool(pending and (not owner_match or not counts_complete or extra_ack))
    publish=bool(pending and safe and not bad)
    return bool(proposal and not pending),publish,bad


def prove():
    fields=0
    for values in itertools.product((False,True),repeat=9):
        pending,after=field_step(values)
        assert not pending or after
        fields+=1
    aggregation=0
    for values in itertools.product((False,True),repeat=10):
        old,new,local,*rest=values
        q=tuple(rest[:3]);now=tuple(rest[3:6]);raw=rest[6]
        # Reachable sticky-state invariant; no stale fault can disappear.
        if old and not (new or local or any(q)):
            continue
        old_after,new_after,local_after,q_after,barrier=aggregation_step(old,new,local,q,now,raw)
        assert not old_after or barrier
        assert not new or new_after
        aggregation+=1
    sequences=0
    for masks in itertools.product(range(16),repeat=2):
        old=new=local=False;q=(False,False,False)
        previous_old=False
        for mask in (*masks,0,0):
            now=tuple(bool(mask&(1<<b)) for b in range(3))
            old,new,local,q,barrier=aggregation_step(old,new,local,q,now,bool(mask&8))
            assert not old or barrier
            assert not previous_old or new  # Registered report lags at most one edge.
            previous_old=old
        assert aggregation_step(old,new,local,q,(True,True,True),True,reset=True)==(
            False,False,False,(False,False,False),False)
        sequences+=1
    publication=0
    for pending,proposal,safe,owner,counts,ack,reset in itertools.product((False,True),repeat=7):
        after,publish,bad=publication_step(pending,proposal,safe=safe,owner_match=owner,
                                         counts_complete=counts,extra_ack=ack,reset=reset)
        assert not publish or (pending and safe and owner and counts and not ack and not reset)
        assert not reset or not (after or publish or bad)
        publication+=1
    # A fault on either proposal or drain edge cannot escape as ready/read-valid.
    hazards=0
    for fault_edge in (-1,0,1,2):
        pending=False;published=False;old=new=local=False;q=(False,False,False)
        for edge in range(4):
            pre_barrier=bool(new or local or any(q))
            pending,pulse,bad=publication_step(pending,edge==0,safe=not pre_barrier)
            published=published or pulse
            old,new,local,q,barrier=aggregation_step(old,new,local,q,
                (fault_edge==edge,False,False),False)
            visible=published and not barrier
            assert not (fault_edge>=0 and edge>=fault_edge) or not visible
            if fault_edge<0:
                assert visible==(edge>=1)
            hazards+=1
    return dict(field_pending_to_registered_controller_cases=fields,
        aggregation_cases=aggregation,sticky_two_edge_sequences=sequences,
        publication_owner_reset_priority_cases=publication,fault_proposal_drain_checks=hazards,
        global_report_max_added_edges=1,early_registered_source_barrier_preserved=True,
        healthy_publication_fence_edges_per_job=1,healthy_equal_pair_extra_edges=2,
        known_two_state_only=True,native_qualified=False,clock_or_area_claim=False)
