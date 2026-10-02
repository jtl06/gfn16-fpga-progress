"""P16 warm-controller interface/event proposal. No HDL or full-N numeric NTT.

The frozen physical probes are unchanged. Component edge contracts are composed
with explicit next-edge transfers; this is NOT measured whole-core timing.
CONTEXTS=1 owns two consecutive image leases, never two independent tests.
"""
from .merged_stream27_model_v1 import topology
from .stream27_registered_fault_contract_v1 import Protocol as FieldProtocol
from .stream_ntt_model import bit_reverse


def geometry(n=65536, *, variant='p16c'):
    if n < 64 or n > 65536 or n & (n-1) or variant not in ('p16c', 'p16a'):
        raise ValueError('P16_WARM_GEOMETRY')
    p=16; rows=n//p; aw=n.bit_length()-1
    ct=topology(n,p)['first_output_edge']
    gs=topology(n,p,inverse=True)['first_output_edge']
    minimum_frame_spacing=rows+max(s['shuffle_depth_per_buffer']
        for inverse in (False,True) for s in topology(n,p,inverse=inverse)['stages'])
    # Digit reducer k->k+3; optional separate twist then k->k+3.
    # Small corrections ALWAYS retain the separate twist/P-point DIF route.
    separate=variant=='p16a'
    forward_accept=4+4*separate
    pointwise=forward_accept+ct+1  # add-A accept
    square=pointwise+2             # add-A / add-B are one FF each
    inverse=square+4               # square output k+3, consumer next edge
    physical=inverse+gs+4*separate # optional fused untwist k+3
    sink=physical+1
    # Proposed S4 register contract, not the A4 RAM-based post-NTT wrapper:
    # CRT accepted k -> k+15; centered optional-double FF at k+16;
    # carry accepts k+17 -> digit k+42 -> feedback accepted k+43.
    carry=sink+17
    digit=carry+25
    boundary=carry+rows-1+28
    # Accept signed A at C, B at C+1, small twists at C+5/C+6,
    # P16 DIF accepts C+9/C+10, outputs +23; bank captures C+33/+34.
    # Four initial seeds at C+35..38, cache captures C+39..42.
    correction_latency=6*4+18
    earliest=digit+1
    correction=boundary+1  # rotate/negate into registered next-epoch request
    # If correction predates frame admission, hold its request until admission.
    # A cache captured on a PW edge is too late for that edge's pre-state.
    interval=max(earliest,correction+correction_latency+1-pointwise)
    correction=max(correction,interval)
    cache=correction+correction_latency
    if cache>=interval+pointwise:
        raise ValueError('P16_WARM_COLD_CORRECTION_CANNOT_MEET_DEADLINE')
    return dict(n=n,p=p,rows=rows,aw=aw,variant=variant,contexts=1,
        ct_output_latency=ct,gs_output_latency=gs,forward_accept=forward_accept,
        pointwise_accept=pointwise,square_accept=square,inverse_accept=inverse,
        physical_first=physical,sink_accept=sink,last_sink=sink+rows-1,
        crt_accept=sink,crt_output=sink+15,double_register=sink+16,
        carry_accept=carry,first_digit=digit,last_digit=digit+rows-1,
        boundary_output=boundary,carry_done=boundary+1,
        earliest_next_frame=earliest,warm_interval=interval,
        minimum_transform_frame_spacing=minimum_frame_spacing,
        feedback_delay=interval-earliest,feedback_fifo_rows=interval-earliest,
        next_correction_accept=correction,correction_cache_latency=correction_latency,
        next_cache_capture=cache,cache_margin=interval+pointwise-cache-1,
        initial_latest_correction=pointwise-correction_latency-1,
        term_seed_first=35,term_seed_last=38,term_contexts=4,
        scope='proposed registered integration edge model; not RTL/native/clock qualification',
        full_N_numeric_NTT_performed=False)


def lane_contract(n=65536):
    g=geometry(n); rows=g['rows']
    return [dict(field_lane=lane,carry_lane=bit_reverse(lane,4),
                 coefficient_index_base=bit_reverse(lane,4)*rows,
                 boundary_target_lane=bit_reverse((bit_reverse(lane,4)+1)%16,4),
                 boundary_sign=-1 if bit_reverse(lane,4)==15 else 1)
            for lane in range(16)]


