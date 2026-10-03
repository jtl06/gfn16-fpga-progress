"""Check-preserving field100 batch on exact protected R9.

Protected timing10 remedies are composed, R11 transports are NOT composed.
Protocol's original accepted sticky is the immediate field FAST authority.
Only reports/transform quarantine transport lag; public masks remain FAST.
No native, mapped-area or timing claim follows from source construction.
"""
import copy
import hashlib
import re
from pathlib import Path
from . import stream27_context_storage_combo_timing10_bind as timing
from . import stream27_context_feedback12_bind as ingress
from . import stream27_context_feedback12_model as calendar
from . import stream27_protected_field100_model as model
from . import stream27_canonical_fold_payload_bind as fold

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_protected_field100_bind.py'
SOURCE_READY=True
PROTOCOL='genefer_stream27_epoch_protocol_contexts_v1_payload_lookahead_v1'
NEW_PROTOCOL=PROTOCOL+'_protected_field100_v1'
SETTER='!stop && (admission_bad || join_bad || (|child_pending) || (|child_error) || inverse_pending || inverse_error || protocol_pending || protocol_error)'
FLAGS=dict(FIELD_PROTOCOL_ORIGIN_FAST=1,FIELD_ERROR_REPORT_REG=1,
    DATAPATH_QUARANTINE_REG=1,FEEDBACK_INGRESS_REG=1,AUTO_CORRECTION_INGRESS_REG=1,
    C0_ADMISSION_DIRECT=1,CANONICAL_FOLD_PAYLOAD_REG=1,CARRY_QUARANTINE_LOCAL=1)


def sha(raw):return hashlib.sha256(raw if isinstance(raw,bytes) else raw.encode()).hexdigest()
def need(ok,label):
    if not ok:raise ValueError('PROTECTED_FIELD100_'+label)
def once(text,old,new):
    need(text.count(old)==1,'UNIQUE_ANCHOR:'+old[:70]);return text.replace(old,new,1)
def edit(text,old,new,ops):
    text=once(text,old,new);ops.append((old,new));return text
def reverse(text,ops):
    for old,new in reversed(ops):text=once(text,new,old)
    return text


def protocol(text):
    original=text;ops=[]
    text=edit(text,'module '+PROTOCOL+' #','module '+NEW_PROTOCOL+' #',ops)
    text=edit(text,' input logic clk,rst_n,quarantine,external_fault_pending,',
        ' input logic clk,rst_n,quarantine,external_fault_pending,\n input logic [1:0] fault_report_copies,',ops)
    # This specialized leaf is ONLY called with quarantine==its own sticky.
    # Delayed report copies imply that sticky on every reachable binary trace.
    text=edit(text,'   if(!stop && (bad || external_fault_pending))out_error<=1;',
        '   out_error<=out_error || (|fault_report_copies) || bad || external_fault_pending;',ops)
    text=edit(text,' // synthesis translate_off\n initial if(ROWS<2',
        ' // synthesis translate_off\n'
        ' always @(negedge clk)if(rst_n && (quarantine!=out_error || ((|fault_report_copies) && !out_error)))\n'
        '  $fatal(1,"FIELD100_SELF_QUARANTINE_AND_REPORT_COPY_INDUCTION");\n initial if(ROWS<2',ops)
    need(reverse(text,ops)==original,'PROTOCOL_ALL_BYTES_REVERSE')
    return text,ops


def field(text):
    original=text;ops=[]
    text=edit(text,'out_eligible,out_error,fault_pending,','out_eligible,out_error,fault_pending,out_error_fast,',ops)
    text=edit(text,' wire stop=controller_error;',' wire stop=out_error_fast;',ops)
    text=edit(text,' assign out_error=controller_error;',
        ' assign out_error=controller_error;\n assign out_error_fast=protocol_error;',ops)
    text=edit(text,'assign fault_pending=controller_error ||',
        'assign fault_pending=out_error_fast ||',ops)
    text=edit(text,'.fault_set('+SETTER+'),','.fault_set(out_error_fast),',ops)
    text=edit(text,'   if('+SETTER+')\n    controller_error<=1;',
        '   // Report accepted sticky origin; NEVER requalify by later STOP.\n   controller_error<=out_error_fast;',ops)
    text=edit(text,'.quarantine(stop),.external_fault_pending(',
        '.quarantine(stop),.fault_report_copies(transform_quarantine),.external_fault_pending(',ops)
    text=edit(text,PROTOCOL+' #',NEW_PROTOCOL+' #',ops)
    text=edit(text,'"S4_FAULT_REPLICAS_SAME_ORIGIN_EDGE"',
        '"FIELD100_REPORT_COPY_ALIGNMENT_NOT_FAST_ORIGIN"',ops)
    # The same original state/table/accept/commit checks now use immediate
    # protocol FAST through stop; the controller is reporting-only.
    need('wire stop=out_error_fast;' in text and 'assign out_error_fast=protocol_error;' in text,
         'EXPLICIT_TYPED_FAST')
    need(reverse(text,ops)==original,'FIELD_ALL_BYTES_REVERSE')
    return text,ops


