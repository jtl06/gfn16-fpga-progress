"""Private R14 byte-exact host implementation/reference for the C header.

The frozen B spec/model is unchanged. Full-N linear host work is admitted
Linux-only; coordinator numerical tests stop at N256. This is not transport,
GL/rollback, chip equivalence or a new framing protocol.
"""
from dataclasses import dataclass
import socket
import struct
import sys

from .stream27_blockcarry_param_model_v1 import bounds, minimum_base
from .stream27_canonical_image_model_v1 import fold

PRIMES=(104857601,69206017,67239937)
P=16


class HostError(ValueError):
    pass


def need(ok,tag):
    if not ok:raise HostError('R14_HOST_'+tag)


def worker_numeric(n):
    need(n<=256 or (sys.platform.startswith('linux') and
         socket.gethostname().split('.')[0] in ('aethia','gfn16-pilot-c4d')),
         'FULL_NUMERIC_ADMITTED_LINUX_ONLY')


def geometry(n):
    need(type(n) is int and n in (32,256,65536),'GEOMETRY')
    return n//P,2*n+24*P


def pack32(words):
    need(all(type(v) is int and -(1<<31)<=v<1<<32 for v in words),'WORD32')
    return struct.pack('<'+'I'*len(words),*(v&0xffffffff for v in words))


def profile_make(n,base,generation):
    geometry(n)
    need(type(generation) is int and 0<=generation<256,'GENERATION8')
    proof=bounds(n,P,base)
    reciprocal=(1<<96)//base;limit=proof['A']
    return pack32([base,generation]+[(reciprocal>>(32*i))&0xffffffff for i in range(3)]+
                  [(limit>>(32*i))&0xffffffff for i in range(3)])


def profile_validate(n,raw):
    geometry(n)
    need(type(raw) is bytes and len(raw)==32,'PROFILE_LENGTH')
    words=struct.unpack('<8I',raw)
    need(raw==profile_make(n,words[0],words[1]),'EXACT_PROFILE_RECIP96_LIMIT77')
    return words[0],words[1]


def owner_validate(context,owner,expected_context,expected_owner,generation):
    need(type(context) is type(expected_context) is int and context in (0,1) and
         context==expected_context,'CONTEXT')
    need(type(owner) is type(expected_owner) is int and 0<=owner<1<<56 and
         0<=expected_owner<1<<56 and owner==expected_owner and owner&255==generation,
         'FULL56_OWNER')


def _signed(v):
    return v-(1<<32) if v&(1<<31) else v


def _corrections(raw,k,base):
    need(type(raw) is bytes and len(raw)==128,'CORRECTION_LENGTH')
    words=tuple(map(_signed,struct.unpack('<32I',raw)))
    need(all(abs(v)<=base-1 for v in words[:16]) and all(abs(v)<=k for v in words[16:]),
         'CORRECTION_RANGE')
    return words


def cold_write(n,profile,context,owner,digits,corrections,*,expected_context,expected_owner):
    T,k=geometry(n);worker_numeric(n);base,generation=profile_validate(n,profile)
    owner_validate(context,owner,expected_context,expected_owner,generation)
    need(type(digits) is bytes and len(digits)==4*n,'COLD_EXACT_LENGTH')
    d=struct.unpack('<'+'I'*n,digits)
    need(all(v==0xffffffff or v<base for v in d),'COLD_SIGNED_DIGIT_RANGE')
    c=_corrections(corrections,k,base)
    reverse=[sum(((lane>>bit)&1)<<(3-bit) for bit in range(4)) for lane in range(16)]
    result=[]
    for prime in PRIMES:
        for row in range(T):
            result.extend(_signed(d[reverse[lane]*T+row])%prime for lane in range(16))
    for high in (False,True):
        for prime in PRIMES:
            # High is unscaled c1. The polynomial x^1 term belongs to chip's
            # existing twist/small DFT path, not a host multiplication by b.
            result.extend(v%prime for v in c[16 if high else 0:32 if high else 16])
    return pack32(result)


