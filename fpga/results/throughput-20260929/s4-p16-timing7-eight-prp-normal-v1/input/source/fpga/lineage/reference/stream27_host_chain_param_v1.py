"""One P8/P16 host/control compiler, retaining frozen P16 output by default.

P8 consumes the separately owned real generic carry/setup compiler fragment;
no field fork or blackbox is emitted. Frozen field/transform generators remain
shared with probe and warm configurations. Arithmetic qualification is separate
from preparing this mechanical width/permutation/profile-constant composition.
"""
import ast
import hashlib
import json
from . import stream27_host_core_v1 as root
from . import stream27_host_chain_v1 as host
from . import stream27_warm_chain_v1 as warm
from . import stream27_chain_canonical_v1 as canonical

ROOT=root.ROOT
PINS={
 'reference/stream27_host_core_v1.py':'7a6cee18c198d09a473e24a89f651b94a32402fbb14ea21cd66717cf106dca20',
 'reference/stream27_host_chain_v1.py':'0ca7724092b7b93dfe5976f8dac023cf90aab7a483e877cc3f126acee04c3759',
 'reference/stream27_warm_chain_v1.py':'6ac232e394dd16a45f7a4dd5f4e1f7b92bace0fc60f5673e134d7cec0572148d',
 'reference/stream27_chain_canonical_v1.py':'eecac249e29c9be29c88d795b92fd2180c95bc8236db7ea74da90c2096188e46',
}
P8_PINS={
 'reference/stream27_threefield_carry_param_v1.py':'6384084d622870c0e7d36a24311887786292dac7781ca3fca4c8d4b8497af96f',
 'rtl/kernel/genefer_stream27_blockcarry_setup_param_v1.sv':'c9ba8163c8bb43afecf1afee07a8a55c4eb89539318cf235b83508ab692f4f26',
 'rtl/kernel/genefer_stream27_blockcarry_lane_param_v1.sv':'8a458519272e89e635eb5cd7e6b2d07c93c8d3b1fc0f44874ba67aeccca77d4b',
}


def replace(s,old,new):
    if s.count(old)!=1:raise ValueError('S4_SHARED_HOST_PARAM_ANCHOR:'+old)
    return s.replace(old,new)


def reverse_expression(variable,p):
    width=p.bit_length()-1
    return '|'.join(f'(({variable}&{1<<i})'+(f'<<{width-1-2*i}' if width-1-2*i>0 else f'>>{2*i-width+1}' if width-1-2*i<0 else '')+')' for i in range(width))


def common(top,s,p):
    new=top.replace('_p16_','_p'+str(p)+'_').replace('_v1','_param_v1')
    s=replace(s,'module '+top+' #','module '+new+' #')
    if 'P=16,CONTEXTS=1' in s:s=replace(s,'P=16,CONTEXTS=1','P='+str(p)+',CONTEXTS=1')
    elif s.count('P='+str(p)+',CONTEXTS=1')!=1:raise ValueError('S4_SHARED_HOST_PARAM_HEADER')
    s=replace(s,'P!=16 || CONTEXTS!=1','P!='+str(p)+' || CONTEXTS!=1')
    s=s.replace('[AW-5:0]','[AW-$clog2(P)-1:0]')
    s=s.replace('ROW_W=AW-4','ROW_W=AW-$clog2(P)')
    return new,s


def warm_source(n,child,g,p):
    top,s=warm.source(n,child,g);top,s=common(top,s,p)
    s=replace(s,'((lane&1)<<3)|((lane&2)<<1)|((lane&4)>>1)|((lane&8)>>3)',reverse_expression('lane',p))
    return top,s


def canonical_source(n,child,text,p):
    return common(*canonical.source(n,child,text),p)


def host_source(n,child,p):
    top,s=host.source(n,child);top,s=common(top,s,p)
    s=replace(s,'K=2*N+384','K=2*N+24*P')
    s=replace(s,'((lane&1)<<3)|((lane&2)<<1)|((lane&4)>>1)|((lane&8)>>3)',reverse_expression('lane',p))
    s=s.replace('Natural block -> physical reverse4','Natural block -> physical reverse(log2P)')
    return top,s