def interface():
    return dict(parameters={'P':16,'CONTEXTS':1,'EPOCH_W':16,'GEN_W':8},
        input_row='16 ordinary unsigned32 digits, index=bit_reverse(lane,4)*T+row',
        configuration='base32, reciprocal96 and coefficient_limit77 qualified before cold start; double bit latched per image',
        frame='dense T rows; row0 carries epoch16/cohort8/base32; no ready-based holes',
        correction='separate valid/epoch16/cohort8 with 16 signed32 c0 and c1 in natural block order; sampled only on acceptance',
        field_output='16 ordinary canonical27 residues plus physical slot/start/epoch/cohort; three fields must agree before CRT',
        carry_input='16 signed96 centered coefficients in natural contiguous-block lane order; optional double AFTER CRT',
        feedback='UNPATCHED redundant digits, not canonical image: static bit-reverse lane wiring plus late c0/c1 spectral correction; boundary rotate + negate final wrap',
        carry_begin='begin_block/config must be accepted before first coefficient; never coassert begin_block and in_valid',
        ownership='two image descriptors in one test; field lease drains at last physical sink; whole-image carry lease lasts through boundary/done',
        cancellation='never deletes physical field/term rows; intrinsic owned tag/current live cohort/enabled always qualify terminal writes',
        fault='current unrelated diagnostic may permit valid old commit at origin k; sticky stop blocks k+1; partial image invalidated',
        reset='flush all valid/lease/cache/producer state; held requests cannot accept during reset',
        finite_tag_reuse='epoch/cohort may wrap only after ALL old producer/cache/correction messages and physical sinks drain',
        contexts2='reserved interface hook only; unsupported/rejected until S5 qualification',
        pending=['parameterized P16 signed reducers/small DIF/segmented term producer RTL',
                 'source-bound arithmetic + native AW8 then AW16 field composition',
                 'three-field alignment, carry restart and feedback FIFO native gates',
                 'host cold load/readback and T5b E2E equivalence'])


class Protocol(FieldProtocol):
    """Reuse r17 intrinsic-lease state transitions, inject new P16 calendar.

    Only the field lease machine is represented; feedback_schedule separately
    counts whole-image carry ownership. This does not make v5 RTL P16-qualified.
    """
    def __init__(self,n=65536,*,variant='p16c',epoch_bits=16):
        self.g=geometry(n,variant=variant);self.mask=(1<<epoch_bits)-1;self.reset()


def producer_collisions(g, starts, corrections):
    """One multiplier/lane: seed issue or current PW's row+4 update, not both."""
    claims={}; collisions=[]
    for owner,(start,corr) in enumerate(zip(starts,corrections,strict=True)):
        for edge in range(corr+g['term_seed_first'],corr+g['term_seed_last']+1):
            claims.setdefault(edge,[]).append(('seed',owner))
        for row in range(g['rows']-4):
            claims.setdefault(start+g['pointwise_accept']+row,[]).append(('update',owner))
    for edge,uses in sorted(claims.items()):
        if len(uses)>1:collisions.append((edge,uses))
    return collisions


def feedback_schedule(n=65536, *, variant='p16c',frames=4):
    """Full-size event-only trace: no arrays of residues, no numerical NTT."""
    if frames<2 or frames>16:raise ValueError('P16_WARM_BOUNDED_FRAMES')
    g=geometry(n,variant=variant)
    starts=[i*g['warm_interval'] for i in range(frames)]
    if g['warm_interval']<g['minimum_transform_frame_spacing']:
        raise ValueError('P16_WARM_FIFO_NOT_DRAINED')
    corrections=[0]+[starts[i-1]+g['next_correction_accept'] for i in range(1,frames)]
    caches=[c+g['correction_cache_latency'] for c in corrections]
    collision=producer_collisions(g,starts,corrections)
    if collision:raise ValueError('P16_WARM_PRODUCER_COLLISION:'+str(collision[:1]))
    model=Protocol(n,variant=variant); peak=commits=physical=0;whole_peak=0
    start_map={t:i for i,t in enumerate(starts)}
    corr_map={t:i for i,t in enumerate(corrections)}
    cache_map={t:i for i,t in enumerate(caches)}
    for tick in range(starts[-1]+g['carry_done']+1):
        pw=[(i,tick-s-g['pointwise_accept']) for i,s in enumerate(starts)
            if 0<=tick-s-g['pointwise_accept']<g['rows']]
        sink=[(i,tick-s-g['sink_accept']) for i,s in enumerate(starts)
              if 0<=tick-s-g['sink_accept']<g['rows']]
        if len(pw)>1 or len(sink)>1:raise ValueError('P16_WARM_ROW_OVERLAP')
        e=model.edge(tick,begin=(start_map[tick],0,1_000_000_000) if tick in start_map else None,
            correction=(corr_map[tick],0) if tick in corr_map else None,
            ready=(cache_map[tick],0) if tick in cache_map else None,
            pw=(0,pw[0][1]==0) if pw else None,sink=(0,sink[0][1]==0) if sink else None)
        if e.error_after:raise ValueError('P16_WARM_EVENT_FAULT:'+str(tick))
        peak=max(peak,e.owners_after);commits+=e.commit;physical+=bool(sink)
        whole_peak=max(whole_peak,sum(s<=tick<=s+g['carry_done'] for s in starts))
    if model.owners or physical!=frames*g['rows'] or commits!=physical or whole_peak>2:
        raise ValueError('P16_WARM_DRAIN')
    return dict(geometry=g,frames=frames,field_peak_owners=peak,whole_peak_owners=whole_peak,
        physical_rows=physical,eligible_commits=commits,producer_collisions=collision,
        starts=starts,corrections=corrections,cache_captures=caches,
        extra_epoch_bits_in_main_FIFO='not adopted; calendar reconstruction still needs composed RTL proof',
        full_N_numeric_NTT_performed=False)
