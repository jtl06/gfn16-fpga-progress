"""Exact output-only narrowing and integer model; NOT HDL simulation/formal proof.

Let R=2^32,T=a*b,m=(T mod R)*P^-1 mod R,H=T//R,K=mP//R.
For ANY27-bit a,b, T<2^54, H<2^22<P, and0<=K<P. Low32 bits
of T and mP agree, hence D=H-K=(T-mP)/R lies in(-P,P).
Conditional+P produces a canonical result<P<2^27. This broader mathematical
bound does NOT extend the module's declared canonical-input contract.

Keep the32-bit m,54-bit T and59-bit mP arithmetic unchanged. Explicit final
zero extension could aid constant propagation but no net resource/timing
saving is established. Reset/hold/valid and k->k+3 latency are unchanged.
"""
import hashlib
from pathlib import Path

ANCESTOR='genefer_montgomery_mul27_sparse_pipe'
TOP='genefer_montgomery_mul27_canonical_pipe'
ANCESTOR_SHA='501d0ce309a3915f7aed0f3bde14ba1ee8d56ddc5f6abef1f2f5bb572d64db4b'
FIELDS=((104857601,4190109697,25),(69206017,4225761281,21),(67239937,4227727361,17))
RADIX=1<<32


def require(value,message):
    if not value:raise ValueError(message)


def expected(original):
    require(hashlib.sha256(original.encode()).hexdigest()==ANCESTOR_SHA,'frozen multiplier ancestor changed')
    changes=(
        ('// Experimental four-stage Montgomery multiplier, II=1.',
         '// Isolated RTL-only candidate: explicitly zero-extended27-bit result, II=1.'),
        ('module '+ANCESTOR+' #(','module '+TOP+' #('),
        ('result<=hi_s3-mp_hi;',"result<={5'b0,27'(hi_s3-mp_hi)};"),
        ('result<=hi_s3+P-mp_hi;',"result<={5'b0,27'(hi_s3+P-mp_hi)};"),
    )
    for old,new in changes:
        require(original.count(old)==1,'ambiguous exact-source anchor')
        original=original.replace(old,new)
    return original


def validate_files(root):
    kernel=Path(root)/'rtl/kernel'
    actual=(kernel/(TOP+'.sv')).read_text()
    require(actual==expected((kernel/(ANCESTOR+'.sv')).read_text()),'unreviewed canonical multiplier delta')
    return {str(Path('rtl/kernel')/(TOP+'.sv')):hashlib.sha256(actual.encode()).hexdigest()}


def parameters(p,q):
    require((p,q) in [(a,b) for a,b,_ in FIELDS],'unsupported modulus/inverse')
    return next(s for a,_,s in FIELDS if a==p)


def mathematical_reduction(a,b,p,q):
    """Bounds model for full27-bit operands, even outside legal HDL domain."""
    s=parameters(p,q);require(0<=a<1<<27 and 0<=b<1<<27,'not27-bit operands')
    t=a*b;lo=t&(RADIX-1);h=t>>32
    m=(lo-(lo<<26)-(lo<<s)-((lo<<22) if p==104857601 else 0))&(RADIX-1)
    mp=m+(m<<26)+(m<<s)+((m<<22) if p==104857601 else 0)
    k=mp>>32
    before=h-k if h>=k else h+p-k
    after=before&((1<<27)-1)
    return dict(t=t,lo=lo,h=h,m=m,mp=mp,k=k,before=before,after=after,corrected=h<k)


class PipelineModel:
    """Literal gated-register clock model, not an execution of SystemVerilog."""
    def __init__(self,p,q):
        self.p=p;self.q=q;self.s=parameters(p,q);self.reset()

    def reset(self):
        self.valid=[False]*3;self.t=0;self.m=0;self.h2=0;self.mp=0;self.h3=0
        self.out_valid=False;self.result=0

    def edge(self,rst_n=True,in_valid=False,a=0,b=0):
        if not rst_n:
            self.reset();return self.out_valid,self.result
        if in_valid:require(0<=a<self.p and 0<=b<self.p,'noncanonical declared input')
        old=self.valid[:];self.out_valid=old[2]
        if old[2]:
            k=self.mp>>32
            value=self.h3-k if self.h3>=k else self.h3+self.p-k
            self.result=value&((1<<27)-1)
        if old[1]:
            self.mp=self.m+(self.m<<26)+(self.m<<self.s)+((self.m<<22) if self.p==104857601 else 0)
            self.h3=self.h2
        if old[0]:
            lo=self.t&(RADIX-1)
            self.m=(lo-(lo<<26)-(lo<<self.s)-((lo<<22) if self.p==104857601 else 0))&(RADIX-1)
            self.h2=self.t>>32
        if in_valid:self.t=a*b
        self.valid=[bool(in_valid),old[0],old[1]]
        return self.out_valid,self.result
