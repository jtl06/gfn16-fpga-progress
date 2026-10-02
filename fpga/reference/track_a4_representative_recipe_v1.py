"""Scalar/event recipe for AW16; local numeric instantiation only at AW5/AW8.

Each starting value is a signed monomial modulo b**N+1. All-(b-1) is -2;
the top monomial exercises negative wrap. Native C++ builds full-N words.
"""


def geometry(aw):
    if aw not in (5,8,16):raise ValueError('representative geometry')
    n=1<<aw;t=n//16
    minimum=max(2*n+5,(2*(2*n+384)+2)//3+1)
    identities=[]
    for case in range(4):
        offset=case*(3*n+5)
        for relative,cold,load,double in ((n+1,1,1,0),(n+2,0,0,1),(n+3,0,0,0),(2*n+4,1,0,1)):
            identities.append(dict(index=offset+relative,cold=cold,load=load,double=double))
    return dict(aw=aw,n=n,t=t,minimum=minimum,commands=12*n+20,squares=16,
        readbacks=8*n,cold_squares=8,profile_loads=4,hold_checks=2*(12*n+20),identities=identities)


def materialize(coefficient,exponent,base,n):
    if n>256:raise ValueError('local oracle limited to N<=256; native C++ owns full-N recipe')
    words=[0]*n
    if coefficient==-1 and exponent==0:return [-1]+words[1:]
    if coefficient<0:
        magnitude=-coefficient
        if not 0<magnitude<base:raise ValueError('negative monomial recipe bound')
        if exponent==0:
            words=[base-1]*n;words[0]=base+1-magnitude
        else:
            words[0]=1;words[exponent]=base-magnitude
            words[exponent+1:]=[base-1]*(n-exponent-1)
    else:
        while coefficient:
            if exponent>=n:raise ValueError('positive monomial recipe extent')
            coefficient,words[exponent]=divmod(coefficient,base);exponent+=1
    return words


def small_cases(aw):
    if aw not in (5,8):raise ValueError('small local recipe only')
    g=geometry(aw);n=g['n']
    for case in range(4):
        base=10**9 if case==3 else g['minimum']
        coefficient=-1 if case==0 else 1 if case==1 else -2
        exponent=n-1 if case==1 else 0
        initial=materialize(coefficient,exponent,base,n)
        states=[]
        for double in (0,1,0,1):
            coefficient=coefficient*coefficient*(1<<double);exponent*=2
            if exponent>=n:coefficient=-coefficient;exponent-=n
            states.append(materialize(coefficient,exponent,base,n))
        yield base,initial,states
