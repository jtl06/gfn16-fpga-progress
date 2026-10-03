"""Private default-OFF age-register lookup on frozen COMPUTE60 only.

No edits to shared compute60/65 or endpoint sources. All non-lookup primitive
checks/table/tuple/FAST/report/retirement text is byte-literal. New ages are
reset-free data, masked by original valid; every accepted allocation initializes.
"""
import copy
import hashlib
import json
import re
from pathlib import Path
from . import stream27_r15_protocol_age_model as model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_protocol_age_bind.py'
MODEL='reference/stream27_r15_protocol_age_model.py'
BASE=ROOT/'results/throughput-20260929/trackS-r15-compute-native-v1'
CAPTURES={256:('aw8-normal','e27236e8a4d65ced6b8e63ab65fa868ef872b1bd66f27bac1142cc6feb443b61'),
 65536:('full-normal','079ea8523f4599bd521d3a3b3c513001b4e537912fb75ad5a2894447e4c7d428')}
LEAF='genefer_stream27_epoch_protocol_contexts_v1_payload_lookahead_v1_protected_field100_v1.sv'
LEAF_PIN='f15a0d82ceaab192417aed9a1e009c92447d662c0a4b69832bf06db99782e090'
PRIVATE_LEAF='genefer_stream27_epoch_protocol_contexts_r15_age_v1.sv'


def sha(x):return hashlib.sha256(x.encode() if isinstance(x,str) else x).hexdigest()
def need(ok,why):
    if not ok:raise ValueError('R15_PROTOCOL_AGE_'+why)


def capture(n):
    need(type(n) is int and n in CAPTURES,'GEOMETRY')
    directory,pin=CAPTURES[n];raw=(BASE/directory/'production-bundle.json').read_bytes()
    need(sha(raw)==pin,'FROZEN_COMPUTE60')
    b=json.loads(raw)
    need(len(b['files'])==60 and sha(b['files'][LEAF])==LEAF_PIN,'FROZEN_ACTUAL_LEAF')
    return b


AGE_BLOCK=''' // Reset-free data ages; original valid is the only lifetime authority.
 // Every actual allocation initializes. STOP does NOT freeze cycle_count,
 // so ages must likewise advance on all valid clocks, including quarantine.
 always_ff @(posedge clk)begin
  if(rst_n)begin
   for(int i=0;i<BANKS;i=i+1)if(valid[i])begin
    pw_age_q[i]<=pw_age_q[i]+32'd1;sink_age_q[i]<=sink_age_q[i]+32'd1;
   end
   if(frame_accept)begin
    pw_age_q[free_index]<=32'd1-32'(POINTWISE_FIRST);
    sink_age_q[free_index]<=32'd1-32'(SINK_FIRST);
   end
  end
 end
'''


def leaf(parent,*,bad_allocation=False,freeze_on_stop=False):
    need(sha(parent)==LEAF_PIN,'PRIVATE_PARENT_PIN')
    edits=[
      ('parameter int unsigned ROWS=8192,POINTWISE_FIRST=8308,SINK_FIRST=16618,',
       'parameter bit EPOCH_AGE_REG=0,\n parameter int unsigned ROWS=8192,POINTWISE_FIRST=8308,SINK_FIRST=16618,'),
      (' logic [31:0] pw_age[0:BANKS-1],sink_age[0:BANKS-1],cycle_count;',
       ' logic [31:0] pw_age[0:BANKS-1],sink_age[0:BANKS-1],cycle_count;\n logic [31:0] pw_age_q[0:BANKS-1],sink_age_q[0:BANKS-1];'),
      ('payload_age_next[i]=(cycle_count+32\'d1)-pw_first[i];',
       'payload_age_next[i]=EPOCH_AGE_REG ? pw_age_q[i]+32\'d1 : (cycle_count+32\'d1)-pw_first[i];'),
      ('pw_age[i]=cycle_count-pw_first[i];sink_age[i]=cycle_count-sink_first[i];',
       'pw_age[i]=EPOCH_AGE_REG ? pw_age_q[i] : cycle_count-pw_first[i];\n   sink_age[i]=EPOCH_AGE_REG ? sink_age_q[i] : cycle_count-sink_first[i];'),
      (' // synthesis translate_off\n always @(negedge clk)',AGE_BLOCK+' // synthesis translate_off\n always @(negedge clk)'),
    ]
    text=parent
    for old,new in edits:
        need(text.count(old)==1,'UNIQUE_LEAF_ANCHOR');text=text.replace(old,new,1)
    reverse=text
    for old,new in reversed(edits):
        need(reverse.count(new)==1,'UNIQUE_REVERSE');reverse=reverse.replace(new,old,1)
    need(reverse==parent,'LITERAL_REVERSE')
    if bad_allocation:text=text.replace("32'd1-32'(POINTWISE_FIRST)","32'd0-32'(POINTWISE_FIRST)")
    if freeze_on_stop:text=text.replace('if(valid[i])begin\n    pw_age_q', 'if(valid[i] && !stop)begin\n    pw_age_q')
    return text,edits


