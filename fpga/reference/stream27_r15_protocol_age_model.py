"""Modular lookup invariant; no native billions of edges or fault immunity.

For every VALID bank, q == cycle_count - first (mod 2**32). Allocation:
(c+1)-(c+FIRST) == 1-FIRST. Live tick: (c+1)-first == q+1.
Retire/reset remove the validity obligation; a later allocation reinitializes.
This induction is independent of c/FIRST, elapsed lifetime, and stop. It does
not justify shortening the counter, freezing on stop or changing retirement.
"""
from dataclasses import dataclass
import random

MASK=(1<<32)-1


def u32(x):return x&MASK


@dataclass
class Bank:
    valid: bool=False
    first_pw: int=0
    first_sink: int=0
    q_pw: int=0
    q_sink: int=0


class Ages:
    def __init__(self,pw_first,sink_first,rows=16,banks=4,cycle=0):
        if not 0<=pw_first<=MASK or not 0<=sink_first<=MASK or rows<2 or banks not in (2,4):
            raise ValueError('R15_AGE_GEOMETRY')
        self.pw,self.sink,self.rows=pw_first,sink_first,rows
        self.cycle=u32(cycle);self.banks=[Bank() for _ in range(banks)]

    def check(self):
        for b in self.banks:
            if b.valid:
                if (b.q_pw,b.q_sink)!=(u32(self.cycle-b.first_pw),u32(self.cycle-b.first_sink)):
                    raise ValueError('R15_AGE_INVARIANT')
        return True

    def outputs(self):
        self.check()
        old_pw=[(i,u32(self.cycle-b.first_pw)) for i,b in enumerate(self.banks)
                if b.valid and u32(self.cycle-b.first_pw)<self.rows]
        new_pw=[(i,b.q_pw) for i,b in enumerate(self.banks) if b.valid and b.q_pw<self.rows]
        old_sink=[(i,u32(self.cycle-b.first_sink)) for i,b in enumerate(self.banks)
                  if b.valid and u32(self.cycle-b.first_sink)<self.rows]
        new_sink=[(i,b.q_sink) for i,b in enumerate(self.banks) if b.valid and b.q_sink<self.rows]
        old_next=[(i,u32(self.cycle+1-b.first_pw)) for i,b in enumerate(self.banks)
                  if b.valid and u32(self.cycle+1-b.first_pw)<self.rows]
        new_next=[(i,u32(b.q_pw+1)) for i,b in enumerate(self.banks)
                  if b.valid and u32(b.q_pw+1)<self.rows]
        if (old_pw,old_sink,old_next)!=(new_pw,new_sink,new_next):raise ValueError('R15_AGE_LOOKUP')
        return new_pw,new_sink,new_next

    def edge(self,*,allocate=None,retire=None,stop=False,reset=False,allocation_offset=1,freeze_on_stop=False):
        self.check()
        if reset:
            self.cycle=0
            for b in self.banks:b.valid=False
            return self.check()  # reset-free q bits are invalid/don't-care
        old_cycle=self.cycle;old_valid=[b.valid for b in self.banks]
        if allocate is not None and (stop or old_valid[allocate]):raise ValueError('R15_AGE_ILLEGAL_ACCEPT')
        if retire is not None and not old_valid[retire]:raise ValueError('R15_AGE_ILLEGAL_RETIRE')
        self.cycle=u32(self.cycle+1)
        for b in self.banks:
            if b.valid and not(stop and freeze_on_stop):
                b.q_pw=u32(b.q_pw+1);b.q_sink=u32(b.q_sink+1)
        if not stop:
            if allocate is not None:
                b=self.banks[allocate];b.valid=True
                b.first_pw=u32(old_cycle+self.pw);b.first_sink=u32(old_cycle+self.sink)
                b.q_pw=u32(allocation_offset-self.pw);b.q_sink=u32(allocation_offset-self.sink)
            # Canceled live generation/enabled flag does NOT affect raw retire.
            if retire is not None:self.banks[retire].valid=False
        return self.check()

    def elapsed(self,delta):
        """Scalar repeated live ticks only; NOT forcing native RTL clock/counters."""
        if type(delta) is not int or delta<0:raise ValueError('R15_AGE_ELAPSED')
        self.cycle=u32(self.cycle+delta)
        for b in self.banks:
            if b.valid:b.q_pw=u32(b.q_pw+delta);b.q_sink=u32(b.q_sink+delta)
        self.check();return self.outputs()


def prove(seed=0x15a9e):
    # Exhaustive reduced-width representatives demonstrate the same modular
    # allocation/induction identities; the algebra above is width-independent.
    checked=0
    for c in range(256):
        for first in range(256):
            assert ((c+1-(c+first))&255)==((1-first)&255)
            assert ((c+1-first)&255)==(((c-first)&255)+1)&255
            checked+=2
    rng=random.Random(seed);edges=0;jumps=0
    for pw,sink,rows in ((79,153,16),(4207,8417,4096),(2,7,2),(MASK-1,MASK,2)):
        for c in (0,1,MASK-1,MASK,0x80000000):
            t=Ages(pw,sink,rows,cycle=c)
            for tick in range(1000):
                invalid=[i for i,b in enumerate(t.banks) if not b.valid]
                live=[i for i,b in enumerate(t.banks) if b.valid]
                stop=rng.randrange(7)==0
                alloc=rng.choice(invalid) if invalid and not stop and rng.randrange(3)==0 else None
                retire=rng.choice(live) if live and rng.randrange(3)==0 else None
                t.edge(allocate=alloc,retire=retire,stop=stop,reset=tick%193==192)
                t.outputs();edges+=1
                if tick%101==100:
                    t.elapsed((1<<32)*rng.randrange(1,4)+rng.randrange(256));jumps+=1
    return dict(algebra='VALID q == cycle-first modulo2**32; allocation1-FIRST; unconditional live tick',
      reduced_width_identity_checks=checked,bounded_edges=edges,scalar_fullwidth_elapsed_jumps=jumps,
      stop_ticks_included=True,reset_free_invalid_ages=True,payload_next_delta=1,
      native_RTL=False,billions_of_native_edges=False,clock_area_claim=False)