@dataclass(frozen=True)
class FinalResult:
    wire:bytes
    carries:tuple
    special:bool


def final_decode(n,profile,context,owner,raw,*,expected_context,expected_owner):
    T,k=geometry(n);worker_numeric(n);base,generation=profile_validate(n,profile)
    owner_validate(context,owner,expected_context,expected_owner,generation)
    need(type(raw) is bytes and len(raw)==4*(n+32),'FINAL_EXACT_LENGTH')
    words=struct.unpack('<'+'I'*(n+32),raw)
    need(all(v<base for v in words[:n]),'FINAL_DIGIT_RANGE')
    c=_corrections(raw[4*n:],k,base)
    image=[words[row*P+lane] for lane in range(P) for row in range(T)]
    carry=0;ends=[]
    for phase in range(3):
        for j in range(n):
            value=image[j]+carry
            if phase==0:
                lane,row=divmod(j,T)
                if row==0:value+=c[lane]
                elif row==1:value+=c[16+lane]
            carry,image[j]=fold(value,base)
            need(abs(carry)<=(2 if phase==0 else 1),'FOLD_INDUCTION')
        ends.append(carry)
        if phase<2:carry=-carry
    special=ends[-1]!=0
    if special:
        need((ends[-1]==1 and all(v==0 for v in image)) or
             (ends[-1]==-1 and all(v==base-1 for v in image)),'SPECIAL_IMAGE')
        image=[-1]+[0]*(n-1)
    return FinalResult(pack32(image),tuple(ends),special)


class AtomicIntake:
    """Bounded sequential host staging, not a transport or chip endpoint.

    Commit invokes the selected decoder only on a complete current transaction.
    Rejection/reset makes this intake unusable; published bytes never change on
    a rejected append/commit. A new intake/fenced owner follows reset. Callers
    must not recycle full wire owners while older transport can still arrive.
    """
    def __init__(self,n,profile,context,owner,kind):
        geometry(n);base,generation=profile_validate(n,profile)
        owner_validate(context,owner,context,owner,generation)
        need(kind in ('cold','final'),'INTAKE_KIND')
        self.n,self.profile,self.context,self.owner,self.kind=n,profile,context,owner,kind
        self.expected_bytes=4*(n+32)
        self.pending=bytearray();self.failed=False;self.published=None

    def reset(self):
        self.pending.clear();self.failed=True;self.published=None

    def append(self,raw,*,offset,context,owner):
        need(not self.failed,'INTAKE_QUARANTINE')
        try:
            need(type(raw) is bytes and type(offset) is int and offset==len(self.pending) and
                 len(raw)%4==0 and len(self.pending)+len(raw)<=self.expected_bytes,
                 'INTAKE_ORDER_LENGTH')
            need(type(context) is type(owner) is int and
                 context==self.context and owner==self.owner,'INTAKE_OWNER')
        except HostError:
            self.failed=True;self.pending.clear();raise
        self.pending.extend(raw)

    def commit(self,*,context,owner):
        need(not self.failed,'INTAKE_QUARANTINE')
        try:
            need(len(self.pending)==self.expected_bytes,'INTAKE_PARTIAL')
            need(type(context) is type(owner) is int and
                 context==self.context and owner==self.owner,'INTAKE_OWNER')
            raw=bytes(self.pending)
            if self.kind=='cold':
                result=cold_write(self.n,self.profile,context,owner,raw[:4*self.n],raw[4*self.n:],
                    expected_context=self.context,expected_owner=self.owner)
            else:
                result=final_decode(self.n,self.profile,context,owner,raw,
                    expected_context=self.context,expected_owner=self.owner)
        except (HostError,ValueError):
            self.failed=True;self.pending.clear();raise
        self.published=result;self.pending.clear();self.failed=True
        return result
