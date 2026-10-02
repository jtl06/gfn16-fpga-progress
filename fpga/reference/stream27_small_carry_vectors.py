"""Native component vectors from pinned ordinary-integer divmod oracle only."""
import hashlib
import random
from .stream27_small_carry_oracle import Cell,bounds,geometry


def corpus(aw,feedback_length=4096):
    if aw not in (5,16) or type(aw) is not int:raise ValueError('explicit AW5 or AW16 profile')
    if type(feedback_length) is not int or not 1<=feedback_length<=4096:raise ValueError('bounded feedback length')
    p=8;cell=Cell(aw,p,16);minimum=geometry(aw,p)['minimum_base'];rows=[]
    counts=dict(events=0,good=0,errors=0,bubbles=0,resets=0,feedback=0,carry_mask=0)
    def emit(y=0,carry=0,base=minimum,valid=True,start=False,reset=False,feedback=False):
        if feedback:carry=cell.out.carry
        tag=(len(rows)*40503+12345)&65535
        out=cell.edge(y=y,carry=carry,base=base,payload=tag,valid=valid,block_start=start,rst_n=not reset)
        row=(int(not reset),int(valid),int(start),base,y,carry,int(feedback),tag,
             int(out.valid),int(out.error),-1 if out.digit is None else out.digit,out.carry,
             -1 if out.payload is None else out.payload)
        rows.append(row);counts['events']+=1;counts['feedback']+=int(feedback)
        if reset:counts['resets']+=1
        elif not valid:counts['bubbles']+=1
        elif out.valid:counts['good']+=1;counts['carry_mask']|=1<<(out.carry+2)
        else:counts['errors']+=1
    emit(y=-(1<<32),carry=-4,base=0,reset=True)
    emit(y=(1<<32)-1,carry=-3,base=0xffffffff,valid=False)
    emit(start=True)
    # Complete admitted y x six-state domain at the small profile's eight
    # lowest bases. This is only40,608 cases; no full-N transform is performed.
    if aw==5:
        for base in range(minimum,minimum+8):
            q=bounds(aw,p,base)
            for carry in range(-2,4):
                for y in range(q['y_min'],q['y_max']+1):emit(y,carry,base)
    for base in (minimum,minimum+1,604832956,999999999,10**9):
        q=bounds(aw,p,base)
        for carry in range(-4,4):
            ys={q['y_min']-1,q['y_min'],q['y_max'],q['y_max']+1,-(1<<32),(1<<32)-1,-1,0,1,base-1,base}
            for threshold in range(-2,5):ys.update(threshold*base+delta-carry for delta in (-1,0,1))
            for y in sorted(x for x in ys if -(1<<32)<=x<(1<<32)):
                emit(y,carry,base)
            for y in (-1,0,base-1,base):emit(y,carry,base,start=True)
    for base in (0,1,minimum-1,10**9+1,0xffffffff):
        for carry in range(-4,4):emit(0,carry,base,start=True)
    for base in (minimum,10**9):
        emit(y=-(1<<32),carry=-4,base=0,reset=True)
        emit(y=base-1,carry=3,base=base,start=True) # immediate valid release
        emit(valid=False)
    rng=random.Random(20260930+aw)
    for base in (minimum,minimum+1,604832956,10**9):
        q=bounds(aw,p,base);restart=True
        for i in range(feedback_length):
            if i%257==0:
                emit(y=-(1<<32),carry=-4,base=0,reset=True)
                emit(y=(1<<32)-1,carry=-3,base=0xffffffff,valid=False);restart=True
            if i%17==0:emit(y=-(1<<32),carry=-4,base=0,valid=False)
            start=restart or i%29==0
            y=rng.randrange(base) if start else rng.randrange(q['y_min'],q['y_max']+1)
            emit(y,base=base,start=start,feedback=True);restart=False
            if i%113==0:emit(y=0,base=10**9+1,feedback=True)
    emit(reset=True);emit(valid=False)
    assert counts['events']==sum(counts[k] for k in ('good','errors','bubbles','resets'))
    assert counts['carry_mask']==63
    text=f'SCELL1 {aw} {p} 16 {len(rows)}\n'+'\n'.join(' '.join(map(str,row)) for row in rows)+'\n'
    return text,dict(aw=aw,p=p,payload_w=16,feedback_length=feedback_length,**counts,
                    before_checks=2*len(rows),edge_checks=len(rows),sha256=hashlib.sha256(text.encode()).hexdigest())
