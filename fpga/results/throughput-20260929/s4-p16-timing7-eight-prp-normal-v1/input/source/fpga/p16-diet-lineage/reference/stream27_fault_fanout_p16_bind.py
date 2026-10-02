"""Separate P16 C1 seam; frozen P8 binder and native snapshots untouched.

The two existing same-D same-edge sticky copies are lane-independent. This
API widens only the copied bundle's admission scope to P16, with exact setter,
reset/public-error and reverse-to-parent proofs. Native P16 gates and measured
composed physical benefit are not inherited from P8.
"""
import copy
from pathlib import Path
from . import stream27_fault_fanout_bind as parent

ROOT=parent.ROOT
SELF='reference/stream27_fault_fanout_p16_bind.py'
LEAF=parent.LEAF


def bind(bundle,*,enabled=1):
    parent.need(type(enabled) is int and enabled in (0,1),'S4_P16_FAULT_REPLICAS_FLAG')
    result=copy.deepcopy(bundle)
    if enabled==0:return result
    parent.need(bundle['mode'] in ('warm','warm_signed') and bundle['parameters']['P']==16
                and bundle['parameters']['CONTEXTS']==1,'S4_P16_FAULT_REPLICAS_WARM_C1')
    parent.need('QUARANTINE_REPLICAS' not in bundle['parameters'],'S4_P16_FAULT_REPLICAS_ALREADY_BOUND')
    oldtop=bundle['top'];top=oldtop+'_quarantine_replicas_v1';original=bundle['files'][oldtop+'.sv']
    parent.need(original.count(parent.DECL)==1 and original.count('if('+parent.SETTER+')')==1,
                'S4_P16_FAULT_REPLICAS_EXACT_SETTER')
    parent.need(original.count('controller_error<=0;')==1 and original.count('controller_error<=1;')==1
                and original.count('assign out_error=controller_error;')==1,'S4_P16_FAULT_REPLICAS_RESET_PUBLIC')
    text=original.replace(parent.DECL,parent.DECL+parent.INSERT,1)
    for index,name in enumerate(('forward_transform','inverse_transform')):
        text=parent.connect_transform(text,name,'.quarantine(stop)',f'.quarantine(transform_quarantine[{index}])')
    for old,new in (('module '+oldtop+' #','module '+top+' #'),(',CONTEXTS=1',',CONTEXTS=1,QUARANTINE_REPLICAS=1'),
                    ('CONTEXTS!=1','CONTEXTS!=1 || QUARANTINE_REPLICAS!=1'),('endmodule\n',parent.ASSERT+'endmodule\n')):
        parent.need(text.count(old)==1,'S4_P16_FAULT_REPLICAS_ROOT_ABI');text=text.replace(old,new,1)
    parent.need(parent.reverse_root(text,oldtop,top)==original,'S4_P16_FAULT_REPLICAS_EXACT_REVERSE')
    result['files'].pop(oldtop+'.sv');result['files'][top+'.sv']=text
    result['files'][Path(LEAF).name]=(ROOT/LEAF).read_text()
    result['top']=top;result['parameters']=dict(result['parameters'],QUARANTINE_REPLICAS=1)
    result['source_dependencies']=list(dict.fromkeys(result['source_dependencies']+[parent.SELF,SELF,LEAF]))
    result['source_sha256']={name:parent.sha((ROOT/name).read_bytes()) for name in result['source_dependencies']}
    result['rtl_sources']=[name for name in result['files'] if name.endswith('.sv')]
    result['generated_sha256']={name:parent.sha(value.encode()) for name,value in result['files'].items()}
    result['fault_fanout']=dict(schema='s4-p16-field-same-edge-quarantine-replicas-v1',parent_top=oldtop,
        parent_root_sha256=parent.sha(original.encode()),new_top=top,local_copies=2,
        destinations=['forward_transform','inverse_transform'],setter=parent.SETTER,
        same_origin_edge=True,reverse_to_parent_exact=True,geometry_unchanged=result['geometry']==bundle['geometry'],
        public_fault_unchanged=True,pending_diagnostic_unchanged=True,commit_tail_unchanged=True,
        physical_gain_measured=False,whole_clock_claim=False,promotion_allowed=False)
    result['scope']='P16 C1 same-edge transform-local fault copies; no inherited P8 numeric, physical or whole qualification.'
    return result
