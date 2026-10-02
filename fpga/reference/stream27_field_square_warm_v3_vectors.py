"""Independent N32 two-owner/late-correction calendar; no protocol/RTL imports.

Appended columns56..64 preserve the frozen cold FIELD32 schema: epoch input,
correction valid/epoch/generation, physical epoch, commit epoch, owner count,
preedge frame acceptance and correction acceptance. All producer messages must
drain before a finite(epoch,generation) pair is reused; retirement alone is not
a proof that arbitrarily delayed old messages cannot reappear.
"""
from dataclasses import dataclass, replace
import hashlib
from .stream27_field_square_oracle import image_cases, physical_rows, residues


@dataclass
class Descriptor:
    start:int
    epoch:int
    generation:int
    base:int
    correction_edge:int|None=None


class Calendar:
    def __init__(self):self.rows=[];self.cases=[]

    def segment(self,label,frames,correction_edges,*,cancel=None,disable=None,reset_age=None,fault=None):
        inputs={};outputs={};corrections={};origins=[]
        def add_frame(start,epoch,image):
            image.validate();origins.append((start,image.generation))
            for row,(digits,answer) in enumerate(zip(physical_rows(image.digits),residues(image))):
                inputs[start+row]=(True,row==0,image.generation,image.base,digits,epoch)
                outputs[start+87+row]=(row==0,image.generation,answer,epoch)
        for (start,epoch,image),edge in zip(frames,correction_edges):
            add_frame(start,epoch,image)
            if edge is not None:corrections[edge]=(epoch,image.generation,image.c0,image.c1)
        finish=max(start for start,_,_ in frames)+94
        if reset_age is not None:
            inputs={t:r for t,r in inputs.items() if t<reset_age}
            outputs={t:r for t,r in outputs.items() if t<reset_age}
            corrections={t:r for t,r in corrections.items() if t<reset_age}
            origins=[entry for entry in origins if entry[0]<reset_age]
            image=replace(image_cases()[9][1],generation=200)
            add_frame(reset_age+1,4321,image)
            corrections[reset_age+1]=(4321,200,image.c0,image.c1)
            finish=max(finish,reset_age+95)
        first=len(self.rows);owners=[];next_epoch=None;remaining=0;input_generation=0;input_base=0
        last_correction=None;sticky=False;peak=0;accepted_frames=accepted_corrections=0
        self.append(False,False,False,True,0,0,0,(0,)*8,(0,)*8,(0,)*8,-1,None,False,None,
                    0,False,0,0,0,False,False)
        for tick in range(finish):
            reset=tick==reset_age
            slot,start,gen,base,data,epoch=inputs.get(tick,(False,False,0,0,(0,)*8,0))
            if not start:base=0
            corr=corrections.get(tick)
            corr_valid=corr is not None
            corr_epoch,corr_gen,c0,c1=corr if corr else (0,0,(2147483647,)*8,(-2147483648,)*8)
            if fault and tick==fault[0]:
                kind=fault[1]
                if kind=='wrong-correction-epoch':corr_epoch=(corr_epoch+11)&65535
                elif kind=='wrong-correction-generation':corr_gen=(corr_gen+1)&255
                elif kind=='duplicate-correction':
                    image=frames[0][2];corr_valid=True;corr_epoch=frames[0][1];corr_gen=image.generation;c0=image.c0;c1=image.c1
                elif kind=='stale-correction':
                    image=frames[0][2];corr_valid=True;corr_epoch=frames[0][1];corr_gen=image.generation;c0=image.c0;c1=image.c1
                elif kind=='c0-range':c0=(2147483647,)+c0[1:]
                elif kind=='c1-range':c1=(257,)+c1[1:]
                elif kind=='wrong-frame-epoch':epoch=(epoch+7)&65535
                elif kind=='no-start':start=False
                elif kind=='hole':slot=False;start=False
                elif kind=='digit-range':data=(frames[0][2].base,)+data[1:]
                elif kind=='generation':gen=(gen+1)&255
                else:raise ValueError('WARM_FAULT_KIND')
            admitted=[generation for origin,generation in sorted(origins) if origin<=tick]
            live=admitted[-1] if admitted else 0
            if cancel is not None and tick>=cancel:live=250
            enabled=not(disable is not None and tick>=disable)
            digit_bad=((start and (not slot or remaining!=0)) or (slot and not start and remaining==0) or
                (not slot and remaining!=0) or (slot and not start and remaining!=0 and gen!=input_generation))
            if slot:
                chosen_base=base if start else input_base
                digit_bad |= not 172<=chosen_base<=1000000000 or any(not 0<=value<chosen_base for value in data)
            prospective=Descriptor(tick,epoch,gen,base) if slot and start and not digit_bad else None
            bad=bool(digit_bad)
            if prospective:
                bad |= len(owners)>=2 or any(owner.epoch==epoch for owner in owners) or (next_epoch is not None and epoch!=next_epoch)
            corr_owner=None
            if corr_valid:
                candidates=[owner for owner in owners if (owner.epoch,owner.generation)==(corr_epoch,corr_gen)]
                if not candidates and prospective and (epoch,gen)==(corr_epoch,corr_gen):candidates=[prospective]
                if len(candidates)!=1:bad=True
                else:
                    corr_owner=candidates[0]
                    bad |= corr_owner.correction_edge is not None or any(abs(value)>corr_owner.base-1 for value in c0) or any(abs(value)>256 for value in c1)
                bad |= last_correction is not None and tick-last_correction<4
            pw=[owner for owner in owners if 43<=tick-owner.start<47]
            sink=[owner for owner in owners if 88<=tick-owner.start<92]
            bad |= len(pw)>1 or len(sink)>1
            if pw:
                edge=pw[0].correction_edge
                bad |= edge is None or edge+36>=tick
            pending=bool(sticky or bad)
            frame_accept=bool(prospective and not pending and not reset)
            correction_accept=bool(corr_valid and corr_owner and not pending and not reset)
            physical=outputs.get(tick) if not(pending or reset) else None
            previous=outputs.get(tick-1)
            if reset_age is not None and tick-1==reset_age:previous=None
            commit=previous if previous and not(pending or reset) and enabled and previous[1]==live else None
            if reset:
                owners=[];next_epoch=None;remaining=0;input_generation=0;input_base=0;last_correction=None;sticky=False;pending=-1
            else:
                sticky=pending
                if not sticky:
                    if frame_accept:
                        owners.append(prospective);next_epoch=(epoch+1)&65535
                        input_generation=gen;input_base=base;remaining=3;accepted_frames+=1
                    elif slot:remaining-=1
                    if correction_accept:
                        corr_owner.correction_edge=tick;last_correction=tick;accepted_corrections+=1
                    peak=max(peak,len(owners))
                    if sink and tick-sink[0].start==91:owners.remove(sink[0])
            self.append(not reset,slot,start,enabled,gen,live,base,data,c0,c1,pending,physical,sticky,commit,
                        epoch,corr_valid,corr_epoch,corr_gen,len(owners),frame_accept,correction_accept)
        self.cases.append(dict(name=label,first_event=first,events=len(self.rows)-first,peak_owners=peak,
            accepted_frames=accepted_frames,accepted_corrections=accepted_corrections))

    def append(self,rst,slot,start,enabled,gen,live,base,data,c0,c1,pending,physical,error,commit,
               epoch,corr_valid,corr_epoch,corr_gen,owners,frame_accept,correction_accept):
        row=[rst,slot,start,enabled,gen,live,base,*data,*c0,*c1,pending,
            bool(physical),bool(physical and physical[0]),bool(physical and enabled and physical[1]==live),error,
            physical[1] if physical else -1,*(physical[2] if physical else (-1,)*8),
            bool(commit),bool(commit and commit[0]),commit[1] if commit else -1,*(commit[2] if commit else (-1,)*8),
            epoch,corr_valid,corr_epoch,corr_gen,physical[3] if physical else -1,commit[3] if commit else -1,
            owners,frame_accept,correction_accept]
        if len(row)!=65:raise AssertionError('WARM65_SCHEMA')
        self.rows.append(tuple(map(int,row)))

    def result(self):
        text=f'FIELDWARM3 {len(self.rows)}\n'+'\n'.join(' '.join(map(str,row)) for row in self.rows)+'\n'
        return text,dict(events=len(self.rows),slots=sum(r[32] for r in self.rows),commits=sum(r[45] for r in self.rows),
            errors=sum(r[35] for r in self.rows),resets=sum(not r[0] for r in self.rows),
            frame_accepts=sum(r[63] for r in self.rows),correction_accepts=sum(r[64] for r in self.rows),
            peak_owners=max(r[62] for r in self.rows),before_checks=2*len(self.rows),edge_checks=len(self.rows),
            sha256=hashlib.sha256(text.encode()).hexdigest(),cases=self.cases,
            arithmetic_scope='N32 only; direct signed schoolbook. Full-N geometry is not native arithmetic.')


