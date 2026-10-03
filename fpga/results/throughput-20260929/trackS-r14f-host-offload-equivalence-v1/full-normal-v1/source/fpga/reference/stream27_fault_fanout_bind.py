"""Isolated same-edge field quarantine replicas; shared emitters untouched.

Only the forward/inverse transform quarantine connections consume new same-D
sticky FFs. Public controller_error, pending diagnostics, accepted-origin-edge
tails, immediate lease/tag/live rejection, arithmetic and calendars are exact
parent source. Source attributes request retention; placement benefit is not
inferred. Native/whole physical qualification is separate.
"""
import copy
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_fault_fanout_bind.py'
LEAF='rtl/kernel/genefer_stream27_quarantine_replicas_v1.sv'
SETTER='!stop && (admission_bad || join_bad || (|child_pending) || (|child_error) || inverse_pending || inverse_error || protocol_pending || protocol_error)'
DECL=' wire stop=controller_error;\n'
INSERT=''' // Same-D, same-origin-edge transform-local sticky quarantine copies.
 wire [1:0] transform_quarantine;
 genefer_stream27_quarantine_replicas_v1 #(.COPIES(2)) fault_replicas (
  .clk,.rst_n,.fault_set('''+SETTER+'''),.quarantine(transform_quarantine));
'''
ASSERT=''' // synthesis translate_off
 always @(negedge clk)if(rst_n && transform_quarantine!={2{controller_error}})
  $fatal(1,"S4_FAULT_REPLICAS_SAME_ORIGIN_EDGE");
 // synthesis translate_on
'''


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def connect_transform(text,name,before,after):
    anchor=' '+name+' ('
    need(text.count(anchor)==1,'S4_FAULT_REPLICAS_TRANSFORM '+name)
    start=text.index(anchor);end=text.index(');',start)+2
    call=text[start:end]
    need(call.count(before)==1,'S4_FAULT_REPLICAS_QUARANTINE_PORT '+name)
    return text[:start]+call.replace(before,after,1)+text[end:]


def reverse_root(text,parent_top,new_top):
    need(text.count(INSERT)==1 and text.count(ASSERT)==1,'S4_FAULT_REPLICAS_REVERSE_INSERTS')
    text=text.replace(INSERT,'',1).replace(ASSERT,'',1)
    for index,name in enumerate(('forward_transform','inverse_transform')):
        text=connect_transform(text,name,f'.quarantine(transform_quarantine[{index}])','.quarantine(stop)')
    need(text.count('module '+new_top+' #')==1,'S4_FAULT_REPLICAS_REVERSE_TOP')
    text=text.replace('module '+new_top+' #','module '+parent_top+' #',1)
    need(text.count(',QUARANTINE_REPLICAS=1')==1 and text.count(' || QUARANTINE_REPLICAS!=1')==1,
         'S4_FAULT_REPLICAS_REVERSE_FLAG')
    return text.replace(',QUARANTINE_REPLICAS=1','',1).replace(' || QUARANTINE_REPLICAS!=1','',1)


def bind(bundle,*,enabled=1):
    need(type(enabled) is int and enabled in (0,1),'S4_FAULT_REPLICAS_FLAG')
    result=copy.deepcopy(bundle)
    if enabled==0:return result
    need(bundle['mode'] in ('warm','warm_signed'),'S4_FAULT_REPLICAS_WARM_FIELD_ONLY')
    need(bundle['parameters']['P']==8 and bundle['parameters']['CONTEXTS']==1,
         'S4_FAULT_REPLICAS_P8_CONTEXTS1')
    need('QUARANTINE_REPLICAS' not in bundle['parameters'],'S4_FAULT_REPLICAS_ALREADY_BOUND')
    oldtop=bundle['top'];top=oldtop+'_quarantine_replicas_v1';parent=bundle['files'][oldtop+'.sv']
    need(parent.count(DECL)==1 and parent.count('if('+SETTER+')')==1,
         'S4_FAULT_REPLICAS_EXACT_ORIGINAL_SETTER')
    need(parent.count('controller_error<=0;')==1 and parent.count('controller_error<=1;')==1,
         'S4_FAULT_REPLICAS_EXACT_ORIGINAL_RESET_SET')
    need(parent.count('assign out_error=controller_error;')==1,'S4_FAULT_REPLICAS_PUBLIC_ERROR')
    text=parent.replace(DECL,DECL+INSERT,1)
    for index,name in enumerate(('forward_transform','inverse_transform')):
        text=connect_transform(text,name,'.quarantine(stop)',f'.quarantine(transform_quarantine[{index}])')
    need(text.count('module '+oldtop+' #')==1 and text.count(',CONTEXTS=1')==1 and text.count('CONTEXTS!=1')==1,
         'S4_FAULT_REPLICAS_FIELD_ABI')
    text=text.replace('module '+oldtop+' #','module '+top+' #',1)
    text=text.replace(',CONTEXTS=1',',CONTEXTS=1,QUARANTINE_REPLICAS=1',1)
    text=text.replace('CONTEXTS!=1','CONTEXTS!=1 || QUARANTINE_REPLICAS!=1',1)
    need(text.count('endmodule\n')==1,'S4_FAULT_REPLICAS_FIELD_END')
    text=text.replace('endmodule\n',ASSERT+'endmodule\n',1)
    need(reverse_root(text,oldtop,top)==parent,'S4_FAULT_REPLICAS_EXACT_REVERSE_PARENT')
    result['files'].pop(oldtop+'.sv');result['files'][top+'.sv']=text
    result['files'][Path(LEAF).name]=(ROOT/LEAF).read_text()
    result['top']=top;result['parameters']=dict(result['parameters'],QUARANTINE_REPLICAS=1)
    result['source_dependencies']=list(dict.fromkeys(result['source_dependencies']+[SELF,LEAF]))
    result['source_sha256']={name:sha((ROOT/name).read_bytes()) for name in result['source_dependencies']}
    result['rtl_sources']=[name for name in result['files'] if name.endswith('.sv')]
    result['generated_sha256']={name:sha(value.encode()) for name,value in result['files'].items()}
    result['fault_fanout']=dict(schema='s4-field-same-edge-quarantine-replicas-v1',
        parent_top=oldtop,parent_root_sha256=sha(parent.encode()),new_top=top,
        local_copies=2,destinations=['forward_transform','inverse_transform'],setter=SETTER,
        same_origin_edge=True,reverse_to_parent_exact=True,geometry_unchanged=result['geometry']==bundle['geometry'],
        public_fault_unchanged=True,pending_diagnostic_unchanged=True,commit_tail_unchanged=True,
        physical_gain_measured=False,whole_clock_claim=False,promotion_allowed=False)
    result['scope']='Isolated P8 field same-D same-edge quarantine replicas; actual native and composed physical benefit pending.'
    return result
