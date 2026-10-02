"""P5/L3b: signed raw REDC only inside a fused lazy CT/GS butterfly.

R=2^32, lhs<2P/rhs<P gives t<2P²<PR. With m=t_low*P^-1 modR,
q=floor(mP/R)<P, raw=floor(t/R)-q lies strictly(-P,P), so signed28
is sufficient. The variable DSP product remains27x27; lhs bit27's
rhs<<27 correction is outside that DSP. No28x28 product is admitted.

CT prefix is u modP. S=prefix+raw+P lies(0,3P); S>=2P ? S-P : S
lies[0,2P). D=prefix-raw lies(-P,2P); D<0 ? D+P : D likewise.
CT S needs signed30 (3P can exceed signed29), D needs signed29.
GS pre sum/diff fold mod2P; lower=raw+P lies(0,2P).
All public outputs are UNSIGNED28<2P and congruent to frozen CT/GS
outputs moduloP, but may differ by P. Canonical finalGS/point consumers
still require their existing boundary canonicalization. Raw signed data
never enters an unchanged lazy multiplier or MDC transport.
"""
from fpga.reference import stream27_l3_factored_model_v1 as factor
FIELDS=factor.FIELDS;R=1<<32
def need(ok,why):
    if not ok:raise ValueError(why)
def raw_montgomery(lhs,rhs,p):
    need(p in FIELDS and 0<=lhs<2*p and 0<=rhs<p,'P5_INPUT_RANGE')
    t=lhs*rhs;m=((t&(R-1))*((2-p)&(R-1)))&(R-1)
    q=(m*p)>>32;raw=(t>>32)-q
    need((m*p)&(R-1)==t&(R-1) and 0<=q<p and -p<raw<p,'P5_RAW_RANGE')
    need(raw%p==lhs*rhs*pow(R,-1,p)%p,'P5_RAW_DOMAIN')
    return raw
def butterfly(u,v,w,p,gs):
    need(p in FIELDS and 0<=u<2*p and 0<=v<2*p and 0<=w<p and gs in (0,1),'P5_BFLY_RANGE')
    if gs:
        a=(u+v)%(2*p);raw=raw_montgomery((u-v)%(2*p),w,p);b=raw+p
    else:
        prefix=u%p;raw=raw_montgomery(v,w,p);total=prefix+raw+p;difference=prefix-raw
        need(0<total<3*p and -p<difference<2*p,'P5_CT_FUSION_BOUNDS')
        a=total-p if total>=2*p else total;b=difference+p if difference<0 else difference
    need(0<=a<2*p and 0<=b<2*p,'P5_EXTERNAL_UNSIGNED28_BOUND')
    expected=((u+v*w*pow(R,-1,p))%p,(u-v*w*pow(R,-1,p))%p) if not gs else ((u+v)%p,((u-v)*w*pow(R,-1,p))%p)
    need((a%p,b%p)==expected,'P5_FROZEN_RESIDUE_EQUIVALENCE')
    return a,b

def butterfly_sign(u,v,w,p,gs):
    """Successor: CT prefix±raw in(-P,2P), sign-only+P, signed29.

    GS is unchanged. This avoids biased30bit CT arithmetic and comparison
    against2P; still legal unsigned28 representatives, NOT bitwise legacy.
    """
    need(p in FIELDS and 0<=u<2*p and 0<=v<2*p and 0<=w<p and gs in (0,1),'P5_SIGN_INPUT_RANGE')
    if gs:return butterfly(u,v,w,p,gs)
    prefix=u%p;raw=raw_montgomery(v,w,p)
    sums=(prefix+raw,prefix-raw)
    need(all(-p<x<2*p and -(1<<28)<=x<(1<<28) for x in sums),'P5_SIGN_SIGNED29_BOUND')
    outputs=tuple(x+p if x<0 else x for x in sums)
    need(all(0<=x<2*p for x in outputs),'P5_SIGN_PUBLIC28_BOUND')
    need(tuple(x%p for x in outputs)==tuple(x%p for x in butterfly(u,v,w,p,0)),'P5_SIGN_RESIDUE_EQUIVALENCE')
    return outputs
