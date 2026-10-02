"""Composable S3 physical-slot interface proposal; no RTL or timing promotion.

Physical slot_valid/frame_start survive cancellation. Eligibility is advisory
at intermediate cells and is rechecked against live generation at commit.
Downstream consumers must NEVER replace slot_valid with eligible.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path

from .stream27_commutator_sync_model import IdealFIFO, SyncFIFO, Token
from .stream_ntt_schedule import commutator, m20k

FROZEN = {
    'reference/stream27_commutator_sync_model.py': '84fa950285704162ed1374bbf53c991abe390e17b21ce557a5a342ae332dd6c5',
    'reference/stream_ntt_schedule.py': '03c1c855e0f6e31f0fcb85d32ed2e604a935e482dfa725d7207e635cb1e963cc',
}


def verify_sources():
    root=Path(__file__).resolve().parents[1]
    for name,digest in FROZEN.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('composable prerequisite changed: '+name)
    return dict(FROZEN)


@dataclass(frozen=True)
class PhysicalRow:
    slot_valid: bool = False
    frame_start: bool = False
    eligible: bool = False
    error: bool = False
    tokens: tuple | None = None


class SlotPair:
    """Finite two-FIFO cell with separate physical and terminal-valid planes."""
    def __init__(self, depth, frame_ticks, *, synchronous=True, contexts=2):
        if depth<1 or depth&(depth-1) or frame_ticks<2*depth or frame_ticks%(2*depth):
            raise ValueError('L power of two and T multiple of 2L')
        if contexts not in (1,2):raise ValueError('CONTEXTS1|2')
        self.depth=depth;self.frame_ticks=frame_ticks;self.contexts=contexts
        factory=SyncFIFO if synchronous else IdealFIFO
        self.upper=factory(depth);self.lower=factory(depth)
        self.remaining=0;self.offset=0;self.output_offset=0
        self.frame_owner=None;self.output_owner=None;self.out=PhysicalRow()

    def edge(self, tokens=None, *, frame_start=False, reset=False,
             enabled=(True,True), generations=(0,0)):
        if reset:
            self.upper.reset();self.lower.reset()
            self.remaining=self.offset=self.output_offset=0
            self.frame_owner=self.output_owner=None
            self.out=PhysicalRow(tokens=self.out.tokens)
            return self.out
        active=bool(self.remaining)
        malformed=((frame_start and (active or tokens is None)) or
                   (tokens is not None and not(frame_start or active)) or
                   (tokens is None and active))
        if tokens is not None:
            if len(tokens)!=2:raise ValueError('two lane tokens')
            owners={(t.context,t.generation) for t in tokens}
            owner=next(iter(owners))
            malformed |= len(owners)!=1 or not 0<=owner[0]<self.contexts or (active and owner!=self.frame_owner)
        if malformed or self.out.error:
            self.out=PhysicalRow(error=True,tokens=self.out.tokens)
            return self.out
        if frame_start:
            self.remaining=self.frame_ticks;self.offset=0;self.frame_owner=owner
        phase=(self.offset//self.depth)&1 if tokens is not None else 0
        a,b=self.upper.head(),self.lower.head()
        x,y=tokens if tokens is not None else (None,None)
        self.upper.clock(b if phase else x);self.lower.clock(y)
        result=(a,x if phase else b)
        if tokens is not None:self.remaining-=1;self.offset+=1
        if any(t is not None for t in result) and not all(t is not None for t in result):
            raise AssertionError('SLOTS_PARTIAL_ROW')
        if result[0] is None:
            self.out=PhysicalRow(tokens=self.out.tokens)
            return self.out
        owners={(t.context,t.generation) for t in result}
        if len(owners)!=1:raise AssertionError('SLOTS_OWNER_MIX')
        owner=next(iter(owners));ctx,gen=owner
        start=self.output_offset==0
        if start:self.output_owner=owner
        elif self.output_owner!=owner:raise AssertionError('SLOTS_FRAME_OWNER')
        self.output_offset=(self.output_offset+1)%self.frame_ticks
        eligible=bool(enabled[ctx] and gen==generations[ctx])
        # Payload updates for every physical row, including killed rows.
        self.out=PhysicalRow(True,start,eligible,False,result)
        return self.out


class TwoCell:
    """Registered output edge E is consumed by cell2 at E+1, not E."""
    def __init__(self, first_depth, second_depth, frame_ticks, *, synchronous=True,
                 contexts=2, broken_link=False, same_edge=False):
        self.first=SlotPair(first_depth,frame_ticks,synchronous=synchronous,contexts=contexts)
        self.second=SlotPair(second_depth,frame_ticks,synchronous=synchronous,contexts=contexts)
        self.broken_link=broken_link;self.same_edge=same_edge

    def edge(self, tokens=None, *, frame_start=False, reset=False,
             enabled=(True,True), generations=(0,0)):
        old=self.first.out
        new=self.first.edge(tokens,frame_start=frame_start,reset=reset,enabled=enabled,generations=generations)
        link=new if self.same_edge else old
        valid=link.eligible if self.broken_link else link.slot_valid
        return self.second.edge(link.tokens if valid else None,
                                frame_start=link.frame_start and valid,
                                reset=reset,enabled=enabled,generations=generations)


def scenario(first_depth=2, second_depth=4, *, gap=0, cancel_age=None, reset_age=None,
             contexts=2, broken_link=False, same_edge=False):
    """Compare all queued outputs against independent frozen-frame transforms.

    Two contexts alternate A/B/A, with reload generation1 on the third frame.
    A cancellation changes generation at the selected edge, never row cadence.
    A global reset interrupts the first segment, then a fresh full segment
    starts on the very next edge. Integer token data only, no NTT arithmetic.
    """
    T=max(8,2*max(first_depth,second_depth));delay=first_depth+1+second_depth
    events=[];expected={};launches=[];cancel_edge=cancel_age
    segment_origins=[0] if reset_age is None else [0,reset_age+1]
    ends=[None] if reset_age is None else [reset_age,None]
    for segment,(origin,end) in enumerate(zip(segment_origins,ends)):
        for epoch in range(3):
            start=origin+epoch*(T+gap);ctx=epoch%contexts;gen=int(epoch>=2)+segment*2
            rows=[tuple(Token((segment+1)*100000+epoch*1000+c*2+l,ctx,gen,c*2+l)
                        for l in range(2)) for c in range(T)]
            if end is not None and start>=end:continue
            launches.append((start,rows,segment))
            transformed=commutator(commutator(rows,0,first_depth),0,second_depth)
            for c,row in enumerate(transformed):
                due=start+delay+c
                if end is None or due<end:expected[due]=(tuple(row),c==0)
    finish=max(start+T+delay for start,_,_ in launches)+1
    inputs={start+c:(row,c==0,segment) for start,rows,segment in launches for c,row in enumerate(rows)
            if reset_age is None or not (segment==0 and start+c>=reset_age)}
    chain=TwoCell(first_depth,second_depth,T,contexts=contexts,broken_link=broken_link,same_edge=same_edge)
    # A global reset defines the segment boundary. Initial construction is the
    # reset state; the optional midstream reset also removes the intercell row.
    physical=eligible=starts=B_rows=0;cancelled_physical=0
    for tick in range(finish):
        reset=tick==reset_age
        segment=int(reset_age is not None and tick>reset_age)
        base_generation=segment*2
        generations=[base_generation,base_generation]
        if cancel_edge is not None and tick>=cancel_edge:generations[0]=base_generation+1
        # New A generation1 is accepted without reusing generation0. No early
        # recycle back to an older generation is admitted by this proposal.
        third=segment_origins[segment]+2*(T+gap)
        if tick>=third:generations[0]=base_generation+1
        source=inputs.get(tick);tokens,start,_=source if source else (None,False,segment)
        out=chain.edge(tokens,frame_start=start,reset=reset,generations=tuple(generations))
        if out.error:raise AssertionError(f'SLOTS_CHAIN_CADENCE tick={tick}')
        want=expected.get(tick)
        if reset:want=None
        if out.slot_valid != (want is not None):raise AssertionError(f'SLOTS_CHAIN_EDGE tick={tick}')
        if want:
            row,first=want;ctx=row[0].context
            should= row[0].generation==generations[ctx]
            if (out.tokens,out.frame_start,out.eligible)!=(row,first,should):
                raise AssertionError(f'SLOTS_CHAIN_DATA_TAG tick={tick}')
            physical+=1;eligible+=int(should);starts+=int(first);B_rows+=int(ctx==1)
            cancelled_physical+=int(not should)
        elif out.frame_start or out.eligible:raise AssertionError('SLOTS_EMPTY_FLAGS')
    return dict(first_depth=first_depth,second_depth=second_depth,T=T,gap=gap,
                delay=delay,physical_rows=physical,eligible_rows=eligible,
                physical_frame_starts=starts,B_rows=B_rows,
                killed_rows_still_transported=cancelled_physical,
                complete_frames_planned=len(launches),contexts=contexts)


def token_width_scenarios(depth=4096):
    """Per-FIFO legal-shape bounds, not inferred RAM counts or integration GO."""
    return dict(
        diagnostic=dict(data=27,payload=16,generation=8,owner=1,slot_valid=1,
                        stored_bits=53,M20K_per_FIFO_shape=m20k(depth,53)),
        proposed_minimal=dict(data=27,payload=1,generation=8,owner=1,slot_valid=1,
                              stored_bits=38,M20K_per_FIFO_shape=m20k(depth,38),adopted=False),
        sidebands=dict(frame_start='regenerated by physical row count; not per-word RAM bit',
                       eligible='advisory output register; never physical downstream valid',
                       killed='logical complement of eligibility on occupied row; not sticky RAM state'),
        caveat='38-bit hypothesis requires reviewed payload semantics and finite generation no-reuse/drain proof. 53 bits exceeds x40. Shape counts are not fitter results.')
