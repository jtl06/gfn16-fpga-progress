"""Additive signed cold-image admission, preserving native-qualified warm RTL.

T5b accepts -1 at any loaded digit position, not just the exceptional image's
first word. The frozen digit reducer already converts -1 to ordinary p-1;
this successor permits that exact full32-bit word at admission. No other
negative value is legal. Warm feedback remains unsigned [0,b-1]. For b>=2,
|-1|<=b-1, so the absolute coefficient bound is unchanged; this is not an
oracle or unsigned reinterpretation of arbitrary negative words.
"""
import hashlib
from . import stream27_shared_field_v2 as parent

ROOT=parent.ROOT
PARENT_PIN='05eab167ccb00c2bb6a74475ec2b3c84549f0b328ac4d5dbf9e1faea73657fd2'


def prepare(n=65536,p=16,field=0,*,mode='warm',contexts=1,allow_full_constants=False):
    if hashlib.sha256((ROOT/'reference/stream27_shared_field_v2.py').read_bytes()).hexdigest()!=PARENT_PIN:
        raise ValueError('S4_SIGNED_INPUT_PARENT_DRIFT')
    if mode not in ('probe','warm','warm_signed'):raise ValueError('S4_SIGNED_INPUT_MODE')
    b=parent.prepare(n,p,field,mode='warm' if mode=='warm_signed' else mode,
        contexts=contexts,allow_full_constants=allow_full_constants)
    if mode!='warm_signed':return b
    oldtop=b['top'];s=b['files'].pop(oldtop+'.sv');top=oldtop+'_signed_host_v3'
    old='for(int lane=0;lane<LANES;lane=lane+1)if(data_in[lane*32+:32]>=digit_base)admission_bad=1;'
    new="for(int lane=0;lane<LANES;lane=lane+1)if(data_in[lane*32+:32]>=digit_base && data_in[lane*32+:32]!=32'hffffffff)admission_bad=1;"
    if s.count(old)!=1:raise ValueError('S4_SIGNED_INPUT_ADMISSION_ANCHOR')
    s=s.replace(old,new).replace('module '+oldtop+' #','module '+top+' #',1)
    b['files'][top+'.sv']=s;b['top']=top;b['rtl_sources']=[name for name in b['files'] if name.endswith('.sv')]
    path='reference/stream27_shared_field_v3.py';b['source_dependencies'].append(path)
    b['source_sha256'][path]=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    b['generated_sha256']={name:hashlib.sha256(text.encode()).hexdigest() for name,text in b['files'].items()}
    b['mode']=mode;b['signed_cold_admission']='Only exact signed32 -1 additionally legal; existing frozen reducer, roots and arithmetic unchanged.'
    return b