def prepare(n=32,p=16,*,paired=False,contexts=1,allow_full_constants=False):
    if p not in (8,16) or contexts!=1:raise ValueError('S4_SHARED_HOST_P8_P16_CONTEXTS1')
    if (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('brief PAUSE')
    for path,pin in PINS.items():
        if root.sha(path)!=pin:raise ValueError('S4_SHARED_HOST_PARAM_PARENT_DRIFT:'+path)
    if p==16:
        b=host.prepare(n,p,paired=paired,contexts=contexts,allow_full_constants=allow_full_constants)
        path='reference/stream27_host_chain_param_v1.py';b['source_dependencies'].append(path);b['source_sha256'][path]=root.sha(path)
        return b
    # The component owner hands this real arithmetic fragment back separately.
    # Until it exists, P8 preparation is unavailable rather than emitting a stub.
    for path,pin in P8_PINS.items():
        if root.sha(path)!=pin:raise ValueError('S4_SHARED_HOST_P8_HANDOFF_DRIFT:'+path)
    from .stream27_threefield_carry_param_v1 import prepare as arithmetic
    def compile_arithmetic(n,p,**kwargs):return arithmetic(n,p,mode='warm_signed',**kwargs)
    def compile_warm(n,p,**kwargs):
        b=root.bind(warm.parent,compile_core=compile_arithmetic,source=lambda n,c,g:warm_source(n,c,g,p))(n,p,**kwargs)
        g=b['geometry']
        if g['warm_interval']<=g['carry_done']-g['first_digit']:raise ValueError('S4_SHARED_FULL_ORDINAL_NONOVERLAP')
        return b
    def compile_canonical(n,p,**kwargs):
        return root.bind(canonical.base,compile_warm=compile_warm,source=lambda n,c,s:canonical_source(n,c,s,p))(n,p,paired=False,**kwargs)
    raw=(ROOT/'reference/stream27_host_core_v1.py').read_text()
    node=next(x for x in ast.parse(raw).body if isinstance(x,ast.FunctionDef) and x.name=='prepare')
    body=''.join(raw.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    body=replace(body,"if p!=16:raise ValueError('S4_HOST_P8_CARRY_WRAPPER_NOT_QUALIFIED')", "if p not in (8,16):raise ValueError('S4_SHARED_HOST_PARAM_P')")
    def composable(n,child):
        top,s=host_source(n,child,p);temporary=top.replace('host_chain','host_core_long')
        return temporary,s.replace(top,temporary)
    namespace=dict(vars(root));namespace.update(source=composable,signed_chain=compile_canonical)
    exec(compile(body,'[S4 shared P host composition]','exec'),namespace)
    b=namespace['prepare'](n,p,paired=paired,contexts=contexts,allow_full_constants=allow_full_constants)
    def rename(s):return s.replace('host_t5b_paired_long','host_chain_t5b_paired').replace('host_core_long','host_chain')
    b['files']={rename(name):rename(s) for name,s in b['files'].items()};b['top']=rename(b['top'])
    if paired:
        name=b['top']+'.sv';b['files'][name]=replace(b['files'][name],'#(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) candidate (.*);',
          '#(.EPOCH_SEED(EPOCH_SEED),.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) candidate (.*);')
    deps=b['source_dependencies']+list(PINS)+['reference/stream27_host_core_v2.py','reference/stream27_host_core_v3.py',
      'reference/stream27_host_core_v4.py','reference/stream27_host_core_v5.py','reference/stream27_host_chain_param_v1.py']
    b['source_dependencies']=list(dict.fromkeys(deps));b['source_sha256']={path:root.sha(path) for path in b['source_dependencies']}
    b['generated_sha256']={name:hashlib.sha256(s.encode()).hexdigest() for name,s in b['files'].items()}
    b['rtl_sources']=[name for name in b['files'] if name.endswith('.sv')]
    b['scope']='Shared P8 mechanical long-host composition source; real generic carry/setup fragment, no field fork/stub. Integrated native/whole physical pending.'
    b['host_contract']=dict(host.prepare(32)['host_contract'])
    b['host_contract'].update(profile_guard='max(2N+5,ceil(2*(2N+24P)/3)+1)..1e9',extra_shadow_bits=32*n,canonical_bits=32*n,
      parameterization='P8/P16 real shared field + generic carry/setup, ROW_W=AW-log2P, reverse(log2P) static natural/physical routing; no hidden narrower core.')
    b['cycle_contract']=host.cycle_contract(n,b['geometry'])
    return b
