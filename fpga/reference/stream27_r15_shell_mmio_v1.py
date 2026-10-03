"""Additive application-window semantics; no vendor DMA descriptor aliases."""
from .stream27_r15_host_mmio_v1 import REG as BASE_REG,ABI
REG={**BASE_REG,'DESCRIPTOR_CONTEXT':0x70,'DESCRIPTOR_INDEX':0x74,
     'DESCRIPTOR_GENERATION':0x78,'DESCRIPTOR_DOUBLE':0x7c}
ID=0x52313541
CMD_DESCRIPTOR=7
STATUS_BITS={'LINK_READY':0,'LOCAL_ERROR':1,'CORE_ERROR':2,'COLD_ACTIVE':3,
             'LOADED0':4,'LOADED1':5,'IDLE0':6,'IDLE1':7,'BUSY0':8,'BUSY1':9,
             'CANONICAL0':10,'CANONICAL1':11,'COMMAND_PENDING':12,'EXPORT_PENDING':13}
ERROR_BITS={'LOCAL_PROTOCOL':0,'CORE_FAULT':1,'NON_OK_RESPONSE':2}
SEMANTICS={
 'LEASE':'Latest successfulBEGIN minted lease, not nextlease; reset invalidates. BEGIN uses coherent core nextlease internally.',
 'START':'TOKEN_SESSION current and TOKEN_LEASE global most-recentBEGIN; mask selects only committed contexts. No implicit token refresh.',
 'STATUS':'Core fields are a coherent response snapshot; local pending/error bits are PCIe-domain state.',
 'DESCRIPTOR':'Context0/1, indexuint32, generationuint8, double0/1; reserved high bits reject. Original core ready/accept and underflow checks retained.',
 'BAR':'Offsets relative to application window only; vendor BAR/interconnect build binding still required.'}
