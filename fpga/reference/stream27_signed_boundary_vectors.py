"""Frozen deterministic corpus from independent integer modulo/D4 queues."""
import hashlib
import random
from .stream27_signed_boundary_oracle import FIELDS,Pipeline,evaluate,geometry


def corpus(aw,random_count=8192):
    if type(aw) is not int or aw not in (5,16):raise ValueError('explicit AW5 orAW16')
    if type(random_count) is not int or not 1<=random_count<=8192:raise ValueError('bounded random count')
    blocks=8;_,k,minimum=geometry(aw,blocks);models=[Pipeline(aw,blocks,p) for p in FIELDS]
    rows=[];counts=dict(events=0,accepted=0,responses=0,errors=0,bubbles=0,resets=0,output_idle=0)
    typed=dict(accepted_good=0,accepted_error=0,discarded_good=0,discarded_error=0,
        negative_zero_inputs=0,c0_inputs=0,c1_inputs=0,int_min_rejections=0,reset_ages=0)
    def emit(x=0,kind=0,base=minimum,valid=True,reset=False):
        wire=x&0xffffffff;tag=(len(rows)*40503+12345)&65535
        if reset:
            for token in models[0].queue:
                if token is not None:typed['discarded_error' if token[0]['error'] else 'discarded_good']+=1
        elif valid:
            result=evaluate(wire,kind,base,aw=aw,blocks=blocks,p=FIELDS[0])
            typed['accepted_error' if result['error'] else 'accepted_good']+=1
            typed['c1_inputs' if kind else 'c0_inputs']+=1
            if not result['error'] and x<0 and any(x%p==0 for p in FIELDS):typed['negative_zero_inputs']+=1
            if x==-2147483648 and result['error']:typed['int_min_rejections']+=1
        outputs=[m.edge(in_valid=valid,word=wire,boundary_high=kind,base=base,payload=tag,rst_n=not reset) for m in models]
        common=outputs[0]
        assert all((out['out_valid'],out['out_error'],out['payload'])==(common['out_valid'],common['out_error'],common['payload']) for out in outputs)
        rows.append((int(not reset),int(valid),kind,base,wire,tag,int(common['out_valid']),int(common['out_error']),
            *(out['residue'] for out in outputs),common['payload']))
        counts['events']+=1;counts['responses']+=common['out_valid'];counts['errors']+=common['out_error'];counts['output_idle']+=not(common['out_valid'] or common['out_error'])
        if reset:counts['resets']+=1
        else:counts['accepted']+=valid;counts['bubbles']+=not valid
    emit(reset=True);emit(valid=False)
    for base in (minimum,minimum+1,604832956,1_000_000_000):
        for kind,limit in ((0,base-1),(1,k)):
            for x in sorted({-limit-1,-limit,-1,0,1,limit,limit+1,-2147483648,2147483647}):emit(x,kind,base)
    for p in FIELDS:
        for multiple in range(1,17):
            for delta in (-1,0,1):
                value=multiple*p+delta
                if value<=999999999:
                    emit(value,0,1_000_000_000);emit(-value,0,1_000_000_000)
    for base in (0,1,minimum-1,1_000_000_001,0xffffffff):
        for kind in (0,1):
            for x in (-2147483648,-1,0,1,2147483647):emit(x,kind,base)
    for age in range(5):
        for invalid in (False,True):
            emit(reset=True);emit(-2147483648 if invalid else -FIELDS[0],0,1_000_000_000)
            for _ in range(age):emit(valid=False)
            emit(reset=True);typed['reset_ages']|=1<<age
            emit(-1,0,1_000_000_000) # immediate restart
            for _ in range(6):emit(valid=False)
    rng=random.Random(0xB0322026+aw)
    for index in range(random_count):
        if index%257==0:emit(reset=True)
        if index%17==0:emit(-2147483648,kind=1,base=0xffffffff,valid=False)
        kind=rng.randrange(2);base=rng.choice((minimum,minimum+1,604832956,1_000_000_000));limit=k if kind else base-1
        x=rng.randrange(-limit,limit+1) if index%19 else rng.choice((-limit-1,limit+1,-2147483648,2147483647))
        emit(x,kind,base)
    for _ in range(6):emit(valid=False)
    assert counts['responses']==typed['accepted_good']-typed['discarded_good']
    assert counts['errors']==typed['accepted_error']-typed['discarded_error']
    assert typed['reset_ages']==31 and typed['negative_zero_inputs']>0 and typed['int_min_rejections']>0
    text=f'SBRED1 {aw} {blocks} 16 {len(rows)}\n'+'\n'.join(' '.join(map(str,row)) for row in rows)+'\n'
    return text,dict(aw=aw,blocks=blocks,payload_w=16,random_count=random_count,fields=list(FIELDS),**counts,
        before_checks=2*len(rows),edge_checks=len(rows),field_checks=3*len(rows),typed_coverage=typed,
        sha256=hashlib.sha256(text.encode()).hexdigest())
