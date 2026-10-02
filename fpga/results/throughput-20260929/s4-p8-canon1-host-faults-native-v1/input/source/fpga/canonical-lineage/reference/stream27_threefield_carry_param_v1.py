"""Isolated P8/default-P16 three-field + CRT + carry compiler fragment.

The shared field generators stay frozen. Unsigned warm field bytes for
N>=P^2 are inherited exactly; signed-cold admission is a separately named
shared-v3 top. This intermediate has no host/canonical or PRP promise.
"""
import hashlib
from pathlib import Path
from . import stream27_threefield_carry_v1 as parent
from . import stream27_shared_field_v3 as fields
from .stream27_shared_field_v2 import geometry
from . import stream27_blockcarry_param_model_v1 as proof

ROOT=parent.ROOT
COMPONENTS=[name for name in parent.COMPONENTS if name not in
            ('rtl/kernel/genefer_track_a4_setup_v1.sv','rtl/kernel/genefer_track_a4_blockcarry_lane_v1.sv')]+[proof.SETUP,proof.LANE]

def source(n,p,bundles,mode='warm'):
    aw=n.bit_length()-1
    oldtop,text=parent.source(n,bundles)
    top=f'genefer_stream27_threefield_carry_aw{aw}_p{p}_param_v1'+('_signed' if mode=='warm_signed' else '')
    changes=[
        (oldtop,top),('parameter int AW='+str(aw)+',P=16,CONTEXTS=1','parameter int AW='+str(aw)+',P='+str(p)+',CONTEXTS=1'),
        ('[AW-5:0]','[AW-$clog2(P)-1:0]'),('ROW_W=AW-4','ROW_W=AW-$clog2(P)'),
        ('genefer_track_a4_setup_v1 #(.AW(AW))','genefer_stream27_blockcarry_setup_param_v1 #(.AW(AW),.P(P))'),
        ('genefer_track_a4_blockcarry_lane_v1 #(.AW(AW))','genefer_stream27_blockcarry_lane_param_v1 #(.AW(AW),.P(P))'),
        ('// Static inverse physical lane reverse(b,4) -> natural block b.\n  localparam int PHYSICAL=((b&1)<<3)|((b&2)<<1)|((b&4)>>1)|((b&8)>>3);',
         '// Static inverse physical lane reverse(b,log2(P)) -> natural block b.\n  localparam int PHYSICAL=reverse_lane(b);'),
        (f'AW!={aw} || P!=16 || CONTEXTS!=1',f'AW!={aw} || P!={p} || CONTEXTS!=1'),
    ]
    for old,new in changes:
        proof.need(old in text,'S4_PARAM_WRAPPER_ANCHOR '+old[:60]); text=text.replace(old,new)
    anchor=' localparam int ROW_W=AW-$clog2(P),ROWS=1<<ROW_W,TAG_W=24+ROW_W;'
    function='''
 function automatic integer reverse_lane(input integer value);
  integer result;
  begin result=0;for(integer bit_index=0;bit_index<$clog2(P);bit_index=bit_index+1)begin
   result=(result<<1)|(value&1);value=value>>1;
  end reverse_lane=result;end
 endfunction'''
    proof.need(text.count(anchor)==1,'S4_PARAM_REVERSE_INSERT');text=text.replace(anchor,anchor+function)
    # Fixed CRT latency is sixteen stages; it is deliberately NOT changed to P.
    proof.need('crt_tag[0:15]' in text and 'd<16' in text and 'crt_double[15]' in text,'S4_PARAM_CRT16')
    return top,text

def prepare(n=32,p=16,*,contexts=1,allow_full_constants=False,mode='warm'):
    if (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('brief PAUSE')
    proof.need(p in (8,16) and contexts==1 and mode in ('warm','warm_signed'),'S4_PARAM_P8_P16_CONTEXTS1_ONLY')
    proof.bounds(n,p,1000000000);proof.parent_identity()
    bundles=[fields.prepare(n,p,f,mode=mode,contexts=contexts,allow_full_constants=allow_full_constants) for f in range(3)]
    files={};deps=[]
    for b in bundles:
        for name,text in b['files'].items():
            proof.need(name not in files or files[name]==text,'S4_PARAM_SHARED_COLLISION '+name);files[name]=text
        deps+=b['source_dependencies']
    for path in COMPONENTS:
        name=Path(path).name;text=(ROOT/path).read_text()
        proof.need(name not in files or files[name]==text,'S4_PARAM_COMPONENT_COLLISION '+name);files[name]=text
    top,text=source(n,p,bundles,mode);files[top+'.sv']=text
    deps=list(dict.fromkeys(deps+COMPONENTS+['reference/stream27_threefield_carry_v1.py',
        'reference/stream27_threefield_carry_param_v1.py','reference/stream27_blockcarry_param_model_v1.py',
        'reference/stream_ntt_blockwrap2_proposal.py']))
    g=dict(geometry(n,p));sink=g['sink_accept']
    g.update(crt_accept=sink,crt_output=sink+15,double_register=sink+16,carry_accept=sink+17,last_digit=g['first_digit']+n//p-1)
    return dict(top=top,files=files,rtl_sources=[name for name in files if name.endswith('.sv')],
        source_dependencies=deps,source_sha256={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in deps},
        generated_sha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in files.items()},
        geometry=g,parameters=dict(AW=n.bit_length()-1,P=p,CONTEXTS=1),mode=mode,
        scope='P8/defaultP16 represented-residue three-field/CRT/carry intermediate; no host/canonical/PRP/clock claim',
        setup_latency=97,full_N_numeric_NTT_performed=False,native_run_performed=False,RTL_qualified=False)
