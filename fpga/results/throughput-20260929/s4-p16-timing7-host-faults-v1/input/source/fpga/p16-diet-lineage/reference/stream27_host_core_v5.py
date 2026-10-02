"""Explicit range-guarded width at native command-line epoch seed boundary."""
import ast
import hashlib
from . import stream27_host_core_v1 as root
from . import stream27_host_core_v4 as parent

ROOT=root.ROOT
PIN='6e1d16911dbe15d9fe02937bb332831ef2bea763b17e5136f22f010dcc0dd3ac'


def source(n,child):
    top,text=parent.source(n,child);newtop=top[:-2]+'v5'
    changes=[('module '+top+' #','module '+newtop+' #'),
        ('parameter logic [15:0] EPOCH_SEED=0','parameter int unsigned EPOCH_SEED=0'),
        ('job_epoch<=EPOCH_SEED;next_cold_epoch<=EPOCH_SEED;',
         "job_epoch<=16'(EPOCH_SEED);next_cold_epoch<=16'(EPOCH_SEED);"),
        ('initial if(AW!=',"initial if(EPOCH_SEED>32'd65535 || AW!=")]
    for old,new in changes:
        if text.count(old)!=1:raise ValueError('S4_HOST_EPOCH_SEED_WIDTH_ANCHOR')
        text=text.replace(old,new)
    return newtop,text


def prepare(n=32,p=16,*,paired=False,contexts=1,allow_full_constants=False):
    path=ROOT/'reference/stream27_host_core_v4.py';raw=path.read_text()
    if hashlib.sha256(raw.encode()).hexdigest()!=PIN:raise ValueError('S4_HOST_EPOCH_SEED_WIDTH_PARENT_DRIFT')
    nodes=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='prepare']
    if len(nodes)!=1:raise ValueError('S4_HOST_EPOCH_SEED_WIDTH_ENTRY')
    node=nodes[0];body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    namespace=dict(vars(parent));namespace['source']=source
    exec(compile(body,str(path)+'[range-guarded seed boundary]','exec'),namespace)
    b=namespace['prepare'](n,p,paired=paired,contexts=contexts,allow_full_constants=allow_full_constants)
    path='reference/stream27_host_core_v5.py';b['source_dependencies'].append(path);b['source_sha256'][path]=root.sha(path)
    b['host_contract']['epoch_seed_width']='Native -G uses32bit integer parameter; explicit unsigned range0..65535 guard precedes intentional16bit reset casts. No WIDTHTRUNC waiver.'
    return b
