"""Independent Python whole-X check of the native-only oracle's small corpus."""
from fpga.reference import stream27_canonical_image_model_v1 as math


def corpus(aw,p):
    math.need(type(aw) is int and aw in (5,8) and type(p) is int and p in (8,16),'CANON_CORPUS_SMALL_ONLY')
    g=math.geometry(aw,p);n,t,k=g['n'],g['t'],g['k'];trials=[]
    for base in (g['minimum_base'],math.MAX_BASE):
        zero=[0]*n;maximum=[base-1]*n;empty=[0]*p
        dense=[(i*104729+(i//t)*31+17)%base for i in range(n)]
        trials += [(base,zero,empty,empty), (base,dense,empty,empty),
            (base,maximum,empty,empty), (base,zero,[-1]+[0]*(p-1),empty),
            (base,maximum,[1]+[0]*(p-1),empty),
            (base,maximum,[base-1]*p,[k]*p), (base,zero,[1-base]*p,[-k]*p),
            (base,dense,[1-base if b%2 else base-1 for b in range(p)],
             [k if b%2 else -k for b in range(p)]),
            (base,maximum,[0]*(p-1)+[base-1],[0]*(p-1)+[k])]
    state=0x43414e4f4e563100^(aw<<8)^p;mask=(1<<64)-1
    def rand():
        nonlocal state
        state^=(state<<13)&mask;state^=state>>7;state^=(state<<17)&mask
        return state
    for test in range(24):
        base=g['minimum_base'] if test%3==0 else math.MAX_BASE if test%3==1 else g['minimum_base']+rand()%(math.MAX_BASE-g['minimum_base']+1)
        digits=[rand()%base for _ in range(n)];c0=[];c1=[]
        for _ in range(p):c0.append(rand()%(2*(base-1)+1)-(base-1));c1.append(rand()%(2*k+1)-k)
        trials.append((base,digits,c0,c1))
    math.need(len(trials)==42,'CANON_CORPUS_COUNT')
    return trials


def checksum(aw,p):
    value=0
    for base,digits,c0,c1 in corpus(aw,p):
        expected=math.independent_integer_oracle(digits,c0,c1,base)
        math.need(expected==math.canonicalize(digits,c0,c1,base).digits,'CANON_CORPUS_INTEGER_MISMATCH')
        for d in expected:value=(value*65599+d+1)%1000000007
    return value
