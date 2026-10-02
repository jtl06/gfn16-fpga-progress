"""Scalar corpus/model for the additive lazy28 butterfly; no native execution."""
import hashlib
from itertools import product
from pathlib import Path
import random

ROOT=Path(__file__).resolve().parents[1]
MULTIPLIER='rtl/kernel/genefer_montgomery_mul28x27_sparse_pipe_v2.sv'
MULTIPLIER_SHA='a93cb002eb08e585e62a847ef4b070175ae8108919da30ea5bf67dad3a597026'
FIELDS=(104857601,69206017,67239937)
RTL='rtl/kernel/genefer_ntt_lazy28_butterfly_v1.sv'
LATENCY=5


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def butterfly(u,v,w,p,gs):
    """Ordinary integer oracle: no sparse multiplication or REDC recurrence."""
    assert p in FIELDS and 0<=u<2*p and 0<=v<2*p and 0<=w<p
    mont=lambda x:x*w*pow(1<<32,-1,p)%p
    if gs:return (u+v)%(2*p),mont((u-v)%(2*p))
    uc=u%p;t=mont(v)
    return uc+t,uc+p-t


def mutant(text,role):
    changes={
        'truncate-high-bit':('pre_v<=gs ? gs_diff_fold : v;',"pre_v<=gs ? gs_diff_fold : {1'b0,v[26:0]};"),
        'missing-ct-precorrection':("wire [27:0] ct_u=u>=28'(P) ? u-28'(P) : u;","wire [27:0] ct_u=u;"),
        # Common wrong threshold: fold only on bit28, missing [2P,2^28).
        # All29 input bits remain consumed, so -Wall must still pass this mutant.
        'missing-gs-fold':("wire [27:0] gs_sum_fold=28'(gs_sum>=TWO_P ? gs_sum-TWO_P : gs_sum);","wire [27:0] gs_sum_fold=gs_sum[28] ? 28'(gs_sum-TWO_P) : gs_sum[27:0];"),
        'wrong-tag-latency':('out_tag<=tag_pipe[4];','out_tag<=tag_pipe[4]^tag_pipe[3];'),
        'early-valid':('out_valid<=product_valid;','out_valid<=pre_valid;'),
    }
    old,new=changes[role]
    if text.count(old)!=1:raise ValueError('ambiguous mutant anchor')
    return text.replace(old,new)


def events(p,role='control'):
    """(reset_n, valid, gs, u, v, w, tag); explicit ordering, deterministic."""
    r=(1<<32)%p
    stream=[(0,1,0,2*p-1,2*p-1,p-1,999),(1,0,0,0,0,0,0)]
    witness={
        'truncate-high-bit':(0,0,1<<27,r),
        'missing-ct-precorrection':(0,p,0,0),
        'missing-gs-fold':(1,p,p,0),
        'wrong-tag-latency':(0,7,11,r),
        'early-valid':(0,7,11,r),
    }
    if role!='control':
        gs,u,v,w=witness[role];stream.append((1,1,gs,u,v,w,17))
        stream.extend((1,0,0,0,0,0,100+i) for i in range(8))
        return stream
    tag=0
    # Every negative-control witness is also included in the positive corpus.
    triples=list(witness.values())
    values=sorted({0,1,p-1,p,p+1,2*p-2,2*p-1,(1<<27)-1,1<<27,(1<<27)+1})
    values=[x for x in values if 0<=x<2*p]
    for gs,u,v,w in product((0,1),values,values,(0,1,r,p-1)):
        triples.append((gs,u,v,w))
    rng=random.Random(0x281927+p)
    triples.extend((rng.randrange(2),rng.randrange(2*p),rng.randrange(2*p),rng.randrange(p)) for _ in range(4000))
    for index,(gs,u,v,w) in enumerate(triples):
        tag+=1;stream.append((1,1,gs,u,v,w,tag))
        if index%7==0:stream.append((1,0,not gs,2*p-1,0,p-1,0xf0000000+index))
        if index%113==37:stream.append((0,1,gs,u,v,w,tag))
    stream.extend((1,0,0,0,0,0,0) for _ in range(8))
    for occupancy in range(1,7):
        for _ in range(occupancy):
            tag+=1;stream.append((1,1,tag&1,2*p-1,p,r,tag))
        stream.append((0,1,1,2*p-1,2*p-1,p-1,tag))
        stream.extend((1,0,0,0,0,0,0) for _ in range(7))
        tag+=1;stream.append((1,1,0,p,1<<27,r,tag))
        stream.extend((1,0,0,0,0,0,0) for _ in range(7))
    return stream


def coverage(stream,p):
    pending=[];checked=cancelled=high=ct=gs=0
    for edge,(reset,valid,form,u,v,w,tag) in enumerate(stream):
        if not reset:cancelled+=len(pending);pending=[];continue
        if valid:
            y=butterfly(u,v,w,p,form)
            assert all(0<=x<2*p for x in y)
            residues=((u+v*w*pow(1<<32,-1,p))%p,(u-v*w*pow(1<<32,-1,p))%p) if not form else ((u+v)%p,((u-v)*w*pow(1<<32,-1,p))%p)
            assert tuple(x%p for x in y)==residues
            pending.append((edge+LATENCY,tag));high+=int(bool(u>>27 or v>>27));gs+=int(bool(form));ct+=int(not form)
        if pending and pending[0][0]==edge:pending.pop(0);checked+=1
    assert not pending
    return dict(events=len(stream),checked=checked,cancelled=cancelled,high_inputs=high,ct=ct,gs=gs)


def replay_pipeline(stream,p):
    """Explicit nonblocking pre/multiply/output stage replay, independent queue.

    Multiplier arithmetic is ordinary modular multiplication (native v2 is a
    separately pinned prerequisite); this checks butterfly transport only.
    """
    prefix=[0]*5;tags=[0]*5;forms=[0]*5
    pre=(False,0,0);mult=[(False,0)]*4
    output=(False,0,0,0);pending=[];checked=0
    for edge,(reset,valid,gs,u,v,w,tag) in enumerate(stream):
        if not reset:
            prefix=[0]*5;tags=[0]*5;forms=[0]*5;pre=(False,0,0);mult=[(False,0)]*4
            output=(False,0,0,0);pending=[];continue
        if valid:pending.append((edge+5,*butterfly(u,v,w,p,gs),tag))
        due=bool(pending and pending[0][0]==edge)
        product_valid,product=mult[3]
        if product_valid:
            output=(True,prefix[4] if forms[4] else prefix[4]+product,
                    product if forms[4] else prefix[4]+p-product,tags[4])
        else:output=(False,*output[1:])
        self_product=pre[1]*pre[2]*pow(1<<32,-1,p)%p
        mult=[(pre[0],self_product)]+mult[:3]
        total=u+v;difference=u+2*p-v
        folded_sum=total-2*p if total>=2*p else total
        folded_diff=difference-2*p if difference>=2*p else difference
        pre=(bool(valid),folded_diff if gs else v,w)
        prefix=[folded_sum if gs else (u-p if u>=p else u)]+prefix[:4]
        forms=[gs]+forms[:4];tags=[tag]+tags[:4]
        assert output[0]==due,(edge,output,pending[:1])
        if due:
            wanted=pending.pop(0);assert output[1:]==wanted[1:];checked+=1
    assert not pending
    return checked


def corpus(p,role='control'):
    stream=events(p,role);counts=coverage(stream,p)
    text=f'LAZYBFLY1 {p} {len(stream)}\n'+''.join(' '.join(str(int(x)) for x in row)+'\n' for row in stream)
    return text,counts
