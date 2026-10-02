"""Narrow current host-image publication qualification; arithmetic unchanged."""
import ast
import hashlib
from . import stream27_host_core_v1 as parent

ROOT=parent.ROOT
PIN='7a6cee18c198d09a473e24a89f651b94a32402fbb14ea21cd66717cf106dca20'


def source(n,child):
    top,text=parent.source(n,child);newtop=top[:-2]+'v2'
    changes=[('module '+top+' #','module '+newtop+' #'),
        ('logic [7:0] job_generation;','logic [7:0] job_generation;logic image_published;'),
        ('assign canonical_ready=state==IDLE && child_ready && !error;',
         'assign canonical_ready=state==IDLE && image_published && child_ready && !error;'),
        ('state<=IDLE;done<=0;error<=0;job_base<=0;','state<=IDLE;done<=0;error<=0;image_published<=0;job_base<=0;'),
        ('done<=0;source_valid<=row_read_valid && !error;',
         'done<=0;source_valid<=row_read_valid && !error;\n   if(state==IDLE && !start && load_we && !error)image_published<=0;'),
        ('IDLE:if(start)begin\n     job_base<=base;','IDLE:if(start)begin\n     image_published<=0;job_base<=base;'),
        ('COPY_DRAIN:begin state<=IDLE;done<=1;end','COPY_DRAIN:begin state<=IDLE;done<=1;image_published<=1;end'),
        ('state<=FAILED;error<=1;done<=1;source_valid<=0;',
         'state<=FAILED;error<=1;done<=1;source_valid<=0;image_published<=0;')]
    for old,new in changes:
        if text.count(old)!=1:raise ValueError('S4_HOST_PUBLICATION_ANCHOR:'+old)
        text=text.replace(old,new)
    return newtop,text


def prepare(n=32,p=16,*,paired=False,contexts=1,allow_full_constants=False):
    path=ROOT/'reference/stream27_host_core_v1.py';raw=path.read_text()
    if hashlib.sha256(raw.encode()).hexdigest()!=PIN:raise ValueError('S4_HOST_PUBLICATION_PARENT_DRIFT')
    nodes=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='prepare']
    if len(nodes)!=1:raise ValueError('S4_HOST_PUBLICATION_PARENT_FUNCTION')
    node=nodes[0];body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    namespace=dict(vars(parent));namespace['source']=source
    exec(compile(body,str(path)+'[current copied host image publication]','exec'),namespace)
    b=namespace['prepare'](n,p,paired=paired,contexts=contexts,allow_full_constants=allow_full_constants)
    path='reference/stream27_host_core_v2.py';b['source_dependencies'].append(path);b['source_sha256'][path]=parent.sha(path)
    b['host_contract']['publication']='canonical_ready invalidates on start/accepted idle mutation; done publishes only the fully copied current output. Idle host input reads still follow T5b independently of this output milestone.'
    return b