def arithmetic(text):
    original=text;ops=[]
    text=edit(text,'field_eligible,field_error,field_pending;',
        'field_eligible,field_error,field_pending,field_fast;',ops)
    for index in range(3):
        text=edit(text,f'.out_error(field_error[{index}]),',
            f'.out_error(field_error[{index}]),.out_error_fast(field_fast[{index}]),',ops)
    text=edit(text,'assign error_barrier=out_error || (|field_error) || local_fault_q;',
        'assign error_barrier=out_error || (|field_fast) || local_fault_q;',ops)
    text=edit(text,'if(fault_pending)out_error<=1;',
        'if((|field_error) || local_fault_q)out_error<=1;',ops)
    # Each carry receiver has a local sticky transport of accepted FAST.
    # This may admit private faulted-job work for one edge; EVERY public
    # valid/eligible/accept/publication mask remains immediate error_barrier.
    text=edit(text,'  // Static inverse physical lane reverse(b,log2(P)) -> natural block b.',
        '  (* preserve, dont_merge *) logic carry_quarantine_q;\n'
        '  always_ff @(posedge clk or negedge rst_n)begin\n'
        '   if(!rst_n)carry_quarantine_q<=0;\n'
        '   else carry_quarantine_q<=carry_quarantine_q || error_barrier;\n'
        '  end\n  // Static inverse physical lane reverse(b,log2(P)) -> natural block b.',ops)
    text=edit(text,'.begin_block(begin_carry),.in_valid(coefficient_valid),',
        '.begin_block(joined && join_start && !carry_quarantine_q),\n'
        '   .in_valid(doubled_valid && !carry_quarantine_q),',ops)
    need(reverse(text,ops)==original,'ARITHMETIC_ALL_BYTES_REVERSE')
    return text,ops


