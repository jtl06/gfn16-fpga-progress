"""Pure model for the reserved six-edge stage-shared owner transport seam.

No RTL, numerical NTT or physical claim. Original stage cadence, acceptance,
slot/start flushing and registered aggregate fault authority stay outside the
proposed helper. Invalid GEN presentation is not an occupied transfer.
"""
from dataclasses import dataclass,field

MASK=(1<<25)-1
def owner(frame):return ((frame&1)<<24)|(((65535+frame)&65535)<<8)|((255+frame)&255)

@dataclass
class Literal:
    words:list=field(default_factory=lambda:[0]*6)
    def tick(self,advance,slot,start,gen):
        if advance:self.words=[gen]+self.words[:-1]
    def output(self):return self.words[5]

@dataclass
class Compact:
    frame_t:int
    colors:list=field(default_factory=lambda:[0]*6)
    owners:list=field(default_factory=lambda:[0,0])
    current:int=0
    next_color:int=0
    fallback:Literal=field(default_factory=Literal)
    def reset(self):self.current=0;self.next_color=0
    def tick(self,advance,slot,start,gen):
        if self.frame_t<6:
            self.fallback.tick(advance,slot,start,gen);return
        if not advance:return
        selected=self.next_color if start else self.current
        self.colors=[selected]+self.colors[:-1]
        if slot and start:
            self.owners[selected]=gen;self.current=selected;self.next_color^=1
    def output(self):return self.fallback.output() if self.frame_t<6 else self.owners[self.colors[5]]

class Stage:
    """Literal original cadence/valid/stop model surrounding BOTH transports."""
    def __init__(self,t):
        self.t=t;self.old=Literal();self.new=Compact(t)
        self.valid=[False]*6;self.starts=[False]*6
        self.remaining=0;self.frame_owner=0;self.error=False
        self.checks=self.occupied=self.canceled=self.invalid_difference=self.origins=0
    def observe(self,stop,live):
        valid=self.valid[5] and not stop
        if valid:
            assert self.old.output()==self.new.output(),'occupied/fullowner mismatch'
            self.occupied+=1;self.canceled+=self.old.output()!=live
        elif self.old.output()!=self.new.output():self.invalid_difference+=1
        if self.t<6:assert self.old.output()==self.new.output(),'literal small-T fallback'
        self.checks+=1
    def edge(self,slot,start,gen,*,quarantine=False,reset=False,live=None):
        assert 0<=gen<=MASK
        if live is None:live=gen
        stop=quarantine or self.error
        # PRE-edge consumer sees old dictionary before any same-edge write.
        self.observe(stop or reset,live)
        bad=(start and (not slot or self.remaining!=0)) or (slot and not start and self.remaining==0) or (not slot and self.remaining!=0) or (slot and not start and self.remaining!=0 and gen!=self.frame_owner)
        if bad and not stop and not reset and self.valid[5]:self.origins+=1
        if reset:
            self.valid=[False]*6;self.starts=[False]*6;self.remaining=0;self.error=False
            self.new.reset() # dictionaries and full GEN words deliberately unreset
        else:
            accept=slot and not stop
            # Original GEN transport shifts on idle as well, but freezes at stop.
            self.old.tick(not stop,slot,start,gen);self.new.tick(not stop,slot,start,gen)
            if stop:self.valid=[False]*6;self.starts=[False]*6
            else:
                self.valid=[accept]+self.valid[:-1];self.starts=[accept and start]+self.starts[:-1]
                if accept:
                    if start:self.remaining=self.t-1;self.frame_owner=gen
                    else:self.remaining-=1
                # cadence_bad contributes directly to original stage_pending;
                # aggregate_error captures it on this edge, not six edges later.
                if bad:self.error=True
        self.observe(quarantine or self.error or reset,live)

def run():
    totals=dict(cases=0,edge_comparisons=0,occupied_comparisons=0,canceled_comparisons=0,invalid_presentation_differences=0,fault_origin_preedge_checks=0)
    def count(s):
        totals['cases']+=1;totals['edge_comparisons']+=s.checks;totals['occupied_comparisons']+=s.occupied
        totals['canceled_comparisons']+=s.canceled;totals['invalid_presentation_differences']+=s.invalid_difference;totals['fault_origin_preedge_checks']+=s.origins
    for t in (2,6,8,16,32,4096):
        for gap in (0,1,7):
            for pause in (False,True):
                s=Stage(t);s.edge(False,False,0,reset=True)
                for f in range(5):
                    for row in range(t):
                        g=owner(f)
                        if pause and row==min(2,t-1):
                            for _ in range(3):s.edge(True,row==0,g,quarantine=True)
                        s.edge(True,row==0,g,live=g^(1 if (row+f)%3==0 else 0))
                        assert not s.error
                    for k in range(gap):s.edge(False,False,(f*937+k*13)&MASK)
                for k in range(8):s.edge(False,False,(12345+k)&MASK)
                s.edge(False,False,999,reset=True)
                for row in range(t):s.edge(True,row==0,owner(65536))
                count(s)
        for fault in ('overlap','gap','generation','epoch','context','invalid_start','missing_first'):
            s=Stage(t);s.edge(False,False,0,reset=True)
            # Full preceding frame then mid-next-frame malformed ingress;
            # overlap forces a dictionary write while old tails may be present.
            for i in range(t+min(3,t-1)):
                s.edge(True,i%t==0,owner(i//t));assert not s.error
            slot,start,g=True,False,owner(1)
            if fault=='overlap':start=True
            elif fault=='gap':slot=False
            elif fault=='generation':g^=1
            elif fault=='epoch':g^=1<<8
            elif fault=='context':g^=1<<24
            elif fault=='invalid_start':slot=False;start=True
            elif fault=='missing_first':
                s.edge(False,False,0,reset=True);g=owner(2)
            s.edge(slot,start,g);assert s.error
            for _ in range(8):s.edge(True,False,g)
            s.edge(False,False,0,reset=True);assert not s.error
            for i in range(2*t+8):s.edge(i<2*t,i in (0,t),owner(i//t))
            count(s)
    assert totals['occupied_comparisons'] and totals['canceled_comparisons'] and totals['fault_origin_preedge_checks']
    assert totals['invalid_presentation_differences']>0
    return dict(status='PASS_pure_model_not_RTL',**totals,scope='E5 occupied full25 equality, original cadence/fault authority, pause/reset/wrap/canceled tails; T2 literal fallback. Invalid GEN not guaranteed equal. No RTL/native/resource claim.')

if __name__=='__main__':
    import json
    print(json.dumps(run()))
