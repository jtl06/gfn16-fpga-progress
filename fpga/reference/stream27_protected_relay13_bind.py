"""Final R13 protected ingress-relay batch on immutable field100.

All three new flags default OFF. Disabled returns the exact protected
field100 bundle, not a regenerated/renamed substitute. The primary batch
adds matched add-A/term, square/inverse, and matching forward ingress tuples;
CRT transport and inner-BF splitting remain OFF. Full checking, FAST public
containment, R6 cold acceptance retirement and R9 publication drain persist.
"""
import copy
import hashlib
import re
from pathlib import Path
from . import stream27_protected_field100_bind as parent_api
from . import stream27_context_storage_combo_transport11_bind as relay
from . import stream27_protected_relay13_model as model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_protected_relay13_bind.py'
MODEL='reference/stream27_protected_relay13_model.py'
PARENT_PIN='84b14c2ce04d37aec04d7eadb42eec04a9e34c0d1412ed927b8e1a0f60757ebd'
RELAY_PIN='5375b3fd76f78b342b2ee1a6a931629ae4e3883dcc2b8091e9157f9bc3ab9d3b'
MODEL_PIN='fdd5a171af84d3e62c334727ada44f33c69f69c4bb2ef416fcc2e456de3934d4'
SOURCE_READY=True
FLAGS=model.FLAGS
PRIMARY_FLAGS=dict(INVERSE_INGRESS_REG=1,TERM_JOIN_TRANSPORT_REG=1,FORWARD_INGRESS_REG=1)


def sha(raw):return hashlib.sha256(raw if isinstance(raw,bytes) else raw.encode()).hexdigest()
def need(ok,label):
    if not ok:raise ValueError('PROTECTED_RELAY13_'+label)
def once(text,old,new):
    need(text.count(old)==1,'UNIQUE_ANCHOR:'+old[:90]);return text.replace(old,new,1)
def edit(text,old,new,ops):
    text=once(text,old,new);ops.append((old,new));return text
def reverse(text,ops):
    for old,new in reversed(ops):text=once(text,new,old)
    return text


FORWARD_DECL=''' // R13: complete forward ingress; field FAST fences origin and consumer.
 logic forward_slot_q,forward_start_q;logic [24:0] forward_generation_q;
 logic [LANES*28-1:0] forward_data_q;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin forward_slot_q<=0;forward_start_q<=0;end
  else begin
   forward_slot_q<=digit_slot && !stop;
   forward_start_q<=digit_slot && launch_tag[ROW_W] && !stop;
  end
 end
 always_ff @(posedge clk)if(rst_n && digit_slot && !stop)begin
  forward_generation_q<=launch_tag[ROW_W+25:ROW_W+1];forward_data_q<=input_wide;
 end
'''


def field(text,flags,before,after):
    original=text
    changed,ops=relay.field(text,dict(TERM_JOIN_TRANSPORT_REG=flags['TERM_JOIN_TRANSPORT_REG'],
        INVERSE_INGRESS_REG=flags['INVERSE_INGRESS_REG']),before,after)
    if flags['FORWARD_INGRESS_REG']:
        ct=re.search(r' (genefer_stream28_merged_ct_\w+) #\(.GEN_W\(25\)\) forward_transform \(',changed)
        need(ct is not None,'ACTUAL_MATCHING_FORWARD_BOUNDARY')
        changed=edit(changed,ct.group(0),FORWARD_DECL+ct.group(0),ops)
        changed=edit(changed,
            '.in_slot_valid(digit_slot),.frame_start(digit_slot && launch_tag[ROW_W]),.quarantine(transform_quarantine[0]),',
            '.in_slot_valid(forward_slot_q && !stop),.frame_start(forward_start_q),.quarantine(transform_quarantine[0]),',ops)
        changed=edit(changed,'.generation_in(launch_tag[ROW_W+25:ROW_W+1]),',
            '.generation_in(forward_generation_q),',ops)
        changed=edit(changed,'.data_in(input_wide),','.data_in(forward_data_q),',ops)
        changed=edit(changed,f'.POINTWISE_FIRST({before["pointwise_accept"]})',
            f'.POINTWISE_FIRST({after["pointwise_accept"]})',ops)
    # Calendar rebinds are distinct from the protocol's authority and raw
    # retirement body. No product/E4/cache/payload write checks are changed.
    need(reverse(changed,ops)==original,'FIELD_ALL_BYTES_REVERSE')
    return changed,ops


