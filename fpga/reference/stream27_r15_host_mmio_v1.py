"""Private R15 logical application MMIO/header codec, NOT vendor BAR layout.

No hardware I/O. This address map is relative to the application control
window; actual BAR mapping awaits generated PCIe IP. DMA descriptor registers
are separate vendor-defined interfaces, never aliases of these offsets.
"""
from dataclasses import dataclass
from .stream27_r15_host_link_model_v1 import LinkFault, need
from .stream27_blockcarry_param_model_v1 import minimum_base

ABI = 0x00010000
REG = {'ID':0x00,'ABI':0x04,'SESSION':0x08,'STATUS':0x0c,
       'CONTEXT':0x10,'OWNER_LO':0x14,'OWNER_HI':0x18,'COUNT':0x1c,
       'BASE':0x20,'GENERATION':0x24,'RESERVED_SETUP0':0x28,
       'RESERVED_SETUP1':0x2c,'RESERVED_SETUP2':0x30,'RESERVED_SETUP3':0x34,
       'RESERVED_SETUP4':0x38,'RESERVED_SETUP5':0x3c,
       'COMMAND':0x40,'ACCEPTED':0x44,'APPLIED':0x48,'ERROR':0x4c,
       'MODE':0x50,'NEXT_EPOCH':0x54,'NEXT_GENERATION':0x58,'LEASE':0x5c,
       'DOUBLE_MASK':0x60,'TOKEN_SESSION':0x64,'TOKEN_LEASE':0x68,
       'START_MASK':0x6c}
MODE_BATCH,MODE_FEED,MODE_FIRST_DOUBLE = 1,2,4
CMD_BEGIN,CMD_COMMIT,CMD_CANCEL,CMD_START = 1,2,3,4


@dataclass(frozen=True)
class Header:
    n: int
    context: int
    base: int
    count: int
    mode: int
    double_mask: int
    first_epoch: int  # read-only core snapshot, not a software override
    generation: int  # next generation from core, never old/current live_owner
    owner: int


def header(n, context, base, count, mode, double_mask, *, core_next_epoch, core_job_generation):
    need(type(n) is int and n in (32,256,65536), 'HEADER_GEOMETRY')
    need(type(context) is int and context in (0,1), 'HEADER_CONTEXT')
    need(type(base) is int and minimum_base(n,16) <= base <= 1000000000, 'HEADER_BASE')
    need(type(mode) is int and 0 <= mode < 8 and not(mode & MODE_FEED and not mode & MODE_BATCH), 'HEADER_MODE')
    need(type(count) is int and 1 <= count < 1 << 32, 'HEADER_COUNT')
    need((mode & MODE_BATCH or count == 1) and (mode & MODE_FEED or count <= 32), 'HEADER_COUNT_MODE')
    need(type(double_mask) is int and 0 <= double_mask < 1 << 32, 'HEADER_DOUBLE_MASK')
    need(type(core_next_epoch) is int and 0 <= core_next_epoch < 1 << 16, 'HEADER_EPOCH')
    need(type(core_job_generation) is int and 0 <= core_job_generation < 255, 'HEADER_GEN_EXHAUSTED')
    generation=core_job_generation+1
    ordinal=count-1
    owner=(ordinal<<24)|(((core_next_epoch+ordinal)&65535)<<8)|generation
    return Header(n,context,base,count,mode,double_mask,core_next_epoch,generation,owner)


def register_writes(h, *, session):
    need(type(h) is Header, 'HEADER_TYPE')
    need(type(session) is int and 0 <= session < 1 << 32, 'HEADER_SESSION')
    # Revalidate immutable object fields before returning any writes.
    expected=header(h.n,h.context,h.base,h.count,h.mode,h.double_mask,
                    core_next_epoch=h.first_epoch,core_job_generation=h.generation-1)
    need(h==expected,'HEADER_OWNER')
    values={'CONTEXT':h.context,'OWNER_LO':h.owner&0xffffffff,'OWNER_HI':h.owner>>32,
            'COUNT':h.count,'BASE':h.base,'GENERATION':h.generation,'MODE':h.mode,
            'DOUBLE_MASK':h.double_mask,'TOKEN_SESSION':session}
    values.update({f'RESERVED_SETUP{i}':0 for i in range(6)})
    return tuple((REG[k],v) for k,v in values.items())


def commit_writes(session, lease):
    need(all(type(x) is int and 0 <= x < 1 << 32 for x in (session,lease)), 'COMMIT_TOKEN')
    return ((REG['TOKEN_SESSION'],session),(REG['TOKEN_LEASE'],lease),(REG['COMMAND'],CMD_COMMIT))
