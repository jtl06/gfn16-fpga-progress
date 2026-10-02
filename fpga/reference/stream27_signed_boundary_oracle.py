"""Independent ordinary-integer S3 signed-boundary cell contract; no HDL run.

Inputs are exact unsigned32 wire words decoded as signed32.  The oracle uses
Python modulo directly, not the candidate's compare/subtract magnitude path.
The edge model owns an explicit D4 queue, independent of RTL valid registers.
"""
from collections import deque
from dataclasses import dataclass

FIELDS=(104857601,69206017,67239937)
LATENCY=4


def geometry(aw,blocks):
    if type(aw) is not int or not 5<=aw<=16 or type(blocks) is not int or blocks<1 or blocks&(blocks-1) or blocks>(1<<aw)//2:
        raise ValueError('AW5..16, power-of-two BLOCKS<=N/2')
    n=1<<aw;k=2*n+24*blocks
    return n,k,max(2*n+5,(2*k+2)//3+1)


def evaluate(word,boundary_high,base,*,aw=16,blocks=8,p=FIELDS[0]):
    _,k,minimum=geometry(aw,blocks)
    if p not in FIELDS:raise ValueError('exact three-field modulus')
    if type(word) is not int or not 0<=word<1<<32:raise ValueError('full unsigned32 input wire word')
    if type(base) is not int or not 0<=base<1<<32:raise ValueError('full unsigned32 base wire word')
    if type(boundary_high) is not int or boundary_high not in (0,1):raise ValueError('one-bit c0/c1 kind')
    value=word-(1<<32) if word>=1<<31 else word
    limit=k if boundary_high else base-1
    legal=minimum<=base<=1_000_000_000 and abs(value)<=limit
    return dict(error=not legal,residue=value%p if legal else None,signed_value=value,
                admitted_limit=limit,minimum_base=minimum)


@dataclass
class Pipeline:
    aw:int=16
    blocks:int=8
    p:int=FIELDS[0]

    def __post_init__(self):
        geometry(self.aw,self.blocks)
        if self.p not in FIELDS:raise ValueError('exact three-field modulus')
        self.async_reset()

    def async_reset(self):
        self.queue=deque([None]*LATENCY)
        self.out_valid=False;self.out_error=False;self.residue=0;self.payload=0
        return self.outputs()

    def outputs(self):
        return dict(out_valid=self.out_valid,out_error=self.out_error,residue=self.residue,payload=self.payload)

    def edge(self,*,in_valid=False,word=0,boundary_high=0,base=1_000_000_000,payload=0,rst_n=True):
        if not rst_n:return self.async_reset()
        due=self.queue.popleft()
        token=(evaluate(word,boundary_high,base,aw=self.aw,blocks=self.blocks,p=self.p),payload) if in_valid else None
        self.queue.append(token);self.out_valid=False;self.out_error=False
        if due is not None:
            result,self.payload=due
            self.out_error=result['error'];self.out_valid=not result['error']
            if self.out_valid:self.residue=result['residue']
        return self.outputs()