def prepare(n=256,*,p=16,contexts=2,enabled=0,inverse_ingress_reg=0,
            term_join_transport_reg=0,forward_ingress_reg=0):
    flags=dict(INVERSE_INGRESS_REG=inverse_ingress_reg,
        TERM_JOIN_TRANSPORT_REG=term_join_transport_reg,FORWARD_INGRESS_REG=forward_ingress_reg)
    need(n in (256,65536) and p==16 and contexts==2,'CLOSED_GEOMETRY')
    need(all(type(v) is int and v in (0,1) for v in (enabled,*flags.values())),'BOOLEAN_FLAGS')
    need(sha((ROOT/parent_api.SELF).read_bytes())==PARENT_PIN,'FROZEN_FIELD100_PARENT')
    parent=parent_api.prepare(n,p=p,contexts=contexts,enabled=1,
        **{key.lower():1 for key in parent_api.FLAGS})
    if not enabled:
        need(not any(flags.values()),'DISABLED_NO_REQUESTED_CHANGES')
        return parent
    need(any(flags.values()),'ENABLE_AN_ACTUAL_RELAY')
    need(sha((ROOT/relay.SELF).read_bytes())==RELAY_PIN,'FROZEN_RELAY_HELPER')
    need(sha((ROOT/MODEL).read_bytes())==MODEL_PIN,'FROZEN_OWN_CALENDAR')
    out=copy.deepcopy(parent);files=out['files'];baseline=copy.deepcopy(files)
    before=parent['geometry'];after=model.geometry(before,**{k.lower():v for k,v in flags.items()})
    plan=model.schedule(after);records={};renames={}
    for name,text in list(files.items()):
        if name.startswith('genefer_stream27_shared_warm_aw'):
            changed,ops=field(text,flags,before,after)
            files[name]=changed;records[name]=dict(new_file=name,edits=ops)
            renames[name[:-3]]=name[:-3]+'_relay13_v1'
        elif name.startswith(('genefer_stream27_threefield_carry_aw','genefer_stream27_warm_contexts_aw')):
            renames[name[:-3]]=name[:-3]+'_relay13_v1'
    oldtop=parent['top'];newtop=f'genefer_stream27_host_contexts_aw{after["aw"]}_p16_protected_relay13_v1'
    renames[oldtop]=newtop
    for name,text in list(files.items()):
        changed=text
        for old,new in renames.items():changed=re.sub(r'\b'+re.escape(old)+r'\b',new,changed)
        newname=renames.get(name[:-3],name[:-3])+'.sv'
        if changed!=text:
            records.setdefault(name,dict(new_file=name,edits=[]))['edits'].append((text,changed))
            records[name]['new_file']=newname
        if newname!=name:files.pop(name)
        files[newname]=changed
    host=files[newtop+'.sv'];ops=[]
    oldsecond=next(c['accept'] for c in parent['two_context_schedule']['correction']
        if c['tag'][0]==1 and c['tag'][3]==0)
    second=next(c['accept'] for c in plan['correction'] if c['tag'][0]==1 and c['tag'][3]==0)
    host=edit(host,f'CONTEXT_OFFSET={before["warm_interval"]//2},SECOND_CORRECTION={oldsecond};',
        f'CONTEXT_OFFSET={after["warm_interval"]//2},SECOND_CORRECTION={second};',ops)
    for key,value in dict(CRT_TRANSPORT_REG=0,**flags).items():
        host=edit(host,',CONTEXTS=2',f',CONTEXTS=2,{key}={value}',ops)
    files[newtop+'.sv']=host;records[oldtop+'.sv']['edits']+=ops
    for name,row in records.items():
        need(reverse(files[row['new_file']],row['edits'])==baseline[name],'EVERY_FUNCTIONAL_AND_NAMESPACE_BYTE_REVERSE')
    # Imports reuse literal source construction/scalar mechanics only. The
    # R11 graph, lean watchdog/circuit, RTL tests and clocks are not composed.
    deps=list(dict.fromkeys(parent['source_dependencies']+[SELF,MODEL,relay.SELF,
        'reference/stream27_context_transport11_model.py']))
    out.update(top=newtop,geometry=after,two_context_schedule=plan,
        parameters=dict(parent['parameters'],CRT_TRANSPORT_REG=0,**flags),
        rtl_sources=list(files),source_dependencies=deps,
        source_sha256={path:sha((ROOT/path).read_bytes()) for path in deps},
        generated_sha256={name:sha(text) for name,text in files.items()})
    need(len(files)==58 and 'LEAN_PRODUCTION' not in out['parameters'],'PROTECTED58_NO_LEAN')
    out['context_protected_relay13']=dict(source_ready=SOURCE_READY,parent_top=oldtop,
        flags=flags,CRT_TRANSPORT_REG=0,default_disabled_exact_field100=True,
        lean_production=False,inner_BF_arithmetic_unchanged=True,arithmetic_profile_unchanged=True,
        calendar_before=before,calendar_after=after,
        physical_feedback_FIFO_rows=before['existing_feedback_delay'],explicit_feedback_register_rows=1,
        field_boundary_edges_added=sum(flags.values()),field_to_CRT_edges_added=0,
        field_report_lag=1,arithmetic_report_lag=2,host_report_lag=1,public_FAST_origin_lag=0,
        protocol_FAST_and_raw_tuple_retirement_literal=True,field100_fold_and_carry_receivers_literal=True,
        cold_one_shot_acceptance_retirement_literal=True,host_full56_COPY_DRAIN_literal=True,
        publication_fence_edges_per_job=1,copy_edges=n+4,
        source_declared_cold_first_edges=[204,204+after['warm_interval']//2],
        source_declared_solo_first_edge=104,
        healthy_calendars={str(k):model.event_calendar(after,k) for k in (2,100,1000,1911814)},
        solo2=model.event_calendar(after,2,solo=True),
        tuple_model=model.prove_tuples(),source_edits=records,
        declared_new_register_bits=3*(891*term_join_transport_reg+475*inverse_ingress_reg+475*forward_ingress_reg),
        register_bits_not_mapped_cost=True,logic_level_cap_proven=False,
        native_qualified=False,clock_or_area_gain_claim=False)
    return out
