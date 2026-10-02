"""Exact bounded E5/E6 tag transport model; no arithmetic or physical claim."""
from dataclasses import dataclass, field

MASK=(1<<25)-1
def owner(frame):return ((frame&1)<<24)|(((65535+frame)&65535)<<8)|((255+frame)&255)

@dataclass
class Transport:
    depth:int
    frame_t:int
    words:list=field(init=False)
    colors:list=field(init=False)
    owners:list=field(default_factory=lambda:[0,0])
    current:int=0
    next_color:int=0
    def __post_init__(self):
        assert self.depth in (6,7) and self.frame_t>0
        self.words=[0]*self.depth;self.colors=[0]*self.depth
    def reset(self):self.current=0;self.next_color=0
    def tick(self,advance,slot,start,gen):
        if not advance:return
        self.words=[gen]+self.words[:-1]
        selected=self.next_color if start else self.current
        self.colors=[selected]+self.colors[:-1]
        if slot and start:
            self.owners[selected]=gen;self.current=selected;self.next_color^=1
    def literal(self):return self.words[-1]
    def compact(self):
        return self.literal() if self.frame_t<self.depth else self.owners[self.colors[-1]]

class Stage:
    """Original cadence/current owner/checks remain outside the transport."""
    def __init__(self,t,depth):
        self.t=t;self.depth=depth;self.pipe=Transport(depth,t)
        self.valid=[False]*depth;self.starts=[False]*depth
        self.remaining=0;self.frame_owner=0;self.error=False
        self.checks=self.occupied=self.canceled=self.invalid_difference=self.origins=0
    def observe(self,stop,live):
        if self.valid[-1] and not stop:
            assert self.pipe.literal()==self.pipe.compact(),'occupied/fullowner mismatch'
            self.occupied+=1;self.canceled+=self.pipe.literal()!=live
        elif self.pipe.literal()!=self.pipe.compact():self.invalid_difference+=1
        if self.t<self.depth:assert self.pipe.literal()==self.pipe.compact()
        self.checks+=1
    def edge(self,slot,start,gen,*,quarantine=False,reset=False,live=None):
        assert 0<=gen<=MASK
        if live is None:live=gen
        stop=quarantine or self.error
        self.observe(stop or reset,live)
        bad=(start and (not slot or self.remaining!=0)) or (slot and not start and self.remaining==0) or (not slot and self.remaining!=0) or (slot and not start and self.remaining!=0 and gen!=self.frame_owner)
        if bad and not stop and not reset and self.valid[-1]:self.origins+=1
        if reset:
            self.valid=[False]*self.depth;self.starts=[False]*self.depth
            self.remaining=0;self.error=False;self.pipe.reset()
        else:
            accept=slot and not stop
            self.pipe.tick(not stop,accept,start,gen)
            if stop:self.valid=[False]*self.depth;self.starts=[False]*self.depth
            else:
                self.valid=[accept]+self.valid[:-1];self.starts=[accept and start]+self.starts[:-1]
                if accept:
                    if start:self.remaining=self.t-1;self.frame_owner=gen
                    else:self.remaining-=1
                if bad:self.error=True
        self.observe(quarantine or self.error or reset,live)

def run():
    totals=dict(cases=0,edge_comparisons=0,occupied_comparisons=0,canceled_comparisons=0,invalid_presentation_differences=0,fault_origin_preedge_checks=0)
    def count(s):
        for key,value in [('cases',1),('edge_comparisons',s.checks),('occupied_comparisons',s.occupied),('canceled_comparisons',s.canceled),('invalid_presentation_differences',s.invalid_difference),('fault_origin_preedge_checks',s.origins)]:totals[key]+=value
    for depth in (6,7):
      for t in (2,6,7,8,16,32,4096):
        for gap in (0,1,7):
          for pause in (False,True):
            s=Stage(t,depth);s.edge(False,False,0,reset=True)
            for f in range(5):
                for row in range(t):
                    g=owner(f)
                    if pause and row==min(2,t-1):
                        for _ in range(3):s.edge(True,row==0,g,quarantine=True)
                    s.edge(True,row==0,g,live=g^(1 if (row+f)%3==0 else 0));assert not s.error
                for k in range(gap):s.edge(False,False,(f*937+k*13)&MASK)
            for k in range(depth+2):s.edge(False,False,(12345+k)&MASK)
            s.edge(False,False,999,reset=True)
            for row in range(t):s.edge(True,row==0,owner(65536))
            count(s)
        for fault in ('overlap','gap','generation','epoch','context','invalid_start','missing_first'):
            s=Stage(t,depth);s.edge(False,False,0,reset=True)
            for i in range(t+min(3,t-1)):
                s.edge(True,i%t==0,owner(i//t));assert not s.error
            slot,start,g=True,False,owner(1)
            if fault=='overlap':start=True
            elif fault=='gap':slot=False
            elif fault=='generation':g^=1
            elif fault=='epoch':g^=1<<8
            elif fault=='context':g^=1<<24
            elif fault=='invalid_start':slot=False;start=True
            elif fault=='missing_first':s.edge(False,False,0,reset=True);g=owner(2)
            s.edge(slot,start,g);assert s.error
            for _ in range(depth+2):s.edge(True,False,g)
            s.edge(False,False,0,reset=True);assert not s.error
            for i in range(2*t+depth+2):s.edge(i<2*t,i in (0,t),owner(i//t))
            count(s)
    assert min(totals[k] for k in totals)>0
    return dict(status='PASS_pure_model_not_RTL',**totals,depths=[6,7],scope='Occupied/canceled full25 E5/E6 and preedge fault-origin; T<depth literal fallback; invalid GEN not authority; no native/resource claim.')

if __name__=='__main__':
    import json
    print(json.dumps(run()))
