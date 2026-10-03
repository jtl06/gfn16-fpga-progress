"""Independent bounded application-bus codecs, not vendor PCIe/CDC evidence."""
from .stream27_r15_shell_packets_v1 import FIELDS, RESP, OPS, pack, unpack
from .stream27_r15_host_link_model_v1 import decode_word
from .stream27_r15_host_mmio_v1 import REG

DESC_REG = {'DESCRIPTOR_CONTEXT':0x70,'DESCRIPTOR_INDEX':0x74,
            'DESCRIPTOR_GENERATION':0x78,'DESCRIPTOR_DOUBLE':0x7c}
REGISTERS = REG | DESC_REG


def data_command(raw, n):
    w=decode_word(raw)
    if n not in (32,256,65536) or w.index>=n+32:
        raise ValueError('R15_BUS_RECORD_INDEX')
    return pack(FIELDS,op=OPS['DATA'],context=w.context,session=w.session,
                lease=w.lease,owner=w.owner,index=w.index,word=w.value)


def burst(address,count,*,export=False,n=65536):
    if type(address) is not int or type(count) is not int or count not in range(1,32):
        raise ValueError('R15_BUS_BURST')
    limit=1<<23 if export else 1<<22
    if not 0<=address<limit or address%32:
        raise ValueError('R15_BUS_ALIGNMENT')
    context=address>>22 if export else 0
    index=(address&((1<<22)-1))//32
    if index+count>(n if export else (1<<22)//32):
        raise ValueError('R15_BUS_RANGE')
    return context,index,count


def snapshot_register(snapshot,name,context,*,accepted,last_lease):
    s=unpack(RESP,snapshot)
    if context not in (0,1):raise ValueError('R15_BUS_CONTEXT')
    if name=='NEXT_GENERATION':return ((s['core_generation']>>(8*context))&255)+1
    if name=='NEXT_EPOCH':return (s['next_epoch']>>(16*context))&65535
    if name=='ACCEPTED':return accepted
    if name=='APPLIED':return s['applied']
    if name=='SESSION':return s['session']
    if name=='LEASE':return last_lease
    raise ValueError('R15_BUS_SNAPSHOT_REGISTER')


def check_a_response(snapshot,*,context,session,owner,index):
    r=unpack(RESP,snapshot)
    data=r['data']
    if (r['op'],r['status'],r['context'],r['session'])!=(OPS['READ_A'],0,context,session):
        raise ValueError('R15_BUS_RESPONSE_AUTHORITY')
    words=[(data>>(32*i))&0xffffffff for i in range(8)]
    if words[:5]!=[0x52314100|context,session,owner&0xffffffff,owner>>32,index]:
        raise ValueError('R15_BUS_A_RECORD')
    return data


class HeldBeat:
    """Avalon obligation: no withdrawal/mutation of a stalled offered beat."""
    def __init__(self):self.pending=None
    def edge(self,active,payload,waitrequest,reset=False):
        if reset:self.pending=None;return
        if self.pending is not None and (not active or payload!=self.pending):
            raise ValueError('R15_BUS_HELD_PAYLOAD')
        self.pending=payload if active and waitrequest else None


CONTRACT={
 'addresses':'byte relative control/cold/export apertures; actual vendor mapping separate',
 'bounded':'one command512 register; export cursor max31 beats; no payload RAM',
 'commands':'one nonDATA outstanding, all cold/control/export fenced until core response',
 'counts':'ACCEPTED PCIe beat count versus APPLIED core physical ACK count',
 'export':'formatA32 canonical signed96 owned record; nonOK never validA',
 'reset':'common reset clears local caches; link_ready/session/drain owned by shell/core',
 'scope':'AUTHOR endpoint only; no full-core, vendorIP, physicalCDC, timing or promotion',
}
