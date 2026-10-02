"""D1->D2/T8 native corpus: ideal FIFO control plus independent permutations.

This is transport-only Python preparation; it never invokes HDL tools.
"""
import hashlib
from .stream27_commutator_slots_v2_model import Pipeline, Token, verify_sources
from .stream_ntt_schedule import commutator


def frame(context=0, generation=0, base=0):
    return [tuple(Token(base+2*c+l,context,generation,2*c+l) for l in range(2))
            for c in range(8)]


def event(tokens=None, frame_start=False, reset=False, enabled=(True,True), generations=(0,0)):
    return dict(tokens=tokens,frame_start=frame_start,reset=reset,enabled=enabled,generations=generations)


def legal_case(gap=0, cancel=None, disable=False, reset_age=None):
    """Expected physical tokens are frozen full-frame permutations, not FIFO outputs."""
    origins=[0] if reset_age is None else [0,reset_age+1]
    inputs={};expected={}
    for segment,origin in enumerate(origins):
        for f in range(3):
            start=origin+f*(8+gap);data=frame(f%2,int(f==2)+segment*2,segment*10000+f*1000)
            for c,row in enumerate(data):
                tick=start+c
                if segment or reset_age is None or tick<reset_age:inputs[tick]=(row,c==0)
            transformed=commutator(commutator(data,0,1),0,2)
            for c,row in enumerate(transformed):
                tick=start+4+c
                if segment or reset_age is None or tick<reset_age:expected[tick]=(tuple(row),c==0)
    events=[]
    for tick in range(origins[-1]+3*(8+gap)+6):
        segment=int(reset_age is not None and tick>reset_age)
        third=origins[segment]+2*(8+gap)
        generation=int(tick>=third)+2*segment
        enabled=True
        if cancel is not None and tick>=cancel:
            generation=max(generation,int(cancel>=third)+1+2*segment)
            if disable:enabled=tick>=third and cancel<third
        row,start=inputs.get(tick,(None,False))
        events.append(event(row,start,tick==reset_age,(enabled,True),(generation,2*segment)))
    return events,expected


def cases():
    for gap in (0,1,3,138):
        yield f'gap{gap}',*legal_case(gap)
        for age in range(30):
            for disable in (False,True):
                yield f'gap{gap}-cancel{age}-disable{int(disable)}',*legal_case(gap,age,disable)
    for age in range(30):yield f'reset{age}',*legal_case(reset_age=age)
    data=frame()
    malformed=[ [event(data[0])], [event(frame_start=True)],
                [event(data[0],True),event()],
                [event(data[0],True),event(data[1],True)],
                [event(data[0],True),event(frame(1)[1])],
                [event(data[0],True),event(frame(generation=1)[1])],
                [event(data[c],c==0) for c in range(5)]+[event()] ]
    for i,inputs in enumerate(malformed):
        # These cases intentionally have no independent well-formed frame oracle.
        yield f'malformed{i}',inputs+[event() for _ in range(32)],None


def token_ports(tokens):
    if tokens is None:return [-1]*6
    a,b=tokens
    return [a.data,b.data,a.index,b.index,a.context,a.generation]


def corpus():
    verify_sources()
    lines=[];coverage=[]
    count=dict(events=0,slots=0,commits=0,errors=0,resets=0,before_checks=0,edge_checks=0)
    for label,events,expected in cases():
        pipe=Pipeline(1,2,8,contexts=2,synchronous=False)
        events=[event(reset=True)]+events
        coverage.append(dict(name=label,first_event=len(lines),events=len(events)))
        for local_tick,inputs in enumerate(events):
            out,commit=pipe.edge(**inputs)
            tick=local_tick-1
            if expected is not None:
                want=expected.get(tick) if not inputs['reset'] else None
                if out.error or out.slot_valid != (want is not None):raise AssertionError('SLOTS_VECTOR_PHYSICAL_ORACLE')
                if want and (out.tokens,out.frame_start)!=want:raise AssertionError('SLOTS_VECTOR_TOKEN_ORACLE')
                pending=expected.get(tick-1)
                live=bool(pending and not inputs['reset'] and
                          pending[0][0].generation==inputs['generations'][pending[0][0].context] and
                          inputs['enabled'][pending[0][0].context])
                if commit.valid != live:raise AssertionError('SLOTS_VECTOR_COMMIT_ORACLE')
                if live and (commit.tokens,commit.frame_start)!=pending:raise AssertionError('SLOTS_VECTOR_COMMIT_DATA')
            a,b=inputs['tokens'] if inputs['tokens'] is not None else (None,None)
            row=[int(not inputs['reset']),int(a is not None),int(inputs['frame_start']),
                 a.data if a else 0,b.data if b else 0,a.index if a else 0,b.index if b else 0,
                 a.context if a else 0,a.generation if a else 0,
                 sum(int(v)<<i for i,v in enumerate(inputs['enabled'])),
                 inputs['generations'][0]|(inputs['generations'][1]<<8),
                 -1 if inputs['reset'] else int(out.error),
                 int(out.slot_valid),int(out.frame_start),int(out.eligible),int(out.error),
                 sum(int(v)<<i for i,v in enumerate(out.stage_errors))]
            row+=token_ports(out.tokens if out.slot_valid else None)
            row+=[int(commit.valid),int(commit.frame_start)]
            row+=token_ports(commit.tokens if commit.valid else None)
            if len(row)!=31:raise AssertionError('SLOTS_VECTOR_COLUMNS')
            lines.append(' '.join(map(str,row)))
            for key,value in (('events',1),('slots',out.slot_valid),('commits',commit.valid),
                              ('errors',out.error),('resets',inputs['reset']),('before_checks',2),('edge_checks',1)):
                count[key]+=int(value)
    text=f'SLOTS2 1 2 8 {len(lines)}\n'+'\n'.join(lines)+'\n'
    return text,dict(**count,sha256=hashlib.sha256(text.encode()).hexdigest(),cases=coverage)
