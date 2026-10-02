"""Independent small-N blockcarry field-square oracle, with no NTT code.

The field emits ordinary negacyclic square coefficients modulo one prime.
Conditional doubling, CRT, carry and host canonicalization are outside this
boundary. Corrections are part of the same image, base and generation as digits.
Full-size numerical work is deliberately rejected by this local gate oracle.
"""
from dataclasses import dataclass

PRIMES=(104857601,69206017,67239937)
LANES=8


def reverse3(value):
    return ((value&1)<<2)|(value&2)|((value&4)>>2)


@dataclass(frozen=True)
class SquareImage:
    base: int
    generation: int
    digits: tuple
    c0: tuple
    c1: tuple

    @property
    def n(self):return len(self.digits)

    def validate(self):
        n=self.n
        if n<32 or n>256 or n&(n-1):raise ValueError('SQUARE_ORACLE_LOCAL_N32_TO256')
        if len(self.c0)!=LANES or len(self.c1)!=LANES:raise ValueError('SQUARE_CORRECTIONS_P8')
        if type(self.base) is not int or type(self.generation) is not int or not 0<=self.generation<256:
            raise ValueError('SQUARE_BASE_GENERATION_TYPE')
        K=2*n+24*LANES
        minimum=max(2*n+5,(2*K+2)//3+1)
        if not minimum<=self.base<=1000000000:raise ValueError('SQUARE_SUPPORTED_BASE')
        B=self.base-1
        if any(type(x) is not int or not 0<=x<=B for x in self.digits):raise ValueError('SQUARE_DIGIT_RANGE')
        if any(type(x) is not int or abs(x)>B for x in self.c0):raise ValueError('SQUARE_C0_RANGE')
        if any(type(x) is not int or abs(x)>K for x in self.c1):raise ValueError('SQUARE_C1_RANGE')
        return self

    def effective(self):
        self.validate();values=list(self.digits);T=self.n//LANES
        for block in range(LANES):
            values[block*T]+=self.c0[block]
            values[block*T+1]+=self.c1[block]
        return tuple(values)


def coefficients(image):
    """Exact signed integer schoolbook convolution, reduced only by x^N=-1."""
    values=image.effective();n=len(values);result=[0]*n
    for i,a in enumerate(values):
        for j,b in enumerate(values):
            position=i+j
            if position<n:result[position]+=a*b
            else:result[position-n]-=a*b
    return tuple(result)


def physical_rows(values):
    n=len(values)
    if n<32 or n>256 or n&(n-1):raise ValueError('SQUARE_ORACLE_LOCAL_N32_TO256')
    T=n//LANES
    return tuple(tuple(values[reverse3(lane)*T+tick] for lane in range(LANES))
                 for tick in range(T))


def residues(image,field=0):
    if type(field) is not int or not 0<=field<len(PRIMES):raise ValueError('SQUARE_FIELD')
    return physical_rows(tuple(x%PRIMES[field] for x in coefficients(image)))


def image_cases(n=32):
    """Nontrivial signed, sparse and maximum-digit cases; no generation reuse."""
    if n<32 or n>256 or n&(n-1):raise ValueError('SQUARE_ORACLE_LOCAL_N32_TO256')
    K=2*n+24*LANES;minimum=max(2*n+5,(2*K+2)//3+1);cases=[]
    for base in (minimum,1000000000):
        B=base-1
        candidates=[
            ('zero',(0,)*n,(0,)*8,(0,)*8),
            ('canonical-minus-one',(0,)*n,(-1,)+(0,)*7,(0,)*8),
            ('all-max',(B,)*n,(0,)*8,(0,)*8),
            ('signed-boundaries',tuple((i*7919+17)%base for i in range(n)),
                tuple(B if i&1 else -B for i in range(8)),tuple(K if i&1 else -K for i in range(8))),
            ('c1-only',(0,)*n,(0,)*8,tuple((i-4)*K//4 for i in range(8))),
            ('last-index-wrap',(0,)*(n-1)+(1,),(0,)*8,(0,)*8),
        ]
        for label,digits,c0,c1 in candidates:
            cases.append((f'b{base}-{label}',SquareImage(base,len(cases),digits,c0,c1).validate()))
    return tuple(cases)
