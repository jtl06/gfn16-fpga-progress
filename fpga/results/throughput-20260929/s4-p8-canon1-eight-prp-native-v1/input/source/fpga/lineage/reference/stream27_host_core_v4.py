"""Cold ledger actual-completion guard and explicit epoch-wrap test seed.

EPOCH_SEED defaults to0, never changes arithmetic/cycles/P/CONTEXTS, and allows
bounded native coverage of the real16bit wrap without65536 throwaway frames.
Same frozen shared protocol accepts any first epoch after reset, then exact+1.
"""
import ast
import hashlib
from . import stream27_host_core_v1 as root
from . import stream27_host_core_v3 as parent

ROOT=root.ROOT
PIN='bdbae8b210e1009cf8904e89c98f16a87d938d0f51f542dc2da0c922a81764f3'


def source(n,child):
    top,text=parent.source(n,child);newtop=top[:-2]+'v4'
    changes=[('module '+top+' #(parameter int AW=', 'module '+newtop+' #(parameter logic [15:0] EPOCH_SEED=0,parameter int AW='),
        ('job_epoch<=0;next_cold_epoch<=0;','job_epoch<=EPOCH_SEED;next_cold_epoch<=EPOCH_SEED;'),
        ('wire request_bad=state==IDLE && start &&',
         'wire completion_bad=(state==COPY_DRAIN || (state==CANON_WAIT && child_done)) && completed_squares!=job_count;\n wire request_bad=state==IDLE && start &&'),
        ('request_bad || child_error || copy_bad || child_cancelled',
         'request_bad || child_error || copy_bad || child_cancelled || completion_bad')]
    for old,new in changes:
        if text.count(old)!=1:raise ValueError('S4_HOST_ACCEPTED_COMPLETION_ANCHOR')
        text=text.replace(old,new)
    return newtop,text


def prepare(n=32,p=16,*,paired=False,contexts=1,allow_full_constants=False):
    path=ROOT/'reference/stream27_host_core_v3.py';raw=path.read_text()
    if hashlib.sha256(raw.encode()).hexdigest()!=PIN:raise ValueError('S4_HOST_ACCEPTED_COMPLETION_PARENT_DRIFT')
    nodes=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='prepare']
    if len(nodes)!=1:raise ValueError('S4_HOST_ACCEPTED_COMPLETION_ENTRY')
    node=nodes[0];body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    namespace=dict(vars(parent));namespace['source']=source
    exec(compile(body,str(path)+'[accepted completion and real epoch wrap]','exec'),namespace)
    b=namespace['prepare'](n,p,paired=paired,contexts=contexts,allow_full_constants=allow_full_constants)
    if paired:
        name=b['top']+'.sv';text=b['files'][name]
        old='#(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) candidate (.*);'
        if text.count(old)!=1:raise ValueError('S4_HOST_PAIRED_EPOCH_SEED_ANCHOR')
        b['files'][name]=text.replace(old,'#(.EPOCH_SEED(EPOCH_SEED),.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) candidate (.*);')
        b['generated_sha256'][name]=hashlib.sha256(b['files'][name].encode()).hexdigest()
    path='reference/stream27_host_core_v4.py';b['source_dependencies'].append(path);b['source_sha256'][path]=root.sha(path)
    b['host_contract']['cold_epoch']+=' Completion count is checked at canonical handoff and copied commit. EPOCH_SEED default0; seeded65534 native is explicit modulo-wrap coverage, not an easier core.'
    return b
