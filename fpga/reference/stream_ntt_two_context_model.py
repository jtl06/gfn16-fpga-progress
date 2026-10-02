"""S5 additive P8 event/protocol proposal; not RTL or physical qualification.

Literal finite FIFO queues carry (context, generation, epoch, index) observers.
Unlike frozen S1, a later frame may enter a shuffle while its predecessor's
tail drains. Only acceptance windows must be disjoint; claiming disjoint
whole-stage residency would be false. No full-size arithmetic is performed.
"""
from collections import Counter, deque
from dataclasses import dataclass
import hashlib
from pathlib import Path

from .stream_ntt_schedule import dimensions, index_of, bit_reverse, m20k
from .stream_ntt_model import ModelMismatch

PINS = {
    'docs/briefs/2026-09-30-trackS-addendum.md': 'df072416273dd272b51740b2c6a42ffe4389437403d147f067792b2634b8b2c7',
    'reference/stream_ntt_blockcarry_schedule.py': 'eca87517cada3413f18313d447b76e1fcf3c3826e70391f3baf39561ab23b632',
    'reference/stream_ntt_schedule.py': '03c1c855e0f6e31f0fcb85d32ed2e604a935e482dfa725d7207e635cb1e963cc',
}


def verify_sources():
    root = Path(__file__).resolve().parents[1]
    for name, digest in PINS.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError('S5 frozen prerequisite changed: ' + name)
    return dict(PINS)


@dataclass(frozen=True)
class Frame:
    context: int
    generation: int
    epoch: int
    start: int

    @property
    def tag(self):
        return self.context, self.generation, self.epoch


