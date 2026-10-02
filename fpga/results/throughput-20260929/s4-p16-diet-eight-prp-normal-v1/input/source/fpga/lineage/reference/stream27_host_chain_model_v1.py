"""Independent bounded control/event and small ordinary-integer long oracle."""
from collections import deque


class ControlFIFO:
    def __init__(self,count,generation):
        if not 1<=count<=0xffffffff:raise ValueError('COUNT')
        self.count=count;self.generation=generation;self.queue=deque();self.next=1
        self.consumed=0;self.error=None

    def edge(self,descriptor=None,*,consume=False):
        """Pre-edge head consumption, no empty push-to-head bypass."""
        old=list(self.queue);ready=len(old)<4 or consume and bool(old)
        popped=None
        if consume:
            if not old:self.error='UNDERFLOW'
            else:popped=old[0]
        accepted=False
        if descriptor is not None and ready and self.error is None:
            index,generation,bit=descriptor
            if generation!=self.generation:self.error='GENERATION'
            elif not 1<=index<self.count:self.error='RANGE'
            elif index!=self.next:self.error='INDEX'
            else:accepted=True
        if self.error is not None:return dict(ready=ready,accepted=False,popped=None,error=self.error)
        if popped is not None:self.queue.popleft();self.consumed+=1
        if accepted:self.queue.append(descriptor);self.next+=1
        return dict(ready=ready,accepted=accepted,popped=popped,error=None)


def image(value,base,n):
    modulus=base**n+1;value%=modulus
    if value==modulus-1:return (-1,)+(0,)*(n-1)
    words=[]
    for _ in range(n):value,d=divmod(value,base);words.append(d)
    if value:raise ValueError('IMAGE_RANGE')
    return tuple(words)


def program(n,kind):
    if n not in (32,256):raise ValueError('SMALL_ORDINARY_ONLY')
    base=1000000000
    if kind=='prp':exponent=base**n
    elif kind=='paired':exponent=(1<<256)|int('394fed89000000018faabdc9321a5a5a'*2,16)
    else:raise ValueError('PROGRAM_KIND')
    bits=tuple(int(x) for x in bin(exponent)[3:])
    modulus=base**n+1;value=2
    for bit in bits:value=(value*value*(1<<bit))%modulus
    expected=pow(2,exponent,modulus)
    if value!=expected:raise ValueError('INDEPENDENT_POW_DISAGREEMENT')
    return dict(base=base,bits=bits,initial=(2,)+(0,)*(n-1),expected=image(expected,base,n),
                exponent=exponent,kind=kind,count=len(bits),oracle='ordinary modular pow versus separately iterated square/double; no NTT')


def true_final(sequence,count,epoch,first_epoch):
    return sequence==count-1 and epoch==(first_epoch+count-1)&65535

