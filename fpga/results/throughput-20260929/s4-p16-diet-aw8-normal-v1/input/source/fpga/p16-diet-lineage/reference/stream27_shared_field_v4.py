"""Shared probe/warm successor: internal forward starts require row validity.

Reset clears producer eligibility, not its tag payload. The forward CT checks
start-without-slot as a genuine cadence fault; therefore the field must not
present an unoccupied reducer/front-delay tag as a live CT start. External
admission and all CT cadence/fault logic remain unchanged. No pipeline edge,
arithmetic, root, memory, or active-row metadata changes. Frozen probes stay
byte-identical; the same successor serves both probe and warm configurations.
"""
import hashlib
from . import stream27_shared_field_v3 as parent

ROOT=parent.ROOT
PARENT_PIN='42d786e62801476c1444861973bae16c98b5d8a74b5d22c1d50c5043d83de546'


def prepare(n=65536,p=16,field=0,*,mode='warm',contexts=1,allow_full_constants=False):
    if hashlib.sha256((ROOT/'reference/stream27_shared_field_v3.py').read_bytes()).hexdigest()!=PARENT_PIN:
        raise ValueError('S4_INTERNAL_START_PARENT_DRIFT')
    b=parent.prepare(n,p,field,mode=mode,contexts=contexts,allow_full_constants=allow_full_constants)
    if mode!='probe':
        oldtop=b['top'];text=b['files'].pop(oldtop+'.sv')
        tag='launch_tag' if 'wire [ROW_W+8:0] launch_tag;' in text else 'digit_tag[0]'
        old='.frame_start('+tag+'[ROW_W])'
        new='.frame_start(digit_slot && '+tag+'[ROW_W])'
        if text.count(old)!=1:raise ValueError('S4_INTERNAL_START_ANCHOR')
        top=oldtop+'_valid_start_v4'
        text=text.replace(old,new).replace('module '+oldtop+' #','module '+top+' #',1)
        b['files'][top+'.sv']=text;b['top']=top
    path='reference/stream27_shared_field_v4.py'
    b['source_dependencies']=list(dict.fromkeys(b['source_dependencies']+[path]))
    b['source_sha256'][path]=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    b['rtl_sources']=[name for name in b['files'] if name.endswith('.sv')]
    b['generated_sha256']={name:hashlib.sha256(text.encode()).hexdigest() for name,text in b['files'].items()}
    b['internal_start_contract']='Forward CT internal start is matching digit_slot AND producer tag start; unreset invalid payload is not a control token. External admission and real cadence faults unchanged.'
    return b
