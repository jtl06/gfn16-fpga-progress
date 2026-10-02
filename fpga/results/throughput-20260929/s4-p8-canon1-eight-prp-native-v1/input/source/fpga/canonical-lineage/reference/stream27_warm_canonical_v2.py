"""Live-qualified canonical terminal read successor; original v1 preserved."""
import ast
import hashlib
from . import stream27_warm_canonical_v1 as parent

ROOT=parent.ROOT
PIN='c9d868a3f8ef3377499108c00732d103ae4cb409b19a11649b116690ece03682'


def source(n,child,text):
    top,s=parent.source(n,child,text);newtop=top[:-2]+'v2'
    changes=[('module '+top+' #','module '+newtop+' #'),
        ('wire warm_error,warm_pending,canonical_busy,canonical_done,canonical_error,canonical_image_valid;',
         'wire warm_error,warm_pending,canonical_busy,canonical_done,canonical_error,canonical_image_valid,canonical_read_valid;'),
        ('assign canonical_ready=canonical_image_valid && !busy && publish_ok && !out_error;',
         'assign canonical_ready=canonical_image_valid && !busy && publish_ok && !out_error;\n assign read_valid=canonical_read_valid && publish_ok && !out_error;'),
        ('.cycles(canonical_cycles),.read_valid,.read_address_out,.read_data);',
         '.cycles(canonical_cycles),.read_valid(canonical_read_valid),.read_address_out,.read_data);')]
    for old,new in changes:
        if s.count(old)!=1:raise ValueError('S4_READ_TERMINAL_ANCHOR:'+old)
        s=s.replace(old,new)
    return newtop,s


def prepare(n=32,p=16,*,paired=False,contexts=1,allow_full_constants=False):
    path=ROOT/'reference/stream27_warm_canonical_v1.py';raw=path.read_text()
    if hashlib.sha256(raw.encode()).hexdigest()!=PIN:raise ValueError('S4_READ_TERMINAL_PARENT_DRIFT')
    nodes=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='prepare']
    if len(nodes)!=1:raise ValueError('S4_READ_TERMINAL_PARENT_FUNCTION')
    node=nodes[0];body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    namespace=dict(vars(parent));namespace['source']=source
    exec(compile(body,str(path)+'[current-live canonical terminal]','exec'),namespace)
    b=namespace['prepare'](n,p,paired=paired,contexts=contexts,allow_full_constants=allow_full_constants)
    path='reference/stream27_warm_canonical_v2.py';b['source_dependencies'].append(path)
    b['source_sha256'][path]=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    b['terminal_read_live_qualified']=True
    return b