def bind(bundle,epoch_age_reg=0):
    need(type(epoch_age_reg) is int and epoch_age_reg in (0,1),'BOOL_FLAG')
    need(bundle==capture(bundle['geometry']['n']),'EXACT_COMPUTE60_PARENT')
    if not epoch_age_reg:return copy.deepcopy(bundle)
    out=copy.deepcopy(bundle);files=out['files'];text,edits=leaf(files[LEAF])
    files[LEAF]=text
    mapping={LEAF[:-3]:PRIVATE_LEAF[:-3]}
    # Rename dependency closure only. No shared library/generator writes.
    changed=True
    while changed:
        changed=False
        for name,body in files.items():
            module=name[:-3]
            if module not in mapping and any(re.search(r'\b'+re.escape(old)+r'\b',body) for old in mapping):
                mapping[module]=module+'_r15_age_v1';changed=True
    need(len(mapping)==7 and out['top'] in mapping,'EXACT_CALLER_CLOSURE')
    records={};new_files={}
    for name,body in files.items():
        if name[:-3] not in mapping:new_files[name]=body;continue
        before=body
        caller_edits=[]
        if name!=LEAF:
            need(body.count('CONTEXTS=2,')==1,'CALLER_DEFAULT_OFF_PARAMETER')
            old,new='CONTEXTS=2,','CONTEXTS=2,EPOCH_AGE_REG=0,'
            body=body.replace(old,new,1);caller_edits.append([old,new])
            # Real compile-time switch forwarded through the entire private
            # host->warm->arithmetic->threefields->protocol dependency closure.
            for child in mapping:
                if child==name[:-3]:continue
                old=child+' #('
                if old not in body:continue
                need(body.count(old)==1,'SINGLE_DIRECT_CHILD')
                new=child+' #(.EPOCH_AGE_REG(EPOCH_AGE_REG),'
                body=body.replace(old,new,1);caller_edits.append([old,new])
        for old,new in mapping.items():body=re.sub(r'\b'+re.escape(old)+r'\b',new,body)
        reverse=body
        for old,new in mapping.items():reverse=re.sub(r'\b'+re.escape(new)+r'\b',old,reverse)
        for old,new in reversed(caller_edits):
            need(reverse.count(new)==1,'CALLER_FLAG_REVERSE');reverse=reverse.replace(new,old,1)
        need(reverse==before,'CALLER_REVERSE:'+name)
        newname=mapping[name[:-3]]+'.sv';new_files[newname]=body
        records[newname]=dict(parent=name,identifier_reverse_exact=True,parameter_edits=caller_edits)
    need(len(new_files)==60,'PRIVATE_60_SOURCE_COUNT')
    newtop=mapping[out['top']]
    deps=list(dict.fromkeys(out['source_dependencies']+[SELF,MODEL]))
    out.update(files=new_files,top=newtop,rtl_sources=list(new_files),
      parameters=dict(out['parameters'],EPOCH_AGE_REG=1),source_dependencies=deps,
      source_sha256={p:sha((ROOT/p).read_bytes()) for p in deps},
      generated_sha256={p:sha(t) for p,t in new_files.items()})
    out['r15_protocol_age']=dict(enabled=True,parent_top=bundle['top'],parent_capture=CAPTURES[bundle['geometry']['n']],
      parent_leaf_sha256=LEAF_PIN,private_leaf=PRIVATE_LEAF,module_mapping=mapping,modified=records,
      primitive_edits=edits,model_proof=model.prove(),valid_age_width=32,
      allocation_post_NBA_seed='1-FIRST',stop_ticks_advance=True,reset_free_invalid_age_data=True,
      tuple_check_FAST_report_table_retirement_literal=True,geometry_unchanged=True,latency_delta=0,
      native_qualified=False,clock_area_gain_claim=False,promotion_allowed=False,
      lean_build_label='host GL assumed (unimplemented)')
    return out


def prepare(n=256,epoch_age_reg=0):return bind(capture(n),epoch_age_reg)
