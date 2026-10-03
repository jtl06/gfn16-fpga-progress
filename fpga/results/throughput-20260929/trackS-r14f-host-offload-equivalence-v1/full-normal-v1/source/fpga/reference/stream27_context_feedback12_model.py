"""R12 hypothesis: decouple feedback admission and automatic correction.

SOURCE/MODEL ONLY. No production transform or native qualification. The
measured motivating R10 path is carry ACTIVE -> digit/start/context ->
profile qualification -> prospective correction-base -> c0 bound -> fault ENA.
Added stages are counted; cold R6 correction acceptance is not retimed.
"""
import itertools
import random

SOURCE_READY=False
ROSTER=('FEEDBACK_INGRESS_REG','AUTO_CORRECTION_INGRESS_REG','C0_ADMISSION_DIRECT')


def geometry(before,*,feedback_ingress_reg=0,auto_correction_ingress_reg=0,
             c0_admission_direct=0):
    flags=(feedback_ingress_reg,auto_correction_ingress_reg,c0_admission_direct)
    if any(type(v) is not int or v not in (0,1) for v in flags):
        raise ValueError('R12_BOOLEAN_SWITCHES')
    g=dict(before)
    if not any(flags):return g
    if g.get('n') not in (256,65536) or g.get('contexts')!=2 or g.get('p')!=16:
        raise ValueError('R12_CLOSED_C2_GEOMETRY')
    # AW8's automatic correction originally coincides with next-frame BEGIN.
    # Retiming only BEGIN would send correction before its lease exists.
    if feedback_ingress_reg and not auto_correction_ingress_reg and g['n']==256:
        raise ValueError('R12_AW8_AUTO_CORRECTION_BEFORE_FRAME')
    baseline_earliest=g['first_digit']+1
    transport_earliest=baseline_earliest+feedback_ingress_reg
    correction=g['boundary_output']+1+auto_correction_ingress_reg
    interval=max(transport_earliest,
        correction+g['correction_cache_latency']+1-g['pointwise_accept'])
    correction=max(correction,interval)
    g.update(warm_interval=interval,earliest_next_frame=baseline_earliest,
        earliest_feedback_transport_edge=transport_earliest,
        feedback_delay=interval-baseline_earliest,
        feedback_fifo_rows=interval-baseline_earliest,
        existing_feedback_delay=before['feedback_delay'],
        explicit_feedback_register_rows=feedback_ingress_reg,
        next_correction_accept=correction,
        next_cache_capture=correction+g['correction_cache_latency'],
        cache_margin=interval+g['pointwise_accept']-correction-g['correction_cache_latency']-1,
        automatic_correction_input_edges_added=auto_correction_ingress_reg,
        cold_correction_input_edges_added=0,
        c0_admission_direct=c0_admission_direct)
    if g['cache_margin']<0 or g['feedback_delay']<feedback_ingress_reg:
        raise ValueError('R12_INSUFFICIENT_FEEDBACK_OR_CACHE')
    # Field pipeline is measured from actual accepted BEGIN, not a proposal.
    for key in ('pointwise_accept','sink_accept','crt_accept','first_digit',
                'boundary_output','carry_done','correction_cache_latency','term_seed_first','term_seed_last'):
        assert g[key]==before[key]
    return g


def c0_predicates(word,base):
    if not 0<=word<=0xffffffff or not 0<=base<=0xffffffff:
        raise ValueError('R12_FULL_U32_INPUTS')
    signed=word-(1<<32) if word&(1<<31) else word
    magnitude=abs(signed)  # 33-bit unsigned magnitude includes -2^31.
    old=magnitude<=((base-1)&0xffffffff)
    new=base==0 or magnitude<base
    return old,new


def prove_c0_identity():
    # For b>0 both integer predicates differ only <=b-1 versus <b.
    # For b=0, uint32 underflow is 2^32-1, exceeding every s32 magnitude.
    rng=random.Random(0xC012)
    bases=[0,1,2,598,599,131077,604832956,1000000000,0x7fffffff,0x80000000,0xffffffff]
    words=[0,1,0x7fffffff,0x80000000,0xffffffff]
    checks=0
    for b in bases:
        for m in (max(0,b-1),b,min(0x80000000,b+1)):
            if m<=0x80000000:
                words.extend((m&0xffffffff,(-m)&0xffffffff))
    for b,w in itertools.product(bases,set(words)):
        assert c0_predicates(w,b)[0]==c0_predicates(w,b)[1];checks+=1
    for _ in range(50000):
        assert len(set(c0_predicates(rng.randrange(1<<32),rng.randrange(1<<32))))==1
        checks+=1
    return dict(binary_checks=checks,all_u32_s32_identity_by_integer_cases=True,
        base0_unsigned_underflow_preserved=True,c1_and_fault_priority_unchanged=True,
        added_edges=0,added_register_bits=0,native_qualified=False)


def queue_step(pending,incoming,*,origin_bad=False,reset=False,sticky=False):
    """Specification, not implementation: origin fault fences delayed use.

    Incoming is the COMPLETE data/start/context/epoch/gen/double tuple. A raw
    descriptor/collision fault must remain an origin-edge sticky setter; the
    queue is not an authorization shortcut. Canceled but occupied raw tuples
    are not dropped just because a context loses eligibility.
    """
    if reset:return None,None,False
    fault=sticky or origin_bad
    delivered=None if fault else pending
    next_pending=None if fault else incoming
    return next_pending,delivered,fault


def prove_queue_contract():
    checks=0
    for pending,incoming,origin_bad,reset,sticky in itertools.product(
            (None,('row',1,65535,255,7,1)),
            (None,('row',0,0,1,8,0)),(False,True),(False,True),(False,True)):
        q,out,fault=queue_step(pending,incoming,origin_bad=origin_bad,reset=reset,sticky=sticky)
        if reset:assert (q,out,fault)==(None,None,False)
        elif sticky or origin_bad:assert q is None and out is None and fault
        else:assert q==incoming and out==pending and not fault
        checks+=1
    return dict(queue_priority_cases=checks,complete_tuple_specification=True,
        canceled_occupied_tail_not_silently_filtered=True,
        raw_command_collision_fault_setter_required=True,
        host_watchdog_abort_is_not_field_flush=True,implementation_exists=False)


def schedule(g):
    from . import stream27_context_transport11_model as lifetime
    # Reuse the bounded port/storage mechanics with R12 geometry, never its
    # source qualification. New ingress origin checks remain RTL obligations.
    result=lifetime.prove_schedule(g)
    result.update(r12_feedback_ingress_source_proof_pending=True,
        r12_automatic_correction_tuple_alignment_pending=True,
        cold_accept_retirement_must_remain_literal=True)
    return result


def event_calendar(g,count,*,solo=False,special=(False,False)):
    from . import stream27_context_transport11_model as arithmetic
    # Scalar recurrence reuse ONLY. R12 still needs its own source/native join.
    return arithmetic.publication_calendar(g,count,[104] if solo else [204,204+g['warm_interval']//2],
                                           special=special)
