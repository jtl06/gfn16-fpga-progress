"""Native vectors from the ideal deque oracle, not synchronous RAM candidate."""
import hashlib
from .stream27_commutator_sync_model import Pair, transactions


def corpus(depth):
    if depth not in (1,2,4,16,4096):raise ValueError('bounded explicit L profiles')
    T,events=transactions(depth);oracle=Pair(depth,T);rows=[]
    count=dict(depth=depth,frame_ticks=T,events=len(events),valid=0,errors=0,resets=0,
               before_checks=2*len(events),edge_checks=len(events))
    for event in events:
        valid,error,result=oracle.edge(**event)
        pair=event['pair'];a,b=pair if pair else (None,None)
        row=[int(not event['reset']),int(pair is not None),int(event['start']),
             a.data if a else 0,b.data if b else 0,a.index if a else 0,b.index if b else 0,
             a.context if a else 0,a.generation if a else 0,
             sum(int(v)<<i for i,v in enumerate(event['enabled'])),
             event['generations'][0]|(event['generations'][1]<<8),int(valid),int(error)]
        row+=([result[0].data,result[1].data,result[0].index,result[1].index,
               result[0].context,result[0].generation] if result else [-1]*6)
        rows.append(' '.join(map(str,row)))
        count['valid']+=int(valid);count['errors']+=int(error);count['resets']+=int(event['reset'])
    text=f'COMM1 {depth} {T} {len(events)}\n'+'\n'.join(rows)+'\n'
    return text,dict(**count,sha256=hashlib.sha256(text.encode()).hexdigest())
