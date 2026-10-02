"""Independent ideal deque and synchronous-read RAM MDC pair event models.

No full-size arithmetic, RTL simulation, or physical RAM inference claim.
Each step is an edge; old RAM read and writes are explicit and separate.
"""
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Token:
    data: int
    context: int
    generation: int
    index: int


class IdealFIFO:
    def __init__(self, depth): self.depth=depth; self.reset()
    def reset(self): self.queue=deque([None]*self.depth)
    def head(self): return self.queue[0]
    def clock(self, value): self.queue.popleft(); self.queue.append(value)


class SyncFIFO:
    """L>=2 registered lookahead read; L1 is an explicit register branch."""
    def __init__(self, depth, mutant=None):
        self.depth=depth; self.memory=[None]*depth; self.mutant=mutant; self.reset()
    def reset(self):
        # Deliberately retain payload RAM. Fill state masks all stale words.
        self.pointer=0; self.filled=0; self.prefetch=None; self.register=None
    def head(self):
        if self.depth==1:return self.register
        return self.prefetch if self.filled==self.depth else None
    def clock(self, value):
        if self.depth==1:self.register=value;return
        address=(self.pointer+1)%self.depth
        if self.mutant=='current-read-address': address=self.pointer
        # Synchronous read samples pre-edge memory; write cannot influence it.
        sampled=self.memory[address]
        self.memory[self.pointer]=value
        self.prefetch=sampled;self.pointer=(self.pointer+1)%self.depth
        self.filled=min(self.depth,self.filled+1)


class Pair:
    def __init__(self, depth, frame_ticks, *, synchronous=False, mutant=None):
        if depth<1 or depth&(depth-1) or frame_ticks<2*depth or frame_ticks%(2*depth):
            raise ValueError('power-of-two L, T multiple of 2L')
        self.depth=depth;self.frame_ticks=frame_ticks;self.mutant=mutant
        factory=(lambda:SyncFIFO(depth,mutant)) if synchronous else (lambda:IdealFIFO(depth))
        self.upper=factory();self.lower=factory();self.remaining=0;self.offset=0
        self.frame_owner=None
        self.output=None;self.valid=False;self.error=False
    def edge(self, pair=None, *, start=False, reset=False, enabled=(True,True), generations=(0,0)):
        if reset:
            self.upper.reset();self.lower.reset();self.remaining=0;self.offset=0
            self.valid=False;self.error=False
            return self.valid,self.error,self.output
        expected_active=bool(self.remaining)
        malformed=(start and (expected_active or pair is None)) or (pair is not None and not(start or expected_active)) or (pair is None and expected_active)
        if pair is not None:
            owners={(t.context,t.generation) for t in pair}
            malformed |= len(owners)!=1 or (expected_active and next(iter(owners))!=self.frame_owner)
        if malformed or self.error:
            self.error=True;self.valid=False
            return self.valid,self.error,self.output
        if start:
            self.offset=0;self.remaining=self.frame_ticks
            self.frame_owner=(pair[0].context,pair[0].generation)
            if self.mutant=='frame-flush':self.upper.reset();self.lower.reset()
        phase=(self.offset//self.depth)&1 if pair is not None else 0
        if self.mutant=='phase-one-early':phase=((self.offset+1)//self.depth)&1 if pair is not None else 0
        a,b=self.upper.head(),self.lower.head()
        x,y=pair if pair is not None else (None,None)
        self.upper.clock(b if phase else x);self.lower.clock(y)
        result=(a,x if phase else b)
        self.valid=False
        if all(t is not None for t in result):
            owners={(t.context,t.generation) for t in result}
            if len(owners)!=1:raise AssertionError('COMM_OWNER_MISMATCH')
            ctx,gen=next(iter(owners))
            eligible=enabled[ctx] and gen==generations[ctx]
            if self.mutant=='global-cancel':eligible=eligible and all(enabled)
            if eligible:self.output=result;self.valid=True
        elif any(t is not None for t in result):raise AssertionError('COMM_PARTIAL_ROW')
        if pair is not None:self.offset+=1;self.remaining-=1
        return self.valid,self.error,self.output


def transactions(depth):
    """Deterministic corpus: gaps, tail resets, two-context cancellation/reload."""
    T=max(8,2*depth); events=[]; serial=0
    def emit(pair=None,start=False,reset=False,enabled=(True,True),generations=(0,0)):
        events.append(dict(pair=pair,start=start,reset=reset,enabled=enabled,generations=generations))
    def frame(ctx=0,gen=0,enabled=(True,True),generations=(0,0),cancel_at=None):
        nonlocal serial
        for i in range(T):
            active=enabled if cancel_at is None or i<cancel_at else (False,True)
            pair=tuple(Token(((serial+1)*104729+l*127)&((1<<27)-1),ctx,gen,i*2+l) for l in range(2))
            emit(pair,start=i==0,enabled=active,generations=generations);serial+=1
    emit(reset=True)
    for gap in (0,1,3,138):
        frame(0)
        for _ in range(gap):emit()
        frame(1)
        for _ in range(depth+1):emit()
    # Cancellation affects eligibility only; all physical slots still run.
    frame(0,cancel_at=T//2);frame(1,enabled=(False,True))
    for _ in range(depth+1):emit(enabled=(False,True))
    frame(0,1,generations=(1,0));frame(1,generations=(1,0))
    for _ in range(depth+1):emit(generations=(1,0))
    # Actual in-flight cancellation at A head, middle, last input and last
    # output, while B immediately follows. Slots/data still traverse memory.
    for cancel in sorted({0,T//2,T-1,T+depth-1}):
        emit(reset=True)
        for tick in range(2*T+depth):
            ctx=tick//T
            pair=tuple(Token((tick+1)*31+l,ctx,0,(tick%T)*2+l) for l in range(2)) if tick<2*T else None
            emit(pair,start=tick in (0,T),generations=(int(tick>=cancel),0))
    # Every phase/address position for bounded small cells; deep cells sample
    # endpoints and both sides of phase/address rollover, not exhaustive 8192.
    ages=range(T+depth) if depth<=16 else sorted({0,1,depth-1,depth,depth+1,T-1,T,T+depth-1})
    for age in ages:
        emit(reset=True)
        for i in range(age):
            pair=tuple(Token(i*2+l,0,0,i*2+l) for l in range(2)) if i<T else None
            emit(pair,start=i==0)
        emit(reset=True)
        for _ in range(depth+1):emit()
    # Malformed cadence quarantines until global reset.
    emit((Token(1,0,0,0),Token(2,0,0,1)),start=False)
    emit();emit(reset=True);frame(1)
    for _ in range(depth+1):emit()
    return T,events


def compare(depth, *, mutant=None):
    T,events=transactions(depth);ideal=Pair(depth,T);sync=Pair(depth,T,synchronous=True,mutant=mutant)
    counts=dict(events=len(events),valid=0,errors=0,resets=0)
    for tick,event in enumerate(events):
        expected=ideal.edge(**event)
        try:actual=sync.edge(**event)
        except AssertionError as error:raise AssertionError(f'COMM_SYNC_MISMATCH tick={tick} {error}') from error
        if actual!=expected:raise AssertionError(f'COMM_SYNC_MISMATCH tick={tick}')
        counts['valid']+=int(actual[0]);counts['errors']+=int(actual[1]);counts['resets']+=int(event['reset'])
    return counts
