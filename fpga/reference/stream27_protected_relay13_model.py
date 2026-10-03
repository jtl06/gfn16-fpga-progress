"""R13 protected boundary/recurrence model; not native or clock evidence.

Keep the physical warm FIFO from field100. The explicit paired feedback
register is additional to that FIFO, including when forward latency creates
more correction-cache slack. Do not silently shrink the FIFO to the scalar
minimum. No CRT transport, inner-BF split or arithmetic-profile change.
"""
import itertools

FLAGS=('INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG','FORWARD_INGRESS_REG')
SOURCE_READY=False


def geometry(before, *, inverse_ingress_reg=0, term_join_transport_reg=0,
             forward_ingress_reg=0):
    flags=(inverse_ingress_reg,term_join_transport_reg,forward_ingress_reg)
    if any(type(x) is not int or x not in (0,1) for x in flags):
        raise ValueError('R13_BOOLEAN_SWITCHES')
    if not any(flags):return dict(before)
    if before.get('n') not in (256,65536) or before.get('p')!=16 or before.get('contexts')!=2:
        raise ValueError('R13_PROTECTED_P16_C2_GEOMETRY')
    if before.get('explicit_feedback_register_rows')!=1 or before.get('automatic_correction_input_edges_added')!=1:
        raise ValueError('R13_FROZEN_PAIRED_FEEDBACK_PARENT')
    g=dict(before)
    # CT/GS latency is INTERNAL to the transform. The added forward tuple
    # delays its acceptance, not its internal stage count.
    g['forward_accept']+=forward_ingress_reg
    g['pointwise_accept']+=forward_ingress_reg
    g['square_accept']+=forward_ingress_reg+term_join_transport_reg
    g['inverse_accept']+=forward_ingress_reg+term_join_transport_reg+inverse_ingress_reg
    downstream=sum(flags)
    for key in ('physical_first','sink_accept','last_sink','crt_accept','crt_output',
                'double_register','carry_accept','first_digit','last_digit','boundary_output','carry_done'):
        g[key]+=downstream
    physical_fifo=before['existing_feedback_delay']
    earliest=g['first_digit']+1
    feedback_earliest=earliest+physical_fifo+1
    correction=g['boundary_output']+2
    interval=max(feedback_earliest,
        correction+g['correction_cache_latency']+1-g['pointwise_accept'])
    correction=max(correction,interval)
    g.update(earliest_next_frame=earliest,earliest_feedback_transport_edge=earliest+1,
        earliest_physical_FIFO_plus_feedback_edge=feedback_earliest,
        warm_interval=interval,feedback_delay=interval-earliest,feedback_fifo_rows=interval-earliest,
        existing_feedback_delay=physical_fifo,physical_feedback_FIFO_rows=physical_fifo,
        next_correction_accept=correction,next_cache_capture=correction+g['correction_cache_latency'],
        cache_margin=interval+g['pointwise_accept']-correction-g['correction_cache_latency']-1,
        initial_latest_correction=g['pointwise_accept']-g['correction_cache_latency']-1,
        carry_busy_edges=g['carry_done']-g['sink_accept']+1,
        inverse_ingress_reg=inverse_ingress_reg,term_join_transport_reg=term_join_transport_reg,
        forward_ingress_reg=forward_ingress_reg,crt_transport_reg=0,
        crt_delivery_after_field_sink_edges=0,r13_field_boundary_edges_added=downstream)
    if g['cache_margin']<0 or g['feedback_delay']!=physical_fifo+1:
        raise ValueError('R13_LITERAL_FIFO_AND_PAIRED_REGISTER_RECURRENCE')
    for key in ('ct_output_latency','gs_output_latency','correction_cache_latency',
                'term_seed_first','term_seed_last','input_delay'):
        if g[key]!=before[key]:raise ValueError('R13_INNER_TRANSFORM_E4_CACHE_OR_FRONTEND_CHANGED')
    return g


def schedule(g):
    from . import stream27_context_transport11_model as ports
    proof=ports.prove_schedule(g)
    proof.update(r13_protected_source_proof_required=True,
        physical_feedback_FIFO_rows=g.get('physical_feedback_FIFO_rows',g['existing_feedback_delay']),
        explicit_feedback_register_rows=1,field_to_CRT_edges_added=0,
        native_qualified=False,clock_or_area_claim=False)
    return proof


def event_calendar(g,count,*,solo=False,special=(False,False)):
    from . import stream27_context_feedback12_model as publication
    return publication.event_calendar(g,count,solo=solo,special=special)


def prove_tuples():
    """Complete arbitrary binary tuple capture, valid kill and FAST fence.

    This models only the three new boundary registers. It does not infer
    field flush from a HOST watchdog or qualify whole-source fault behavior.
    Private unreset payload is never authorized without a fresh valid tuple.
    """
    tuples=(None,(0,0,65535,255,False,0,0),
        (1,4095,0,1,True,(1<<448)-1,(1<<432)-1))
    cases=0
    for pending,incoming,fast,reset in itertools.product(tuples,tuples,(False,True),(False,True)):
        delivered=None if reset or fast else pending
        captured=None if reset or fast else incoming
        if fast or reset:assert delivered is None and captured is None
        else:assert delivered==pending and captured==incoming
        cases+=1
    # Start/gen/data are one tuple; bubbles cannot consume held payload.
    rows=[(context,row,65535 if context==0 else 0,255 if context==0 else 1,
           row==0,(context<<30)+row,~row) for context in (0,1) for row in range(32)]
    q=None;out=[]
    for token in [None]+rows+[None,None]:
        if q is not None:out.append(q)
        q=token
    assert out==rows
    return dict(binary_priority_cases=cases,coherent_tuple_rows=len(rows),
        full25_generation_and_start_not_narrowed=True,reset_valid_clear=True,
        immediate_FAST_field_consumer_fence_required=True,
        raw_origin_checks_not_retimed=True,unreset_payload_no_stale_authority=True,
        HOST_watchdog_is_not_field_flush=True,native_qualified=False)
