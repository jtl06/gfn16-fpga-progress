"""Independent N32 complete-field square event calendar (no RTL/NTT imports)."""
from dataclasses import replace
import hashlib

from .stream27_field_square_oracle import SquareImage, image_cases, physical_rows, residues

FIRST_OUTPUT=87
FRAME_ROWS=4
NEXT_FRAME=92


class Calendar:
    def __init__(self):
        self.lines=[]
        self.cases=[]

    def segment(self,label,frames,*,cancel=None,disable=None,reset_age=None,fault=None):
        """A frame is (first edge, coherent immutable image). No overlap allowed.

        Base/correction pins are intentionally poisoned after row0. The actual
        frame consumes the captured base/corrections, not these later pin values.
        A reset discards the old frame and accepts a coherent reload next edge.
        """
        inputs={};outputs={};origins=[]
        def add_frame(start,image):
            image.validate();origins.append((start,image))
            digit_rows=physical_rows(image.digits);answer=residues(image)
            for row in range(FRAME_ROWS):
                inputs[start+row]=(True,row==0,image.generation,image.base,digit_rows[row],image.c0,image.c1)
                outputs[start+FIRST_OUTPUT+row]=(row==0,image.generation,answer[row])
        for start,image in frames:add_frame(start,image)
        finish=max(start for start,_ in frames)+NEXT_FRAME+2
        if reset_age is not None:
            inputs={tick:data for tick,data in inputs.items() if tick<reset_age}
            outputs={tick:data for tick,data in outputs.items() if tick<reset_age}
            origins=[(start,image) for start,image in origins if start<reset_age]
            image=replace(image_cases()[9][1],generation=200)
            add_frame(reset_age+1,image)
            finish=max(finish,reset_age+1+NEXT_FRAME+2)
        first=len(self.lines)
        self.append(False,False,False,True,0,0,0,(0,)*8,(0,)*8,(0,)*8,-1,None,False,None)
        remaining=0;owner=0;latched_base=0;busy_until=-1;sticky=False
        for tick in range(finish):
            reset=tick==reset_age
            slot,start,generation,base,data,c0,c1=inputs.get(tick,(False,False,0,0,(0,)*8,(0,)*8,(0,)*8))
            if slot and not start:
                # Legal ignored pin changes must not become live range faults.
                base=0;c0=(2147483647,)*8;c1=(-2147483648,)*8
            if fault and tick==fault[0]:
                kind=fault[1]
                if kind=='no-start':start=False
                elif kind=='empty-start':slot=False;start=True
                elif kind=='hole':slot=False;start=False
                elif kind=='restart':start=True
                elif kind=='generation':generation=255
                elif kind in ('busy-start','extra-row'):
                    image=frames[0][1];slot=True;start=kind=='busy-start';generation=image.generation
                    base=image.base;data=physical_rows(image.digits)[0];c0=image.c0;c1=image.c1
                elif kind=='base':base=171
                elif kind=='digit':data=(frames[0][1].base,)+data[1:]
                elif kind=='c0-positive':c0=(base,)+c0[1:]
                elif kind=='c0-negative':c0=(-base,)+c0[1:]
                elif kind=='c1-positive':c1=(257,)+c1[1:]
                elif kind=='c1-negative':c1=(-257,)+c1[1:]
                else:raise ValueError('FIELD_FAULT_KIND')
            active=[image.generation for origin,image in sorted(origins) if origin<=tick]
            live=active[-1] if active else 0
            if cancel is not None and tick>=cancel:live=max(live,250)
            enabled=not(disable is not None and tick>=disable)
            busy=tick<=busy_until
            bad=((start and (not slot or remaining!=0 or busy)) or
                 (slot and not start and remaining==0) or
                 (not slot and remaining!=0) or
                 (slot and not start and remaining!=0 and generation!=owner))
            if slot and start:
                bad |= not 172<=base<=1000000000 or any(abs(x)>base-1 for x in c0) or any(abs(x)>256 for x in c1)
            if slot:
                digit_base=base if start else latched_base
                bad |= any(not 0<=x<digit_base for x in data)
            pending=sticky or bad
            if reset:
                remaining=0;owner=0;latched_base=0;busy_until=-1;sticky=False;pending=-1
            else:
                sticky |= bad
                if slot and not sticky:
                    if start:
                        remaining=FRAME_ROWS-1;owner=generation;latched_base=base;busy_until=tick+NEXT_FRAME-1
                    else:remaining-=1
            physical=outputs.get(tick) if not(sticky or reset) else None
            previous=outputs.get(tick-1)
            if reset_age is not None and tick-1==reset_age:previous=None
            commit=previous if previous and not(reset or pending) and enabled and previous[1]==live else None
            self.append(not reset,slot,start,enabled,generation,live,base,data,c0,c1,pending,physical,sticky,commit)
        self.cases.append(dict(name=label,first_event=first,events=len(self.lines)-first))

    def append(self,reset_n,slot,start,enabled,generation,live,base,data,c0,c1,pending,physical,error,commit):
        row=[reset_n,slot,start,enabled,generation,live,base,*data,*c0,*c1,pending,
             bool(physical),bool(physical and physical[0]),bool(physical and enabled and physical[1]==live),error,
             physical[1] if physical else -1,*(physical[2] if physical else (-1,)*8),
             bool(commit),bool(commit and commit[0]),commit[1] if commit else -1,
             *(commit[2] if commit else (-1,)*8)]
        if len(row)!=56:raise AssertionError('FIELD56_SCHEMA')
        self.lines.append(tuple(map(int,row)))

    def result(self):
        text=f'FIELD32 {len(self.lines)}\n'+'\n'.join(' '.join(map(str,row)) for row in self.lines)+'\n'
        metadata=dict(events=len(self.lines),slots=sum(row[32] for row in self.lines),
            commits=sum(row[45] for row in self.lines),errors=sum(row[35] for row in self.lines),
            resets=sum(not row[0] for row in self.lines),before_checks=2*len(self.lines),edge_checks=len(self.lines),
            sha256=hashlib.sha256(text.encode()).hexdigest(),cases=self.cases,
            first_output=FIRST_OUTPUT,first_commit=FIRST_OUTPUT+1,next_frame=NEXT_FRAME)
        return text,metadata


def corpus():
    calendar=Calendar();images=image_cases()
    for label,image in images:calendar.segment(label,[(0,image)])
    for gap in (0,1,3,138):
        calendar.segment(f'coherent-reload-gap{gap}',[(0,images[3][1]),(NEXT_FRAME+gap,images[9][1])])
    image=replace(images[9][1],generation=0)
    for age in (0,1,3,4,5,8,9,10,27,28,29,32,33,36,42,43,44,45,48,49,83,84,86,87,88,90,91,92):
        calendar.segment(f'cancel{age}',[(0,image)],cancel=age)
    for age in (0,87,88,91):calendar.segment(f'disable{age}',[(0,image)],disable=age)
    for age in range(94):calendar.segment(f'reset{age}',[(0,image)],reset_age=age)
    for age,kind in ((0,'no-start'),(0,'empty-start'),(1,'hole'),(1,'restart'),(1,'generation'),
                     (4,'extra-row'),(10,'busy-start'),(91,'busy-start'),(0,'base'),(0,'digit'),
                     (3,'digit'),(0,'c0-positive'),(0,'c0-negative'),(0,'c1-positive'),(0,'c1-negative')):
        calendar.segment(f'fault-{kind}-{age}',[(0,image)],fault=(age,kind))
    return calendar.result()