def prepare(n=256,*,p=16,contexts=2,enabled=0,**flags):
    need(n in (256,65536) and p==16 and contexts==2,'CLOSED_GEOMETRY')
    need(type(enabled) is int and enabled in (0,1),'BOOLEAN')
    need(set(flags)<=set(k.lower() for k in FLAGS),'CLOSED_FLAG_ROSTER')
    chosen={key:flags.get(key.lower(),0) for key in FLAGS}
    need(all(type(v) is int and v in (0,1) for v in chosen.values()),'BOOLEAN_FLAGS')
    if not enabled:
        need(not any(chosen.values()),'DISABLED_NO_CHANGES')
        return timing.capture(n)
    need(chosen==FLAGS,'ONE_CLOSED_BATCH_ONLY')
    parent=timing.prepare(n,p=p,contexts=contexts,enabled=1,lean_production=0)
    out=copy.deepcopy(parent);files=out['files'];baseline=copy.deepcopy(files)
    records={};renames={};before=parent['geometry']
    after=calendar.geometry(before,feedback_ingress_reg=1,auto_correction_ingress_reg=1,c0_admission_direct=1)
    plan=calendar.schedule(after)
    for name,text in list(files.items()):
        ops=[];changed=text;newname=name
        if name==PROTOCOL+'.sv':changed,ops=protocol(text);newname=NEW_PROTOCOL+'.sv'
        elif name.startswith('genefer_stream27_shared_warm_aw'):
            changed,first=ingress.field(text);changed,second=field(changed);ops=first+second
            renames[name[:-3]]=name[:-3]+'_protected_field100_v1'
        elif name.startswith('genefer_stream27_warm_contexts_aw'):
            changed,ops=ingress.warm(text);renames[name[:-3]]=name[:-3]+'_protected_field100_v1'
        elif name.startswith('genefer_stream27_threefield_carry_aw'):
            changed,ops=arithmetic(text);renames[name[:-3]]=name[:-3]+'_protected_field100_v1'
        elif name==fold.OLD+'.sv':
            changed=fold.bind_leaf(text,enabled=1);ops=fold.edits();newname=fold.NEW+'.sv'
            renames[fold.OLD]=fold.NEW
        if ops:
            records[name]=dict(new_file=newname,edits=ops)
            files.pop(name);files[newname]=changed
    oldtop=out['top'];newtop=f'genefer_stream27_host_contexts_aw{after["aw"]}_p16_protected_field100_v1'
    renames[oldtop]=newtop
    for name,text in list(files.items()):
        changed=text
        for old,new in renames.items():changed=re.sub(r'\b'+re.escape(old)+r'\b',new,changed)
        newname=renames.get(name[:-3],name[:-3])+'.sv'
        if changed!=text:
            origin=next((k for k,v in records.items() if v['new_file']==name),name)
            records.setdefault(origin,dict(new_file=name,edits=[]))['edits'].append((text,changed))
            records[origin]['new_file']=newname
        files.pop(name);files[newname]=changed
    host=files[newtop+'.sv'];ops=[]
    oldsecond=next(c['accept'] for c in parent['two_context_schedule']['correction'] if c['tag'][0]==1 and c['tag'][3]==0)
    second=next(c['accept'] for c in plan['correction'] if c['tag'][0]==1 and c['tag'][3]==0)
    host=edit(host,f'CONTEXT_OFFSET={before["warm_interval"]//2},SECOND_CORRECTION={oldsecond};',
        f'CONTEXT_OFFSET={after["warm_interval"]//2},SECOND_CORRECTION={second};',ops)
    for key,value in chosen.items():host=edit(host,',CONTEXTS=2',f',CONTEXTS=2,{key}={value}',ops)
    files[newtop+'.sv']=host;records[oldtop+'.sv']['edits']+=ops
    for origin,row in records.items():
        need(reverse(files[row['new_file']],row['edits'])==baseline[origin],'EVERY_LOCAL_AND_NAMESPACE_BYTE_REVERSE')
    # Importing fixed source helpers is not composition of their optional
    # lean circuits/transports. Capture their closure honestly for replay.
    helper=ingress.prepare(n,enabled=1,lean_production=0,feedback_ingress_reg=1,
        auto_correction_ingress_reg=1,c0_admission_direct=1)
    deps=list(dict.fromkeys(out['source_dependencies']+helper['source_dependencies']+[
        SELF,'reference/stream27_protected_field100_model.py',fold.SELF,fold.MODEL]))
    out.update(top=newtop,geometry=after,two_context_schedule=plan,
        parameters=dict(out['parameters'],**chosen),rtl_sources=list(files),
        source_dependencies=deps,source_sha256={path:sha((ROOT/path).read_bytes()) for path in deps},
        generated_sha256={name:sha(text) for name,text in files.items()})
    need(len(files)==58 and 'LEAN_PRODUCTION' not in out['parameters'],'PROTECTED58_NO_LEAN')
    need(not any(k in out['parameters'] for k in ('CRT_TRANSPORT_REG','INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG')),
         'R11_TRANSPORTS_NOT_COMPOSED')
    out['context_protected_field100']=dict(source_ready=SOURCE_READY,flags=chosen,
        default_disabled_exact_protected_R9=True,protected_timing10_remedies=True,R11_transports_composed=False,
        protocol_origin_model=model.prove_protocol_origin(),report_chain_model=model.prove_report_chain(),
        field_FAST_origin_edges_added=0,field_report_lag=1,arithmetic_report_lag=2,host_report_lag=1,
        CT_GS_quarantine_acceptance_lag=1,numeric_tail_activity_not_bounded_by_one_edge=True,
        carry_quarantine_receiving_edges=1,raw_lease_retirement_checks_literal=True,
        private_quarantine_model=model.prove_private_quarantine(),
        warm_FAST_latch_and_host_COPY_DRAIN_literal=True,publication_fence_edges_per_job=1,copy_edges=n+4,
        calendar_before=before,calendar_after=after,
        healthy_calendars={str(k):calendar.event_calendar(after,k) for k in (2,100,1000,1911814)},
        solo2=calendar.event_calendar(after,2,solo=True),source_edits=records,
        binary_inductive_only=True,arbitrary_FF_or_XZ_immunity=False,
        hardware_logic_level_cap_proven=False,
        targeted_classes=['replica_feedback_to_field_and_protocol','carry_feedback_to_field_admission',
            'fault_to_private_carry_gating','scratch_fold_range_write_data'],
        native_qualified=False,clock_or_mapped_area_claim=False)
    return out