def corpus():
    cases=image_cases();a=replace(cases[9][1],generation=0);b=replace(cases[3][1],generation=0)
    c=replace(cases[10][1],generation=1);calendar=Calendar()
    for label,image in cases:calendar.segment(label,[(0,100,image)],[0])
    for gap,corrgap in ((130,135),(20,25),(4,4)):
        calendar.segment(f'two-owner-start{gap}',[(0,0,a),(gap,1,b)],[0,corrgap])
    calendar.segment('crossed-old-correction-new-base',[(0,0,a),(4,1,b)],[4,9])
    calendar.segment('cohort-change',[(0,0,a),(20,1,c)],[0,25])
    calendar.segment('epoch-wrap',[(0,65535,a),(4,0,b)],[0,4])
    calendar.segment('retire-reuse-bank',[(0,0,a),(4,1,b),(92,2,c)],[0,4,97])
    calendar.segment('warm-three',[(0,0,a),(130,1,b),(260,2,c)],[0,135,265])
    calendar.segment('latest-correction',[(0,0,a)],[6])
    calendar.segment('same-edge-cache-deadline',[(0,0,a)],[7])
    calendar.segment('missing-correction',[(0,0,a)],[None])
    calendar.segment('correction-spacing3',[(0,0,a),(4,1,b)],[4,7])
    calendar.segment('third-owner-overflow',[(0,0,a),(4,1,b),(8,2,c)],[0,4,8])
    for age in (0,4,25,27,28,29,32,36,40,42,43,46,47,50,63,66,87,88,90,91,92,95,107,108,111):
        calendar.segment(f'cancel{age}',[(0,0,a),(20,1,b)],[0,25],cancel=age)
    for age in (0,87,88,91,108):calendar.segment(f'disable{age}',[(0,0,a),(20,1,b)],[0,25],disable=age)
    for age in range(114):calendar.segment(f'reset{age}',[(0,0,a),(20,1,b)],[0,25],reset_age=age)
    for age,kind in ((0,'wrong-correction-epoch'),(0,'wrong-correction-generation'),(0,'c0-range'),
                     (0,'c1-range'),(1,'duplicate-correction'),(92,'stale-correction'),(4,'wrong-frame-epoch'),
                     (0,'no-start'),(1,'hole'),(3,'digit-range'),(1,'generation')):
        calendar.segment(f'fault-{kind}',[(0,0,a),(4,1,b)],[0,4],fault=(age,kind))
    return calendar.result()