def _shuffle(events, starts, width, lane_position, depth, *, mutant=None):
    """One read-old and one write per FIFO per clock, including bubbles.

    Input phase restarts with each dense frame, and is zero in the gap/tail.
    T is divisible by 2L: the old frame needs phase zero throughout its tail,
    which agrees with the first L clocks of the next frame. Thus arbitrary
    nonnegative inter-frame gaps are legal, not just multiples of 2L.
    """
    pairs = [(l, l ^ (1 << lane_position)) for l in range(width)
             if not l & (1 << lane_position)]
    queues = [(deque([None] * depth), deque([None] * depth)) for _ in pairs]
    resident = Counter(); peak_words = peak_frames = 0; output = {}
    active_start = min(starts); first = min(events); last = max(events) + depth
    def remove(token):
        if token is not None:
            resident[token[:3]] -= 1
            if not resident[token[:3]]: del resident[token[:3]]
    def add(token):
        if token is not None: resident[token[:3]] += 1
    for tick in range(first, last + 1):
        incoming = events.get(tick)
        if tick in starts:
            active_start = tick
            if mutant == 'flush-on-frame':
                queues = [(deque([None] * depth), deque([None] * depth)) for _ in pairs]
                resident.clear()
        phase = ((tick - active_start) // depth) & 1 if incoming else 0
        if mutant == 'free-running-phase': phase = ((tick - first) // depth) & 1
        result = [None] * width
        for (upper, lower), (uq, lq) in zip(pairs, queues):
            a, b = uq.popleft(), lq.popleft(); remove(a); remove(b)
            x = incoming[upper] if incoming else None
            y = incoming[lower] if incoming else None
            u = b if phase else x
            uq.append(u); lq.append(y); add(u); add(y)
            result[upper] = a; result[lower] = x if phase else b
        peak_words = max(peak_words, sum(resident.values()))
        peak_frames = max(peak_frames, len(resident))
        if any(t is not None for t in result):
            if any(t is None for t in result):
                raise ModelMismatch('S5-shuffle-valid', str(tick))
            output[tick] = result
    if resident: raise ModelMismatch('S5-shuffle-drain', str(resident))
    return output, dict(allocated_words=width * depth, peak_live_words=peak_words,
                        peak_resident_frames=peak_frames, read_ports_per_FIFO=1,
                        write_ports_per_FIFO=1)


def transform_frames(n, frames, *, inverse=False, mutant=None):
    """All stages, all tagged indices; no modular transforms or data values."""
    p = 8; aw, pw, T = dimensions(n, p)
    if not frames or len({f.tag for f in frames}) != len(frames):
        raise ValueError('unique nonempty frames')
    frames = sorted(frames, key=lambda f: f.start)
    if any(b.start < a.start + T for a, b in zip(frames, frames[1:])):
        raise ModelMismatch('S5-input-overlap', 'two frames demand the same row port')
    lb = list(range(pw)) if inverse else list(range(aw-1, aw-pw-1, -1))
    tb = list(range(pw, aw)) if inverse else list(range(aw-pw))
    events = {f.start+c: [(*f.tag, index_of(c, l, lb, tb)) for l in range(p)]
              for f in frames for c in range(T)}
    starts = {f.start: f.tag for f in frames}; stages = []
    for stage, bit in enumerate(range(aw) if inverse else range(aw-1, -1, -1)):
        incoming_starts = dict(starts); depth = 0
        storage = dict(allocated_words=0, peak_live_words=0, peak_resident_frames=0,
                       read_ports_per_FIFO=0, write_ports_per_FIFO=0)
        if bit not in lb:
            pos = tb.index(bit); depth = 1 << pos
            replace = min(lb) if inverse else max(lb); lane_pos = lb.index(replace)
            events, storage = _shuffle(events, starts, p, lane_pos, depth, mutant=mutant)
            lb[lane_pos], tb[pos] = bit, replace
            events = {edge+1: row for edge, row in events.items()}
            starts = {edge+depth+1: tag for edge, tag in starts.items()}
        expected_edges = {s+c for s in starts for c in range(T)}
        if set(events) != expected_edges:
            raise ModelMismatch('S5-stage-edges', str(stage))
        lp = lb.index(bit)
        for start, tag in starts.items():
            for c in range(T):
                row = events[start+c]
                for l, token in enumerate(row):
                    if token != (*tag, index_of(c, l, lb, tb)):
                        raise ModelMismatch('S5-context-order', str((stage, c, l)))
                    if token[3] ^ (1 << bit) != row[l ^ (1 << lp)][3]:
                        raise ModelMismatch('S5-butterfly-pair', str(stage))
        occupancy = [dict(tag=list(tag), input_first=s, input_last=s+T-1,
                          last_shuffle_output=s+T-1+depth,
                          butterfly_first=s+depth+(1 if depth else 0),
                          butterfly_last_output=s+depth+(1 if depth else 0)+T-1+5)
                     for s, tag in incoming_starts.items()]
        stages.append(dict(stage=stage, target_bit=bit, FIFO_depth=depth,
                           frames=occupancy, **storage))
        events = {edge+6: row for edge, row in events.items()}
        starts = {edge+6: tag for edge, tag in starts.items()}
    final_bits = list(range(aw-1, aw-pw-1, -1)) if inverse else list(range(pw))
    wire = [sum(((l >> j) & 1) << lb.index(b) for j, b in enumerate(final_bits)) for l in range(p)]
    for start, tag in starts.items():
        for c in range(T):
            row = events[start+c]
            for l in range(p):
                index = bit_reverse(l, pw)*T+c if inverse else c*p+l
                if row[wire[l]] != (*tag, index):
                    raise ModelMismatch('S5-terminal-order', str((tag, c, l)))
    return dict(stages=stages, first_next_accept_edges=[dict(tag=list(tag), edge=s)
                for s, tag in starts.items()], tokens_checked=len(frames)*n,
                FIFO_words_per_field=sum(s['allocated_words'] for s in stages))


def schedule(n=65536, epochs=3, *, correction_delay=0, mutant=None):
    """Uniform two-context steady schedule, with explicit finite-frame replay."""
    if n < 32 or n > 65536 or epochs < 2: raise ValueError('AW5..16; >=2 epochs')
    p = 8; aw, pw, T = dimensions(n, p); temporal = aw-pw
    f = 8 + 6*aw + T-1 + temporal
    inverse_start = f+6
    inv_end = inverse_start + 6*aw + T-1 + temporal
    first_digit = inv_end + 4+16+12+12+1
    interval = first_digit+1
    # Odd totals use alternating floor/ceil gaps, rather than rounding per-chain.
    offset = interval//2
    if min(offset, interval-offset) < T:
        raise ModelMismatch('S5-capacity', 'frames overlap')
    frames = [Frame(ctx, 0, epoch, epoch*interval+ctx*offset)
              for epoch in range(epochs) for ctx in range(2)]
    forward = transform_frames(n, [Frame(x.context, x.generation, x.epoch, x.start+8) for x in frames], mutant=mutant)
    inverse = transform_frames(n, [Frame(x.context, x.generation, x.epoch, x.start+inverse_start) for x in frames], inverse=True, mutant=mutant)
    corrections = []; issues = {}; small_issues = set()
    for frame in frames:
        boundary = frame.start + first_digit+T-1+2
        tables = boundary+11+6*pw+correction_delay
        ready = tables+1+min(4,T)-1+3
        next_X = frame.start+interval+f-1
        if ready > next_X:
            raise ModelMismatch('S5-correction-arrival', str((frame.tag, ready, next_X)))
        # Two spatial small-DFT frames; all stages share the same shifted gaps.
        for tick in (boundary+10, boundary+11):
            if tick in small_issues: raise ModelMismatch('S5-small-DFT-port', str(tick))
            small_issues.add(tick)
        # Per-lane multiplier issue stream: four initialization operations,
        # then updates/reseeds for m+4 on each of the first T-4 consumes.
        for tick in [tables+1+c for c in range(min(4,T))] + [next_X+1+m for m in range(max(0,T-4))]:
            if tick in issues: raise ModelMismatch('S5-term-port', str(tick))
            issues[tick] = frame.tag
        corrections.append(dict(tag=list(frame.tag), boundary_ready=boundary,
                                tables_ready=tables, term_ready=ready,
                                next_pointwise_X=next_X, margin=next_X-ready))
    # Every shared non-transform pipeline accepts T rows per frame. Fixed
    # stage offsets preserve nonoverlap; arithmetic latency does not change II.
    resources = dict(extra_transform_data_FIFO_words=0,
        total_transform_data_FIFO_words_all_fields=6*(n-p),
        extra_boundary_correction_signed32_words=2*p,
        extra_small_transform_result_field27_words=6*p,
        extra_term_recurrence_field27_words=12*p,
        extra_carry_history_mixed_width_words=5*p,
        extra_base_bits=32, extra_double_bits=1,
        optional_extra_readback_digit_bits=n*32,
        optional_extra_readback_M20K_shape_count=p*m20k(T,32),
        extra_arithmetic_units_required_by_this_schedule=0,
        unquantified=['per-context cached reciprocal/setup state', 'generation/control tags and reset quarantine',
                     'tag RAM packing if tags travel with every word', 'host canonicalization arbitration'],
        physical_ALM_DSP_M20K_delta_qualified=False)
    return dict(status='S5_conditional_event_model_GO_not_RTL', n=n, p=p,
        epochs_per_context=epochs, per_context_interval=interval,
        aggregate_interval_numerator=interval, aggregate_interval_denominator=2,
        launch_gaps=[offset, interval-offset], forward=forward, inverse=inverse,
        correction_obligations=corrections, resources=resources,
        host_contract=dict(
            active_chain='context stays host-busy across automatic dependent epoch launches; first next input precedes previous last output',
            configuration='base/reciprocal and each epoch double are immutable tagged snapshots; no busy host mutation',
            abort='cancel only selected generation; drain occupied physical slots without FIFO clear or phase rescheduling',
            generation_reuse='do not reuse a finite generation tag until every older token using that tag has drained',
            read_or_partial_load='quiesce selected context, canonicalize complete effective image before host access; retain other context',
            base_change='canonicalize under old base, validate new profile base/digits, clear correction/cache state; rejection requires selected-context reload',
            global_reset='cancels both contexts; distinct from context-local abort/error/reset',
            startup='cold setup and initial corrections must be ready before admission; warm throughput excludes load/readback/reconfiguration'),
        stage_acceptance_overlap=False,
        whole_stage_residency_can_overlap=True,
        minimum_correction_margin=min(c['margin'] for c in corrections),
        scope='Finite tagged FIFO replay, fixed modeled pipeline latencies; no full-size arithmetic, RTL, clock or fit claim')


class ContextBank:
    """Small protocol oracle, integer-valued canonical host boundary.

    Host changes require the selected context idle. Abort/error invalidate that
    generation and require reload; they do NOT flush the shared pipelines.
    Readback/base-change canonicalization is abstract and not zero-cycle.
    This untimed integer transaction oracle does not implement the automatic
    epoch launches inside an active chain (the tagged schedule models those).
    Separate hardware/global reset cancels both contexts. Completed jobs from
    old generations are discarded. Busy selected-context host actions reject.
    """
    def __init__(self, n=32):
        if n < 32 or n > 256 or n & (n-1):
            raise ValueError('protocol integer oracle limited to small N32..256')
        self.n = n
        self.contexts = [dict(generation=0, valid=False, busy=False) for _ in range(2)]

    def _idle(self, ctx):
        state = self.contexts[ctx]
        if state['busy']: raise ModelMismatch('S5-host-busy', str(ctx))
        return state

    def load(self, ctx, digits, base):
        state = self._idle(ctx)
        minimum = max(2*self.n+5, (2*(2*self.n+24*8)+2)//3+1)
        exceptional = list(digits) == [-1]+[0]*(self.n-1)
        if (type(base) is not int or not minimum <= base <= 10**9 or len(digits) != self.n
                or (not exceptional and any(type(x) is not int or not 0 <= x < base for x in digits))):
            raise ValueError('canonical complete load')
        state.update(generation=state['generation']+1, valid=True, base=base,
                     value=sum(x*base**i for i,x in enumerate(digits)) % (base**self.n+1))

    def read(self, ctx):
        state = self._idle(ctx)
        if not state['valid']: raise ModelMismatch('S5-reload-required', str(ctx))
        return state['value']

    def start(self, ctx, double=0):
        state = self._idle(ctx)
        if not state['valid'] or double not in (0,1): raise ModelMismatch('S5-start', str(ctx))
        state['busy'] = True
        return (ctx, state['generation'], state['base'], state['value'], double)

    def complete(self, job):
        ctx, generation, base, value, double = job; state = self.contexts[ctx]
        if generation != state['generation'] or not state['valid']: return False
        if not state['busy'] or base != state['base']: raise ModelMismatch('S5-job-ownership', str(ctx))
        state.update(value=(value*value*(1 << double)) % (base**self.n+1), busy=False)
        return True

    def abort(self, ctx, *, leak=False):
        for target in range(2) if leak else (ctx,):
            state = self.contexts[target]
            state.update(generation=state['generation']+1, valid=False, busy=False)

    def reset_all(self):
        self.abort(0); self.abort(1)

    def change_base(self, ctx, base):
        state = self._idle(ctx); digits = self.canonical_digits(ctx)
        minimum = max(2*self.n+5, (2*(2*self.n+24*8)+2)//3+1)
        if not minimum <= base <= 10**9 or any(d >= base for d in digits):
            self.abort(ctx)
            raise ModelMismatch('S5-base-reload', str(ctx))
        self.load(ctx, digits, base)

    def canonical_digits(self, ctx):
        value = self.read(ctx); old = self.contexts[ctx]['base']
        if value == old**self.n: return [-1]+[0]*(self.n-1)
        digits = []
        for _ in range(self.n): value, digit = divmod(value, old); digits.append(digit)
        return digits

    def load_digit(self, ctx, address, digit):
        # Canonicalize the whole old image before a partial host update.
        digits = self.canonical_digits(ctx); base = self.contexts[ctx]['base']
        if not 0 <= address < self.n or not 0 <= digit < base: raise ValueError('host digit')
        digits[address] = digit
        # Signed exceptional -1 remains an exact integer during this update;
        # normalize before presenting the next canonical host image.
        value = sum(d*base**i for i,d in enumerate(digits)) % (base**self.n+1)
        state = self.contexts[ctx]
        state.update(generation=state['generation']+1, value=value, valid=True)


def abort_isolation(*, mutant=False):
    bank = ContextBank(); a = [3]*32; b = [5]*32
    bank.load(0,a,173); bank.load(1,b,1009)
    ja = bank.start(0); jb = bank.start(1,1)
    bank.abort(0,leak=mutant)
    if bank.complete(ja): raise ModelMismatch('S5-abort-stale', 'A committed')
    if not bank.complete(jb): raise ModelMismatch('S5-abort-leakage', 'B discarded')
    expected = (sum(v*1009**i for i,v in enumerate(b))**2*2) % (1009**32+1)
    if bank.read(1) != expected: raise ModelMismatch('S5-abort-leakage', 'B data changed')
    return True
