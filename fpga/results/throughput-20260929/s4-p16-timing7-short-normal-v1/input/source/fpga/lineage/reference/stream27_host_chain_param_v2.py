"""Additive shared P8/P16 host binding of validity-qualified field starts.

Only three field top identifiers and their internal forward-start expression
change. The real generic carry, FIFO, full-width final selector, canonical RAM,
shadow image, legacy scalar ABI, reset duration and calendars stay unchanged.
"""
import hashlib
from . import stream27_host_chain_param_v1 as parent
from . import stream27_shared_field_v3 as old_fields
from . import stream27_shared_field_v4 as fields

ROOT=parent.ROOT
PARENT_PIN='6f9d8799c9c2afa3bd62466973e21308827fbbfb422a08587042c8c8286c0ce5'


def prepare(n=32,p=16,*,paired=False,contexts=1,allow_full_constants=False):
    if parent.root.sha('reference/stream27_host_chain_param_v1.py')!=PARENT_PIN:
        raise ValueError('S4_VALID_START_HOST_PARENT_DRIFT')
    b=parent.prepare(n,p,paired=paired,contexts=contexts,allow_full_constants=allow_full_constants)
    for field in range(3):
        kwargs=dict(mode='warm_signed',contexts=contexts,allow_full_constants=allow_full_constants)
        old=old_fields.prepare(n,p,field,**kwargs);new=fields.prepare(n,p,field,**kwargs)
        oldtop,newtop=old['top'],new['top'];oldname=oldtop+'.sv'
        if b['files'].get(oldname)!=old['files'][oldname]:raise ValueError('S4_VALID_START_HOST_FIELD_DRIFT')
        b['files'].pop(oldname)
        b['files']={name:text.replace(oldtop,newtop) for name,text in b['files'].items()}
        b['files'][newtop+'.sv']=new['files'][newtop+'.sv']
    deps=['reference/stream27_shared_field_v4.py','reference/stream27_host_chain_param_v2.py']
    b['source_dependencies']=list(dict.fromkeys(b['source_dependencies']+deps))
    b['source_sha256']={path:parent.root.sha(path) for path in b['source_dependencies']}
    b['rtl_sources']=[name for name in b['files'] if name.endswith('.sv')]
    b['generated_sha256']={name:hashlib.sha256(text.encode()).hexdigest() for name,text in b['files'].items()}
    b['reset_delta']='Only internal forward frame_start qualified by matching row validity; one asserted reset edge, all valid/fault reset logic and host assertions unchanged.'
    return b
