"""PRIVATE INTERNAL CDC encoding, not vendor DMA descriptors or BAR assignment.

All integers are little-endian bit fields. External cold DATA32 and canonical
A32 records remain separate. Unused bits must be zero. Commands are ordered;
one non-DATA command outstanding fences subsequent ingress until its response.
"""
OPS={'DATA':0,'BEGIN':1,'COMMIT':2,'CANCEL':3,'START':4,'SNAPSHOT':5,'READ_A':6,'DESCRIPTOR':7,'ABORT':15}
FIELDS={'op':(0,4),'context':(4,1),'owner':(5,56),'session':(61,32),
 'lease':(93,32),'count':(125,32),'base':(157,32),'mask':(189,32),
 'mode':(221,3),'index':(224,32),'word':(256,32),'generation':(288,32)}
RESP={'op':(0,4),'status':(8,8),'context':(16,1),'session':(32,32),
 'next_lease':(64,32),'core_generation':(96,16),'next_epoch':(112,32),
 'loaded':(144,2),'idle':(146,2),'busy':(148,2),'canonical_ready':(150,2),
 'error':(152,1),'applied':(160,32),'accepted':(192,32),'data':(256,256)}
STATUS={'OK':0,'NOT_READY':1,'PROTOCOL_ERROR':2}


def pack(fields,**values):
    out=0
    for name,value in values.items():
        if name not in fields:raise ValueError('R15_PACKET_FIELD')
        shift,width=fields[name]
        if type(value) is not int or not 0<=value<1<<width:raise ValueError('R15_PACKET_WIDTH')
        out|=value<<shift
    return out


def unpack(fields,value):
    if type(value) is not int or not 0<=value<1<<512:raise ValueError('R15_PACKET_WIDTH')
    mask=sum(((1<<width)-1)<<shift for shift,width in fields.values())
    if value & ~mask:raise ValueError('R15_PACKET_RESERVED')
    return {k:(value>>s)&((1<<w)-1) for k,(s,w) in fields.items()}


def canonical_a_record(context,session,owner,index,word):
    if context not in (0,1) or not 0<=session<1<<32 or not 0<=owner<1<<56 or not 0<=index<1<<32:
        raise ValueError('R15_A_OWNER')
    if not -(1<<95)<=word<1<<95:raise ValueError('R15_A_SIGNED96')
    return ((0x52314100|context)|(session<<32)|((owner&0xffffffff)<<64)|
            ((owner>>32)<<96)|(index<<128)|((word&((1<<96)-1))<<160))


CONTRACT={
 'scope':'Internal512 CDC protocol; PCIe address translation/descriptor format separate.',
 'data':'Decode exact external DATA32 into DATA fields; reject high/reserved/index truncation.',
 'begin':'Header generation full32 must equal prospective core generation; old R96/A77 MMIO registers reservedzero.',
 'commit':'No accepted data behind COMMIT. PCIe command fence plus ordered FIFO; core checks actual empty after dequeue and physical ACK count.',
 'start':'index low2=start mask; session current; lease global most-recent BEGIN (next_lease−1), both selected contexts committed internally. Config comes only from committed headers.',
 'descriptor':'context/index/generation/word bit0 double; remaining word bits zero; preserve original ready/accept.',
 'snapshot':'All status captured at one core edge, returned as RESP; no asynchronous multiword bus sampling.',
 'read_a':'context/session/owner/lease/index must match retained job lease; read only published idle context with no loader active/BEGIN. Reserve response credit before actual one-cycle read request.',
 'response':'RESP status0/1/2=OK/NOT_READY/PROTOCOL_ERROR; READ_A data contains32-byte owned canonical96A record. Never run raw finalizer.',
 'reset':'Common reset discards both FIFO directions; session must change before either side regains authority. Counter exhaustion fails closed; power-cycle requires host DMA arena teardown.',
}
