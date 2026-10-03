"""R11 scalar publication algebra; source/transport calendar NOT frozen.

The input geometry and FIRST edges must come from the future source writer.
This function does not decide stage deltas, assume added latency is free, or
inherit an earlier sample-cycle count. No arithmetic oracle or HDL is run.
"""

SOURCE_READY = False
SOURCE_FREEZE = 'SOURCE_NOT_FROZEN'
SWITCHES = ('CRT_TRANSPORT_REG', 'INVERSE_INGRESS_REG',
            'TERM_JOIN_TRANSPORT_REG', 'NTT_COMPARE_REG')


def geometry(before, *, crt_transport_reg=0, inverse_ingress_reg=0,
             term_join_transport_reg=0, ntt_compare_reg=0):
    """Core-selected planned edge algebra, still not a frozen source claim.

    Term JOIN captures the matched A/term tuple AFTER the existing E4
    recurrence; it does not register multiplier inputs or change that loop.
    CRT transport leaves field retirement/SINK distinct from CRT delivery.
    Optional compare geometry is capability only, not primary enabled RTL.
    """
    flags = (crt_transport_reg, inverse_ingress_reg, term_join_transport_reg, ntt_compare_reg)
    if any(type(flag) is not int or flag not in (0, 1) for flag in flags):
        raise ValueError('R11_BOOLEAN_SWITCHES')
    g = dict(before)
    if not any(flags):
        return g
    if g.get('n') not in (256, 65536) or g.get('p') != 16 or g.get('contexts') != 2:
        raise ValueError('R11_AW8_FULL_P16_C2_ONLY')
    aw = g['aw']
    ct = aw * ntt_compare_reg
    gs = (aw - 1) * ntt_compare_reg
    sink = ct + gs + term_join_transport_reg + inverse_ingress_reg
    downstream = sink + crt_transport_reg
    g['ct_output_latency'] += ct
    g['gs_output_latency'] += gs
    g['pointwise_accept'] += ct
    g['square_accept'] += ct + term_join_transport_reg
    g['inverse_accept'] += ct + term_join_transport_reg + inverse_ingress_reg
    for key in ('physical_first', 'sink_accept', 'last_sink'):
        g[key] += sink
    for key in ('crt_accept', 'crt_output', 'double_register', 'carry_accept',
                'first_digit', 'last_digit', 'boundary_output', 'carry_done'):
        g[key] += downstream
    earliest = g['first_digit'] + 1
    correction = g['boundary_output'] + 1
    interval = max(earliest, correction + g['correction_cache_latency'] + 1 - g['pointwise_accept'])
    correction = max(correction, interval)
    g.update(earliest_next_frame=earliest, warm_interval=interval,
        feedback_delay=interval-earliest, feedback_fifo_rows=interval-earliest,
        next_correction_accept=correction,
        next_cache_capture=correction+g['correction_cache_latency'],
        cache_margin=interval+g['pointwise_accept']-correction-g['correction_cache_latency']-1,
        carry_busy_edges=g['carry_done']-g['sink_accept']+1,
        crt_transport_reg=crt_transport_reg, inverse_ingress_reg=inverse_ingress_reg,
        term_join_transport_reg=term_join_transport_reg, ntt_compare_reg=ntt_compare_reg,
        crt_delivery_after_field_sink_edges=crt_transport_reg)
    if g['cache_margin'] < 0 or g['feedback_delay'] < 0:
        raise ValueError('R11_NONNEGATIVE_CACHE_AND_FEEDBACK')
    for key in ('correction_cache_latency', 'term_seed_first', 'term_seed_last'):
        if g[key] != before[key]:
            raise ValueError('R11_E4_RECURRENCE_AND_CORRECTION_PATH_UNCHANGED')
    return g


