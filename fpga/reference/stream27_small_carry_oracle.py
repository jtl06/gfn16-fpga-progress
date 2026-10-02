"""Independent ordinary-integer oracle for the one-edge S3 small-carry cell.

No RTL/native execution. No imports from candidate arithmetic/schedule models.
Integer divmod is the oracle; threshold_cell is an independent expression of
the RTL selection regions, checked against that oracle by local properties.
"""
from dataclasses import dataclass

MAX_BASE=10**9


class CellInputError(ValueError):
    def __init__(self,reason):
        super().__init__('STREAM27_SMALL_CARRY_'+reason.upper());self.reason=reason


def geometry(aw,p):
    if type(aw) is not int or type(p) is not int or not 5<=aw<=16 or p<1 or p&(p-1) or p>(1<<aw)//2:
        raise CellInputError('geometry')
    n=1<<aw;k=2*n+24*p;q=2*n+23*p
    return dict(aw=aw,p=p,n=n,k=k,q=q,minimum_base=max(2*n+5,(2*k+2)//3+1))


def bounds(aw,p,base):
    info=geometry(aw,p)
    if type(base) is not int or not info['minimum_base']<=base<=MAX_BASE:
        raise CellInputError('base')
    B=base-1;K=info['k'];Q=info['q'];n=info['n']
    A=2*((n+3*p)*B*B+4*p*B*K+p*K*K)
    exact_q2=(A+base*base-1)//(base*base)
    assert 2*K<=3*B and exact_q2<=Q<K
    assert -Q-2>=-2*base and 2*B+Q+3<4*base
    assert max(4*base,2*B+Q+3)<1<<32
    return dict(info,base=base,y_min=-Q,y_max=2*B+Q,coefficient_bound=A,
                exact_q2_bound=exact_q2,total_min=-Q-2,total_max=2*B+Q+3)


def oracle(y,carry,base,aw=16,p=8,*,block_start=False):
    info=bounds(aw,p,base)
    if type(block_start) is not bool:raise CellInputError('block_start_type')
    if type(y) is not int or not -(1<<32)<=y<(1<<32):raise CellInputError('y_port')
    if type(carry) is not int or not -4<=carry<=3:raise CellInputError('carry_port')
    if not -2<=carry<=3:raise CellInputError('carry_range')
    if not info['y_min']<=y<=info['y_max']:raise CellInputError('y_range')
    if block_start and not 0<=y<base:raise CellInputError('block_start_range')
    quotient,digit=divmod(y+(0 if block_start else carry),base)
    assert -2<=quotient<=3 and 0<=digit<base
    return digit,quotient


def threshold_cell(y,carry,base,*,block_start=False,mutant=None):
    """Arithmetic only; caller first applies oracle's independent legal domain."""
    value=y+(0 if block_start and mutant!='ignore_block_start' else carry)
    thresholds=(-base,0,base,2*base,3*base)
    quotient=3
    for q,t in zip(range(-2,3),thresholds):
        if value<=t if mutant=='boundary_le' else value<t:
            quotient=q;break
    if mutant=='truncate_negative' and value<0:quotient=-((-value)//base)
    return value-quotient*base,quotient


@dataclass
class Outputs:
    valid:bool=False
    error:bool=False
    digit:int|None=None
    carry:int=0
    payload:int|None=None


class Cell:
    """One acceptance edge updates outputs; no extra input/feedback stage."""
    def __init__(self,aw=16,p=8,payload_w=1):
        geometry(aw,p)
        if type(payload_w) is not int or payload_w<1:raise CellInputError('payload_width')
        self.aw,self.p,self.payload_w=aw,p,payload_w;self.out=Outputs()

    def reset(self):
        self.out.valid=False;self.out.error=False;self.out.carry=0
        return Outputs(**vars(self.out))

    def edge(self,*,y=0,carry=0,base=0,payload=0,valid=True,block_start=False,rst_n=True):
        if not rst_n:return self.reset()
        self.out.valid=False;self.out.error=False
        if not valid:return Outputs(**vars(self.out))
        if type(payload) is not int or not 0<=payload<(1<<self.payload_w):raise CellInputError('payload_port')
        self.out.payload=payload
        try:digit,next_carry=oracle(y,carry,base,self.aw,self.p,block_start=block_start)
        except CellInputError:self.out.error=True
        else:self.out.valid=True;self.out.digit=digit;self.out.carry=next_carry
        return Outputs(**vars(self.out))
