"""Maintain frozen protocol epoch sequence across fully drained cold jobs.

Generation identifies the cold job, but does not reset the protocol's sequence.
Do not reset/reconfigure the shared arithmetic merely to accept epoch zero.
Advance the cold epoch only after complete real canonical/copy publication.
"""
import ast
import hashlib
from . import stream27_host_core_v1 as root
from . import stream27_host_core_v2 as parent

ROOT=root.ROOT
PIN='7a6cee18c198d09a473e24a89f651b94a32402fbb14ea21cd66717cf106dca20'
PUB_PIN='0b1856e493f0a56fb54d1822496f29dc2b48912fc79f18bea876aee260025603'


def source(n,child):
    top,text=parent.source(n,child);newtop=top[:-2]+'v3'
    changes=[('module '+top+' #','module '+newtop+' #'),
        ('logic [7:0] job_generation;logic image_published;',
         'logic [7:0] job_generation;logic image_published;logic [15:0] job_epoch,next_cold_epoch;'),
        ('.epoch_in(16\'d0),.correction_epoch(16\'d0),',
         '.epoch_in(job_epoch),.correction_epoch(job_epoch),'),
        ('job_generation<=0;','job_generation<=0;job_epoch<=0;next_cold_epoch<=0;'),
        ('job_mask<=batch_mode ? double_mask : 32\'d0;job_generation<=job_generation+8\'d1;',
         'job_mask<=batch_mode ? double_mask : 32\'d0;job_generation<=job_generation+8\'d1;job_epoch<=next_cold_epoch;'),
        ('COPY_DRAIN:begin state<=IDLE;done<=1;image_published<=1;end',
         'COPY_DRAIN:begin state<=IDLE;done<=1;image_published<=1;next_cold_epoch<=job_epoch+16\'(job_count);end')]
    for old,new in changes:
        if text.count(old)!=1:raise ValueError('S4_HOST_COLD_EPOCH_ANCHOR:'+old)
        text=text.replace(old,new)
    return newtop,text


def prepare(n=32,p=16,*,paired=False,contexts=1,allow_full_constants=False):
    path=ROOT/'reference/stream27_host_core_v1.py';raw=path.read_text()
    if hashlib.sha256(raw.encode()).hexdigest()!=PIN or root.sha('reference/stream27_host_core_v2.py')!=PUB_PIN:
        raise ValueError('S4_HOST_COLD_EPOCH_PARENT_DRIFT')
    nodes=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='prepare']
    if len(nodes)!=1:raise ValueError('S4_HOST_COLD_EPOCH_PARENT_FUNCTION')
    node=nodes[0];body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    namespace=dict(vars(root));namespace['source']=source
    exec(compile(body,str(path)+'[persistent cold epoch sequence]','exec'),namespace)
    b=namespace['prepare'](n,p,paired=paired,contexts=contexts,allow_full_constants=allow_full_constants)
    for path in ('reference/stream27_host_core_v2.py','reference/stream27_host_core_v3.py'):
        b['source_dependencies'].append(path);b['source_sha256'][path]=root.sha(path)
    b['host_contract']['publication']='Current copied output publishes only on successful done; invalidated on accepted idle load/start.'
    b['host_contract']['cold_epoch']='Persistent16bit epoch: next cold job begins at priorjob_epoch+priorcount modulo65536, only after full canonical/copy drain. Fresh generation does not reset frozen protocol sequencing.'
    return b