def event_calendar(g, count, *, special=(False, False), solo=False):
    # These FIRST anchors are explicitly pending the new source trace/native
    # proof; the model never treats the candidate as already frozen/qualified.
    first = [104] if solo else [204, 204 + g['warm_interval']//2]
    result = publication_calendar(g, count, first, special=special)
    result.update(model_only=True, first_edges_source_obligation=True,
                  copy_edges=g['n']+4, measured_full_sample_PRP=False)
    return result


def prove_schedule(g):
    from . import stream27_context_timing_bind as c2
    from . import stream27_c2_state_analysis as lifetime
    schedule = c2.schedule(g)
    second = next(row['accept'] for row in schedule['correction']
                  if row['tag'][0] == 1 and row['tag'][3] == 0)
    witnesses = []
    for anchor in (0, 1):
        windows = lifetime.windows((16, 16), anchor=anchor,
            interval=g['warm_interval'], pointwise=g['pointwise_accept'], rows=g['rows'],
            next_correction=g['next_correction_accept'], second_correction=second)
        gap = lifetime.check_windows(windows)
        logical = lifetime.logical_peak(windows, release_offset=g['last_sink'])
        witnesses.append(dict(anchor=anchor, minimum_gap=gap, logical_peak=logical['peak'],
            windows=windows, last_payload_read=g['pointwise_accept']+g['rows']-1,
            conservative_raw_retirement=g['pointwise_accept']+g['rows']))
    # A passive register preserves tuple identity and delays BEGIN/row0
    # together; actual reset/error gating remains a separate RTL obligation.
    rows = [(context, row, row == 0, context*100+row)
            for context in (0, 1) for row in range(g['rows'])]
    captured = None
    delivered = []
    for token in rows+[None]:
        if captured is not None:
            delivered.append(captured)
        captured = token
    if delivered != rows or any(first != (row == 0) for _, row, first, _ in delivered):
        raise ValueError('R11_COHERENT_CRT_BEGIN_ROW_TUPLE')
    result = dict(schedule)
    result.update(status='PASS_CONDITIONAL_SOURCE_EDGE_MODEL_ONLY',
        storage2_lifetime=witnesses, physical_banks=2, logical_leases=4,
        crt_delivery_offset=g.get('crt_delivery_after_field_sink_edges', 0),
        passive_tuple_begin_alignment_cases=len(rows),
        term_E4_loop_not_retimed=True, cache_and_seed_path_not_retimed=True,
        actual_profile_owner_and_reset_fault_gating_proof_pending=True,
        source_ready=False, native_qualified=False, full_N_numeric_performed=False,
        clock_or_area_claim=False)
    return result


def publication_calendar(geometry, count, first_edges, *, special=(False, False)):
    """Conditional recurrence only; each input remains source-proof obligated."""
    if type(count) is not int or not 1 <= count <= 0xffffffff:
        raise ValueError('R11_FULL32_COUNT')
    if type(first_edges) is not list or len(first_edges) not in (1, 2) or \
            any(type(edge) is not int or edge < 0 for edge in first_edges):
        raise ValueError('R11_EXPLICIT_FIRST_EDGES')
    if len(special) != 2 or any(type(value) is not bool for value in special):
        raise ValueError('R11_SPECIAL_MASK')
    required = ('n', 'rows', 'warm_interval', 'carry_done')
    if any(type(geometry.get(key)) is not int or geometry[key] <= 0 for key in required):
        raise ValueError('R11_EXPLICIT_SOURCE_GEOMETRY')
    warm = [edge + (count - 1) * geometry['warm_interval'] + geometry['carry_done'] + 1
            for edge in first_edges]
    release = -1
    allocation, publication = [], []
    for context, edge in enumerate(warm):
        start = max(edge + 2, release + 1)
        allocation.append(start)
        # R9 one-edge full56 publication drain remains an explicit obligation
        # in the future R11 source; it is not inferred from a candidate name.
        release = start + geometry['rows'] + 10 * geometry['n'] + 7 + \
                  (geometry['n'] if special[context] else 0)
        publication.append(release)
    return dict(count_per_context=count, interval=geometry['warm_interval'],
        first_edges=first_edges, warm_edges=warm, allocation_edges=allocation,
        publication_edges=publication, pair_completion_cycles=release,
        full_read_completion_cycles=release + geometry['n'],
        source_ready=False, conditional_model_only=True,
        proof_obligations=['actual transport/control/tag acceptance and fill',
            'field-retirement versus downstream-CRT lease distinction',
            'four-edge term recurrence and storage reuse',
            'fault/reset/cancel flush and origin publication masking',
            'source-owned I/F/C/cache/seed/PW and cold FIRST edges',
            'unchanged N+4 copy and per-job publication drain'],
        measured_or_inherited_sample_cycles=False, clock_or_area_claim=False)


def require_frozen():
    if not SOURCE_READY or SOURCE_FREEZE == 'SOURCE_NOT_FROZEN':
        raise ValueError('R11_SOURCE_NOT_FROZEN_NO_NATIVE_EXPECTATIONS')
