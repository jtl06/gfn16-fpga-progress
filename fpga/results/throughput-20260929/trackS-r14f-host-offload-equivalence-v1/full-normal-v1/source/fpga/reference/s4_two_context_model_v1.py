"""S4 two-test calendar/reference proposal, NOT a CONTEXTS=2 RTL gate.

Full N uses only integer edge/window/shape arithmetic. Literal finite FIFO and
three-prime arithmetic checks are restricted to N<=256. Logical test contexts,
frame leases, and the four term-recurrence microcontexts are distinct objects.
The frozen CONTEXTS=1 compiler is neither invoked nor changed by this model.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from . import merged_stream27_model_v1 as merged
from . import stream_ntt_blockwrap2_proposal as block
from .stream27_blockcarry_param_model_v1 import bounds, minimum_base
from .stream27_shared_field_v2 import geometry as frozen_geometry
from .stream_ntt_schedule import bit_reverse, index_of, m20k

NAMESPACE = 's4-two-context-model-v1'
ROOT = Path(__file__).resolve().parents[1]
PINS = {
    'reference/stream27_host_chain_param_v2.py': 'bd909f42310a194220c5c20f0a4e3decb3e97bcf142b3ffd5a1b300d0ffc9773',
    'reference/stream27_shared_field_v4.py': 'daa45b2d5c614f8ea2b791f993cc22c5cc1f5e215f307242785542b109e29865',
    'reference/stream27_shared_field_v2.py': '05eab167ccb00c2bb6a74475ec2b3c84549f0b328ac4d5dbf9e1faea73657fd2',
    'reference/stream27_shared_field_source_v1.py': '9a447cf96a88236714a68d4bbfb9edef152c063d48dcb5357cfdba31766ae0a4',
    'reference/stream27_p16_warm_contract_v1.py': '652a367b30e8d4457377ebe5a6c8676f2d5b3853a30d8d53b691278c0f6c676f',
    'reference/merged_stream27_model_v1.py': '7e28559a6b6079f6ab2b5092ea8604b712403b09d335232282105eca17fabee4',
    'reference/stream27_p16c_physical_probe_v1.py': 'a16996d16f0ad79a71b5a2941150441fee23b55a16a418329dbc3105cc933fab',
    'rtl/kernel/genefer_stream27_mdc_commutator_sm1_registered_v1.sv': 'c262261f1a7c7428056111ccdef97462edd081016f219428d2a81b7e429819c9',
    'rtl/kernel/genefer_stream27_term_context_v2.sv': '1785c86519e52908e5e450ec8d48656e2fc402808ad3660bda6aa7e8d4c86592',
    'rtl/kernel/genefer_stream27_blockcarry_lane_param_v1.sv': '8a458519272e89e635eb5cd7e6b2d07c93c8d3b1fc0f44874ba67aeccca77d4b',
    'rtl/kernel/genefer_stream27_host_image_ports_v1.sv': '2d1dbcd3d923323481b920d1354127306cf19253ee98ad60c0a87626cb1ba11e',
    'rtl/kernel/genefer_stream27_canonical_image_v1.sv': 'c6e59a385ed187dceb9b392c096cc1d7cfc5a71ba820326b9b441f1df8093e74',
    'reference/stream_ntt_blockwrap2_proposal.py': 'b6f94debf66b07aa118ab7e82be6802fd5a81cbc8c41a99cb79f65f91726e255',
    'reference/stream_ntt_schedule.py': '03c1c855e0f6e31f0fcb85d32ed2e604a935e482dfa725d7207e635cb1e963cc',
}


class ModelError(ValueError):
    def __init__(self, code, detail=''):
        self.code = code
        super().__init__(code + (': ' + str(detail) if detail else ''))


def need(ok, code, detail=''):
    if not ok:
        raise ModelError(code, detail)


def source_guard():
    for name, pin in PINS.items():
        need(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == pin,
             'S4_TWO_SOURCE_DRIFT', name)
    need(not (ROOT/'docs/briefs/PAUSE').exists(), 'S4_TWO_PAUSE')
    return dict(PINS)


@dataclass(frozen=True)
class Frame:
    context: int
    generation: int
    epoch: int
    ordinal: int
    start: int
    base: int

    @property
    def tag(self):
        return self.context, self.generation, self.epoch, self.ordinal

    @property
    def bank(self):
        return 2*self.context + (self.epoch & 1)


def geometry(n=65536, p=8, *, correction_latency=None):
    g = dict(frozen_geometry(n, p))
    seeds = min(4, g['rows'])
    original = g['correction_cache_latency']
    latency = original if correction_latency is None else correction_latency
    need(type(latency) is int and latency >= original, 'S4_TWO_CORRECTION_LATENCY')
    delta = latency-original
    g.update(initial_term_seeds=seeds, term_seed_first=6*(p.bit_length()-1)+11+delta,
             term_seed_last=6*(p.bit_length()-1)+10+seeds+delta,
             carry_accept=g['sink_accept']+17,
             carry_busy_edges=g['carry_done']-g['sink_accept']+1,
             frozen_correction_cache_latency=original, correction_cache_latency=latency,
             next_cache_capture=g['next_correction_accept']+latency,
             cache_margin=g['warm_interval']+g['pointwise_accept']-g['next_correction_accept']-latency-1,
             correction_scenario='frozen' if not delta else 'explicit_later_datapath_hypothesis')
    need(g['first_digit'] == g['sink_accept']+42 and
         g['carry_done'] == g['sink_accept']+g['rows']+45,
         'S4_TWO_COMPONENT_CALENDAR')
    return g


def disjoint(windows, resource):
    """Closed acceptance windows: a port can accept once on each edge."""
    windows = sorted(windows, key=lambda w: (w[0], w[1]))
    for a, b in zip(windows, windows[1:]):
        need(b[0] > a[1], 'S4_TWO_RESOURCE_'+resource, (a, b))
    return len(windows)


def lease_peak(frames, release_offset, capacity):
    """Admission checks PRE-edge state; same-edge release cannot free a bank."""
    live = []; peak = 0
    for f in frames:
        live = [old for old in live if old.start+release_offset >= f.start]
        need(len(live) < capacity, 'S4_TWO_LEASE_CAPACITY', f.tag)
        need(all(old.bank != f.bank for old in live), 'S4_TWO_BANK_REUSE', f.tag)
        live.append(f); peak = max(peak, len(live))
    return peak


def correction_calendar(frames, g, *, pair_interval=2, immediate_cold=False):
    """Earliest legal correction with seed ROM/Mont windows outside ALL PW rows.

    The cold second context's correction is not necessarily at its admission.
    Warm corrections are available at the predecessor's frozen boundary edge;
    moving one later is allowed only while its cache remains ready PRE-PW.
    This is a proposed outer arbiter, not behavior inherited from CONTEXTS=1.
    """
    pw = [(f.start+g['pointwise_accept'], f.start+g['pointwise_accept']+g['rows']-1, f.tag)
          for f in frames]
    result = []; previous = {}
    for f in frames:
        predecessor = previous.get(f.context)
        available = f.start if predecessor is None else max(f.start,
            predecessor.start+g['next_correction_accept'])
        corr = available
        if not (immediate_cold and predecessor is None):
            for lo, hi, _ in pw:
                if corr+g['term_seed_first'] <= hi and corr+g['term_seed_last'] >= lo:
                    corr = hi+1-g['term_seed_first']
        cache = corr+g['correction_cache_latency']
        margin = f.start+g['pointwise_accept']-cache-1
        need(margin >= 0, 'S4_TWO_CACHE_DEADLINE', (f.tag, corr, cache))
        result.append(dict(tag=f.tag, available=available, accept=corr,
            seed_first=corr+g['term_seed_first'], seed_last=corr+g['term_seed_last'],
            cache_capture=cache, pointwise_first=f.start+g['pointwise_accept'],
            margin=margin))
        previous[f.context] = f
    disjoint([(x['accept'], x['accept']+1, x['tag']) for x in result], 'CORRECTION_INPUT')
    need(type(pair_interval) is int and pair_interval>=2,'S4_TWO_CORRECTION_PAIR_INTERVAL')
    disjoint([(x['accept']+9, x['accept']+9+pair_interval-1, x['tag']) for x in result],
             'CORRECTION_DFT_PAIR_BUSY')
    disjoint(pw+[(x['seed_first'], x['seed_last'], x['tag']) for x in result], 'TERM_ROOT_ROM')
    updates = [(lo, lo+g['rows']-5, tag) for lo, _, tag in pw if g['rows']>4]
    disjoint(updates+[(x['seed_first'], x['seed_last'], x['tag']) for x in result], 'TERM_MONT')
    # Existing admission rejects a new correction while any seed is running.
    for x in result:
        for y in result:
            if x is not y:
                need(not y['seed_first'] <= x['accept'] <= y['seed_last'],
                     'S4_TWO_CORRECTION_DURING_SEED', (x['tag'], y['tag']))
    return result


def feedback_queues(frames, g):
    """Finite per-context FIFO, direct bypass only for zero frozen delay."""
    queues = [deque(), deque()]; peak = [0, 0]; events = {}; previous = {}
    for f in frames:
        old = previous.get(f.context)
        if old is not None:
            for row in range(g['rows']):
                token = (old.tag, row)
                events.setdefault(old.start+g['first_digit']+1+row, [[], []])[0].append((f.context, token))
                events.setdefault(f.start+row, [[], []])[1].append((f.context, token))
        previous[f.context] = f
    for tick, (writes, reads) in sorted(events.items()):
        need(len(writes)<=1 and len(reads)<=1, 'S4_TWO_FEEDBACK_PORT', tick)
        for ctx, token in reads:
            if queues[ctx]:
                need(queues[ctx].popleft() == token, 'S4_TWO_FEEDBACK_OWNER', tick)
            else:
                need(g['feedback_delay'] == 0 and (ctx, token) in writes,
                     'S4_TWO_FEEDBACK_UNDERFLOW', tick)
                writes.remove((ctx, token))
        for ctx, token in writes:
            queues[ctx].append(token); peak[ctx] = max(peak[ctx], len(queues[ctx]))
            need(len(queues[ctx]) <= g['feedback_fifo_rows'], 'S4_TWO_FEEDBACK_CAPACITY', tick)
    need(not any(queues), 'S4_TWO_FEEDBACK_DRAIN')
    return peak


def resources(n, p, g):
    """Exact bit/rectangle proxies for declared banks, never fitter ALM claims."""
    plans = [merged.topology(n, p, inverse=inv) for inv in (False, True)]
    fifo_words = sum(p*s['shuffle_depth_per_buffer'] for plan in plans for s in plan['stages'])
    return dict(logical_contexts=2, descriptor_banks=4, minimum_frame_leases=3 if n==65536 else None,
        shared_arithmetic=dict(field_CT_GS_butterflies='unchanged', field_square_lanes='unchanged',
            CRT_lanes=p, carry_lanes=p, correction_small_DFT_lanes='unchanged', term_Mont_lanes_per_field=p),
        transform_FIFO_words_all_three_fields=3*fifo_words,
        extra_transform_data_FIFO_words=0,
        extra_context_shadow_image_bits=32*n,
        extra_shadow_M20K_rectangle_proxy=p*m20k(n//p, 32),
        extra_shadow_M20K_512x32_proxy=p*((n//p+511)//512),
        extra_A_B_table_bits=3*2*2*p*27,
        extra_term_cache_data_bits=3*2*4*p*27,
        extra_persistent_c0_c1_bits=2*p*32,
        extra_setup_snapshot_bits=32+96+77,
        extra_feedback_FIFO_data_bits=p*32*g['feedback_fifo_rows'],
        tag_contract='Context bit is mandatory in every owner key; (epoch parity) alone aliases two tests.',
        tag_storage='Use per-context calendars/descriptor tags or carry context through FIFO sidebands; exact packed implementation not selected.',
        metadata_not_yet_sized=['generation8/live/enabled/epoch16/full ordinal32/double1 per context',
            'per-context base/profile/setup validity and controller/command FIFO/publication state',
            'term cached-row/valid/owner tags, correction table and pending-response tags',
            'context tag transport/prefetch/lookahead widths and eligibility fanout'],
        canonicalization='Shared canonical scratch requires a T-row waiting-final buffer with P*32-bit writes. A busy unpublished context shadow may double as that buffer ONLY with new tagged row-write ABI; frozen scalar-commit-only host image cannot capture P words/edge.',
        waiting_final_buffer_rows=n//p, waiting_final_buffer_width=p*32,
        separate_waiting_raw_buffer_extra_bits_if_shadow_not_reused=32*n,
        separate_waiting_raw_buffer_M20K_proxy_if_shadow_not_reused=p*m20k(n//p,32),
        ALM_DSP_M20K_delta_physically_qualified=False)


def schedule(n=65536, p=8, epochs=4, *, offset=None, capacity=4,
             correction_latency=None, correction_pair_interval=2):
    g = geometry(n, p, correction_latency=correction_latency)
    need(type(epochs) is int and 2 <= epochs <= 16, 'S4_TWO_BOUNDED_EPOCHS')
    interval = g['warm_interval']; offset = interval//2 if offset is None else offset
    need(type(offset) is int and 0 < offset < interval, 'S4_TWO_OFFSET')
    frames = sorted([Frame(ctx, 11+12*ctx, (65534+ordinal)&65535, ordinal,
        ordinal*interval+ctx*offset, (604832956, 1000000000)[ctx])
        for ordinal in range(epochs) for ctx in range(2)], key=lambda f:f.start)
    for f in frames: bounds(n, p, f.base)
    disjoint([(f.start, f.start+g['rows']-1, f.tag) for f in frames], 'INPUT')
    disjoint([(f.start+g['sink_accept'], f.start+g['carry_done'], f.tag) for f in frames], 'CARRY')
    field_peak = lease_peak(frames, g['last_sink'], capacity)
    whole_peak = lease_peak(frames, g['carry_done'], capacity)
    correction = correction_calendar(frames, g, pair_interval=correction_pair_interval)
    # Every shared row pipeline has II1. All shifted dense T-row windows
    # remain disjoint; the carry ACTIVE state above is the stricter boundary.
    for resource, first in [('PW',g['pointwise_accept']), ('SINK',g['sink_accept']),
                            ('COEFFICIENT',g['carry_accept']), ('DIGIT',g['first_digit'])]:
        disjoint([(f.start+first, f.start+first+g['rows']-1, f.tag) for f in frames], resource)
    feedback_peak = feedback_queues(frames, g)
    stage_proof = []
    for inverse in (False, True):
        plan = merged.topology(n, p, inverse=inverse)
        for s in plan['stages']:
            depth = s['shuffle_depth_per_buffer']
            need(not depth or g['rows'] % (2*depth) == 0, 'S4_TWO_FIFO_PHASE')
            stage_proof.append(dict(direction=plan['direction'], stage=s['stage'], depth=depth,
                first_accept=s['butterfly_first_accept'],
                row0_static_root=True, shared_root_read_ports=1,
                FIFO_words=p*depth, read_write_ports_per_FIFO=(1,1),
                minimum_input_spacing=g['rows'],
                invariant='T multiple2L: old tail phase0 agrees with next frame first L phase0; finite fixed-depth queues never flush at admission.'))
    resource = resources(n,p,g)
    resource['minimum_frame_leases'] = field_peak
    resource['maximum_whole_live_images'] = whole_peak
    finish = frames[-1].start+g['carry_done']+1
    single_finish = (epochs-1)*interval+g['carry_done']+1
    finite_gain = Fraction(2*single_finish, finish)
    return dict(namespace=NAMESPACE, status='PASS_MODEL_ONLY', n=n, p=p, geometry=g,
        frames=[asdict(f) | dict(bank=f.bank) for f in frames], correction=correction,
        per_context_interval=interval, per_context_carry_latency=g['carry_done'],
        launch_gaps=[offset, interval-offset], field_peak_leases=field_peak,
        whole_peak_leases=whole_peak, descriptor_capacity=capacity,
        correction_pair_min_interval=correction_pair_interval,
        feedback_peak_rows=feedback_peak,
        resources=resource, stage_FIFO_root_proof=stage_proof,
        finite_total_operations=2*epochs, finite_finish_exclusive=finish,
        two_serial_single_context_runs_finish=2*single_finish,
        finite_throughput_gain=[finite_gain.numerator, finite_gain.denominator],
        steady_aggregate_interval=[interval,2], steady_model_throughput_gain=2,
        modeled_span='First accepted cold field row through final carry-done inclusive; transform/carry startup and drain INCLUDED.',
        excluded_costs=['qualified setup before admission','host cold scalar load/conversion staging',
            'true-last canonical6N/7N and N-word shadow copy at chain stop','external I/O','fault/recovery'],
        qualification='Conditional calendar/FIFO/reference proposal only: no two-context RTL/native/physical/clock evidence. Warm steady2x and finite gain do NOT include the listed host boundary costs.',
        full_N_numeric_NTT_performed=False)


def stopped_context_buffer(n=65536,p=8,*,capacity_rows=None):
    """Lower-bound exact event occupancy, not a new canonical host controller.

    Both contexts finish the same ordinal. Scratch is assigned to A's final
    rows first. Even BEFORE its N-word copy, six canonical passes occupy it
    until all B's final rows have arrived. B therefore needs T held rows,
    not the small feedback FIFO. Payload values/NTT are never evaluated here.
    """
    g=geometry(n,p);offset=g['warm_interval']//2;T=g['rows']
    scratch_not_free_before=g['carry_done']+1+6*n
    first_B=offset+g['first_digit'];last_B=first_B+T-1
    peak=min(T,max(0,scratch_not_free_before-first_B))
    capacity_rows=T if capacity_rows is None else capacity_rows
    need(type(capacity_rows) is int and capacity_rows>=peak,
         'S4_TWO_STOP_BUFFER_CAPACITY',(capacity_rows,peak))
    return dict(waiting_context=1,first_row=first_B,last_row=last_B,
        canonical_scratch_not_free_before=scratch_not_free_before,
        peak_waiting_rows=peak,capacity_rows=capacity_rows,row_bits=p*32,
        required_bits=peak*p*32,write_rows_per_edge=1,
        owner='context/generation/full ordinal frozen across all waiting rows and c0/c1',
        scope='Only waiting-buffer lower bound; copy/arbitration/reload/host-publication latency is not qualified.')


def interface():
    return dict(
        parameters=dict(AW='5..16 bounded model',P='8|16',CONTEXTS=2),
        frozen_RTL_supports_contexts2=False,
        descriptor='Four banks indexed {context1,epoch_parity1}. Each full owner includes context1/generation8/epoch16; final selector also compares full ordinal32.',
        admission='Dense T rows, one context per frame; alternate at floor(I/2)/ceil(I/2), not T. No ready holes. Each context advances its own epoch and ordinal.',
        setup='Qualify/cache base32/reciprocal96/coefficient_limit77 per context; shared restoring setup may run serially BEFORE admission. Carry latches selected immutable snapshot at joined first sink,17 edges before first coefficient.',
        corrections='Natural block c0/c1 signed32 per context; two accepted vectors at C/C+1 with identical context/generation/epoch. Context tags survive both small transforms, table capture, seed issue, cache capture and PW consumption. Cold B correction can be late, not necessarily at B frame admission.',
        roots='Main CT/GS roots are geometry/field-only, common to contexts. Physical row counters restart on each dense frame; static row0 root plus single-read next-row prefetch. Shared term ROM seeds cannot overlap PW slots in this conservative calendar.',
        term_microcontexts='Four recurrence rows per frame are NOT logical tests. Expand two epoch-parity banks to four {context,parity} banks and extend every lookup/write/bypass owner comparison.',
        feedback='Separate context queues/tags and persistent c0/c1; direct next-edge redundant-digit feedback when delay0, otherwise frozen finite FIFO allocation. Never substitute a canonical host image for warm redundant feedback.',
        boundary='Field lane l is natural carry block reverse(l,log2P). Corrections rotate block k→(k+1)%P, negating BOTH full signed33 components only on final wrap. Carry/digit/boundary tags remain the same accepted owner.',
        publication='Context remains busy through true-last canonical6N/7N and N-word shadow copy. Distinct signed32 shadow RAM/publication generations. Shared canonical scratch needs full T-row waiting-final storage with P-word/edge capture; reuse an unpublished busy shadow ONLY after adding tagged row-write arbitration, else add another32N raw buffer. Frozen scalar commit is insufficient. Host barrier throughput is excluded from warm calendar.',
        cancellation='Do not flush/stall shared occupied FIFO rows for one canceled context. Recheck enabled/live generation plus full intrinsic owner at terminal commit. No finite tag reuse until physical rows, term/cache messages and boundary tails drain. Global reset cancels both; context-local recovery is a NEW RTL/fault gate, not inherited.',
        fault_scope='Frozen r17 unrelated diagnostic can permit one old commit at its origin edge; intrinsic stale/disabled owner blocks immediately. Shared child quarantine may affect both contexts, so this model does not promise fault-local datapath recovery.',
        future_gate='Actual two independent full-N contexts vs single-context reference, typed cross-talk negative, measured per-context/aggregate cycles, native finite-buffer/reset/fault contracts, then resource probe/whole fit. No full-N numeric work on Mac.')


def fifo_replay(n=256, p=8, epochs=4, *, transform_gap=None):
    """All tagged indices at every stage, finite read-old/write FIFO behavior."""
    need(n <= 256, 'S4_TWO_LITERAL_FIFO_SMALL_ONLY')
    calendar = schedule(n,p,epochs); T=n//p; aw=n.bit_length()-1; pw=p.bit_length()-1
    frames=[Frame(**{k:v for k,v in row.items() if k!='bank'}) for row in calendar['frames']]
    if transform_gap is not None:
        need(type(transform_gap) is int and transform_gap>=0,'S4_TWO_TRANSFORM_GAP')
        frames=[Frame(f.context,f.generation,f.epoch,f.ordinal,i*(T+transform_gap),f.base)
                for i,f in enumerate(frames)]
    checked=0; peaks=[]
    for inverse in (False,True):
        plan=merged.topology(n,p,inverse=inverse)
        lb=list(range(pw)) if inverse else list(range(aw-1,aw-pw-1,-1))
        tb=list(range(pw,aw)) if inverse else list(range(aw-pw))
        events={f.start+r:[(*f.tag,index_of(r,l,lb,tb)) for l in range(p)] for f in frames for r in range(T)}
        starts={f.start:f.tag for f in frames}
        for s in plan['stages']:
            L=s['shuffle_depth_per_buffer']
            if L:
                pos=s['commutator_lane_position']; pairs=[(l,l^(1<<pos)) for l in range(p) if not l&(1<<pos)]
                queues=[(deque([None]*L),deque([None]*L)) for _ in pairs]
                output={}; active=min(starts); resident=Counter(); peak=live_words=0
                for tick in range(min(events),max(events)+L+1):
                    incoming=events.get(tick)
                    if tick in starts:active=tick
                    phase=((tick-active)//L)&1 if incoming else 0
                    row=[None]*p
                    for (u,v),(uq,lq) in zip(pairs,queues):
                        a,b=uq.popleft(),lq.popleft()
                        for token in (a,b):
                            if token is not None:
                                resident[token[:4]]-=1
                                if not resident[token[:4]]:del resident[token[:4]]
                        x=incoming[u] if incoming else None; y=incoming[v] if incoming else None
                        values=(b if phase else x,y);uq.append(values[0]);lq.append(values[1])
                        for token in values:
                            if token is not None:resident[token[:4]]+=1
                        row[u]=a;row[v]=x if phase else b
                    peak=max(peak,len(resident))
                    live_words=max(live_words,sum(resident.values()))
                    need(sum(resident.values())<=p*L,'S4_TWO_FIFO_CAPACITY')
                    if any(t is not None for t in row):
                        need(all(t is not None for t in row),'S4_TWO_FIFO_PARTIAL_ROW',tick)
                        output[tick+1]=row  # Registered pair output -> next-edge BF accept.
                need(not resident,'S4_TWO_FIFO_DRAIN')
                events=output;starts={edge+L+1:tag for edge,tag in starts.items()}
                peaks.append(dict(direction=plan['direction'],stage=s['stage'],resident_frames=peak,
                    peak_live_words=live_words,allocated_words=p*L))
            lb=s['lane_bits'];tb=s['time_bits']
            need(set(events)=={edge+r for edge in starts for r in range(T)},'S4_TWO_STAGE_EDGES')
            for edge,tag in starts.items():
                for r in range(T):
                    for lane,token in enumerate(events[edge+r]):
                        need(token==(*tag,index_of(r,lane,lb,tb)),'S4_TWO_FIFO_OWNER_ORDER')
                        checked+=1
                    for u,v in s['pairs']:
                        need(events[edge+r][u][-1]^(1<<s['target_index_bit'])==events[edge+r][v][-1],
                             'S4_TWO_BUTTERFLY_PAIR')
            events={edge+6:row for edge,row in events.items()};starts={edge+6:tag for edge,tag in starts.items()}
        for edge,tag in starts.items():
            for row in range(T):
                for lane,wire in enumerate(plan['terminal_wire']):
                    expected=bit_reverse(lane,pw)*T+row if inverse else p*row+lane
                    need(events[edge+row][wire]==(*tag,expected),'S4_TWO_TERMINAL_ORDER')
        need([edge-f.start for edge,f in zip(sorted(starts),frames)]==[plan['first_next_consumer_edge']]*len(frames),
             'S4_TWO_TRANSFORM_LATENCY')
    return dict(n=n,p=p,checked_stage_tokens=checked,shuffle_residency=peaks,
                input_minimum_spacing=T,transform_gap=transform_gap,
                scope='Transform port/ordering proof only; minimum-T gap is NOT a legal shared-carry warm launch.',
                transform_data_FIFO_extra_words=0)


@dataclass(frozen=True)
class SmallImage:
    digits: tuple
    base: int
    c0: tuple
    c1: tuple


def whole_integer(state):
    need(len(state.digits)<=256,'S4_TWO_INTEGER_SMALL_ONLY')
    T=len(state.digits)//len(state.c0); power=1; value=0
    for i,d in enumerate(state.digits):
        value+=d*power
        if i%T==0:value+=state.c0[i//T]*power
        if i%T==1:value+=state.c1[i//T]*power
        power*=state.base
    return value%(power+1)


def integer_digits(value,base,n):
    need(n<=256,'S4_TWO_INTEGER_SMALL_ONLY')
    if value==base**n:return (-1,)+(0,)*(n-1)
    output=[]
    for _ in range(n):value,d=divmod(value,base);output.append(d)
    need(value==0,'S4_TWO_INTEGER_FINAL_RANGE')
    return tuple(output)


def small_reference(n=32,p=8,epochs=4,*,alias_context_banks=False):
    """Three-prime merged reference vs signed schoolbook and whole integer.

    Candidate state remains redundant with both natural-block corrections;
    only independent expected publication uses a whole integer mod b^N+1.
    The alias mutant strips CTX from a table key but keeps output owner tags.
    """
    need(n in (32,256),'S4_TWO_ARITHMETIC_SMALL_ONLY')
    schedule(n,p,epochs)
    bases=(minimum_base(n,p)+17,1009)
    states=[]
    for ctx,base in enumerate(bases):
        digits=[(i*i+(3+ctx)*i+7+11*ctx)%base for i in range(n)]
        digits[n//3+ctx]=-1  # Current signed cold ABI at a nonzero address.
        states.append(SmallImage(tuple(digits),base,(0,)*p,(0,)*p))
    expected=[whole_integer(s) for s in states];checked=coefficients_checked=0;nonzero=0
    for ordinal in range(epochs):
        tables={}
        for ctx,state in enumerate(states):
            key=(ordinal&1,) if alias_context_banks else (ctx,ordinal&1)
            tables[key]=(state.c0,state.c1)
        next_states=[]
        for ctx,state in enumerate(states):
            key=(ordinal&1,) if alias_context_banks else (ctx,ordinal&1)
            c0,c1=tables[key];candidate=SmallImage(state.digits,state.base,c0,c1)
            double=(ordinal+ctx)&1
            got=merged.block_state_square(candidate,double_bit=double)
            effective=list(state.digits);T=n//p
            for lane in range(p):effective[lane*T]+=state.c0[lane];effective[lane*T+1]+=state.c1[lane]
            school=[0]*n
            for i,a in enumerate(effective):
                for j,b in enumerate(effective):school[(i+j)%n]+=a*b*(1 if i+j<n else -1)*(1<<double)
            need(got==school,'S4_TWO_CROSS_TALK' if alias_context_banks else 'S4_TWO_COEFFICIENT_REFERENCE',(ctx,ordinal))
            next_state,_=block.carry_serial(got,state.base,p)
            expected[ctx]=expected[ctx]*expected[ctx]*(1<<double)%(state.base**n+1)
            need(whole_integer(next_state)==expected[ctx],'S4_TWO_CANONICAL_REFERENCE',(ctx,ordinal))
            need(tuple(next_state.canonical())==integer_digits(expected[ctx],state.base,n),
                 'S4_TWO_SIGNED_PUBLICATION',(ctx,ordinal))
            next_states.append(next_state);checked+=n;coefficients_checked+=n
            nonzero+=bool(any(next_state.c0) and any(next_state.c1))
        states=next_states
    return dict(n=n,p=p,contexts=2,epochs_per_context=epochs,
        three_field_schoolbook_coefficients_checked=coefficients_checked,
        signed_canonical_words_checked=checked,both_correction_terms_nonzero_cases=nonzero,
        distinct_bases=list(bases),raw_signed_cold_nonzero_address=True,
        native_run_performed=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n',type=int,default=65536);parser.add_argument('--p',type=int,choices=(8,16),default=8)
    parser.add_argument('--epochs',type=int,default=4)
    parser.add_argument('--correction-latency',type=int)
    parser.add_argument('--correction-pair-interval',type=int,default=2)
    args=parser.parse_args(argv);source_guard()
    result=schedule(args.n,args.p,args.epochs,correction_latency=args.correction_latency,
                    correction_pair_interval=args.correction_pair_interval)
    result['stopped_boundary_buffer']=stopped_context_buffer(args.n,args.p)
    result['interface']=interface()
    if args.n<=256:
        result['literal_FIFO']=fifo_replay(args.n,args.p,args.epochs)
        if args.n in (32,256):result['small_arithmetic']=small_reference(args.n,args.p,args.epochs)
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
