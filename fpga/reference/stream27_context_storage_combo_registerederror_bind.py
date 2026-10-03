"""R9 protected batch: direct canonical bound and registered error summary.

Default OFF is immutable R7. Raw field checks and their sticky controllers
remain literal. Global reporting samples registered field errors and a local
sticky collector; a registered-source early safety fence and full-owner
publication drain prevent the one-edge report delay leaking output. Healthy
publication costs one extra edge per job. No clock/area/native claim.
"""
import copy
import re

from . import stream27_context_storage_combo_faultlocal_bind as parent_api
from . import stream27_context_storage_combo_directbound_bind as direct
from . import stream27_context_registered_error_model as model

ROOT=parent_api.ROOT
SELF='reference/stream27_context_storage_combo_registerederror_bind.py'
MODEL='reference/stream27_context_registered_error_model.py'
PARENT_PIN='847dc928e3c84e565d8971fbd05e65ff2e3d50627e0d8b8347ff2ae025918d06'
DIRECT_PIN='d7b179631988fd9269f9e3ff955f9e28f58270051380d0149bfbb4a66077be56'
sha=parent_api.sha
once=parent_api.once
FIELD_PENDING='assign fault_pending=controller_error || (|child_pending) || protocol_pending || (!stop && (admission_bad || join_bad));'
FIELD_SET='if(!stop && (admission_bad || join_bad || (|child_pending) || (|child_error) || inverse_pending || inverse_error || protocol_pending || protocol_error))\n    controller_error<=1;'
ARITH_PENDING=''' assign fault_pending=out_error || setup_error || (|field_error) || (|field_pending) ||
  (|lane_error) || join_bad || carry_bad || admission_bad;
'''
ARITH_SUMMARY=''' // Every raw field_pending reaches its unchanged local controller on this edge.
 // Do not route its deep combinational cone into the global sticky report.
 assign error_barrier=out_error || (|field_error) || local_fault_q;
 assign fault_pending=error_barrier;
'''
LOCAL_DECL=''' logic local_fault_q;
 wire local_fault_now=setup_error || (|lane_error) || join_bad || carry_bad || admission_bad;
'''
LOCAL_FF=''' always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)local_fault_q<=0;
  else if(local_fault_now)local_fault_q<=1;
 end
'''
PUB_COMMIT='''      published[canonical_owner]<=1;done_q[canonical_owner]<=1;phase[canonical_owner]<=IDLE;canonical_owned<=0;
      next_epoch[canonical_owner]<=job_epoch[canonical_owner]+16'(job_count[canonical_owner]);
'''
PUB_PROPOSAL='''      publish_pending<=1;publish_context<=canonical_owner;
      publish_owner<=live_owner[canonical_owner*56+:56];
'''
PUB_DRAIN='''   // Hold the scratch lease through one coherent publication fence edge.
   if(publish_pending)begin
    publish_pending<=0;
    if(!canonical_owned || canonical_owner!=publish_context || phase[publish_context]!=COPY_DRAIN ||
     publish_owner!=live_owner[publish_context*56+:56] || copy_requested!=(AW+1)'(N) ||
     copy_issued!=(AW+1)'(N) || copy_committed!=(AW+1)'(N) || shadow_commit_ack)local_error<=1;
    else if(!safety_error)begin
     published[publish_context]<=1;done_q[publish_context]<=1;phase[publish_context]<=IDLE;canonical_owned<=0;
     next_epoch[publish_context]<=job_epoch[publish_context]+16'(job_count[publish_context]);
    end
   end
'''
PUBLIC_ERROR=' assign error=local_error || child_error || canon_error;\n'


def need(ok,label):
    if not ok:
        raise ValueError('C2_REGISTERED_ERROR_'+label)


def replace_record(text,before,after,ops):
    text=once(text,before,after)
    ops.append((before,after))
    return text


def restore(text,ops):
    for before,after in reversed(ops):
        text=once(text,after,before)
    return text


def bind(bundle,*,enabled=0):
    need(type(enabled) is int and enabled in (0,1),'BOOLEAN_SWITCH')
    out=copy.deepcopy(bundle)
    if not enabled:
        return out
    need(sha((ROOT/parent_api.SELF).read_bytes())==PARENT_PIN and
         sha((ROOT/direct.SELF).read_bytes())==DIRECT_PIN,'FROZEN_PARENT_AND_BOUND_RECIPE')
    parent=parent_api.prepare(out['geometry']['n'],enabled=1)
    need(out==parent,'EXACT_R7_ONLY_NO_MIXTURE')
    proof=model.prove()
    fields=[name for name in out['files'] if name.startswith('genefer_stream27_shared_warm_aw')]
    need(len(fields)==3 and all(out['files'][name].count(FIELD_PENDING)==1 and
         out['files'][name].count(FIELD_SET)==1 for name in fields),'RAW_PENDING_LOCAL_CONTROLLER_COVERAGE')
    out=direct.bind(out,enabled=1)
    baseline=copy.deepcopy(out['files'])
    records={}
    aw=out['geometry']['aw']
    old_arith=next(name[:-3] for name in out['files'] if name.startswith('genefer_stream27_threefield_carry_aw'))
    old_warm=next(name[:-3] for name in out['files'] if name.startswith('genefer_stream27_warm_contexts_aw'))
    new_arith=f'genefer_stream27_threefield_carry_aw{aw}_p16_registered_error_v1'
    new_warm=f'genefer_stream27_warm_contexts_aw{aw}_p16_registered_error_v1'
    original=out['files'].pop(old_arith+'.sv');text=original;ops=[]
    text=replace_record(text,'out_error,fault_pending,frame_accept,correction_accept,',
                        'out_error,fault_pending,error_barrier,frame_accept,correction_accept,',ops)
    text=replace_record(text,' logic join_bad,carry_bad,admission_bad;\n',
                        ' logic join_bad,carry_bad,admission_bad;\n'+LOCAL_DECL,ops)
    text=replace_record(text,ARITH_PENDING,ARITH_SUMMARY,ops)
    count=text.count('!out_error');need(count>0,'ARITHMETIC_ELIGIBILITY_FENCE')
    before=text;text=text.replace('!out_error','!error_barrier').replace('.cancel(out_error)', '.cancel(error_barrier)')
    need(text.replace('!error_barrier','!out_error').replace('.cancel(error_barrier)', '.cancel(out_error)')==before,
         'ARITHMETIC_TOKEN_GUARD_REVERSE')
    # Whole-text step is reversal evidence only, never executed as a fit script.
    ops.append((before,text))
    text=replace_record(text,' always_ff @(posedge clk or negedge rst_n)begin\n  if(!rst_n)begin out_error<=0;',
                        LOCAL_FF+' always_ff @(posedge clk or negedge rst_n)begin\n  if(!rst_n)begin out_error<=0;',ops)
    text=replace_record(text,'module '+old_arith+' #','module '+new_arith+' #',ops)
    need(restore(text,ops)==original,'ARITHMETIC_ALL_BYTES_REVERSE')
    out['files'][new_arith+'.sv']=text;records[new_arith+'.sv']=ops
    original=out['files'].pop(old_warm+'.sv');text=original;ops=[]
    text=replace_record(text,'out_error,fault_pending,frame_accept,correction_accept,',
                        'out_error,fault_pending,error_barrier,frame_accept,correction_accept,',ops)
    text=replace_record(text,'wire child_error,child_pending,child_frame_accept,child_correction_accept;',
                        'wire child_error,child_pending,child_barrier,child_frame_accept,child_correction_accept;',ops)
    text=replace_record(text,' assign out_error=local_error || child_error;\n',
                        ' assign out_error=local_error || child_error;\n assign error_barrier=local_error || child_barrier;\n',ops)
    text=replace_record(text,'if(child_error || collision || count_bad || command_bad || cold_request_bad)local_error<=1;',
                        'if(child_barrier || collision || count_bad || command_bad || cold_request_bad)local_error<=1;',ops)
    text=replace_record(text,'if(local_error || child_error)begin active<=0;warm_done<=0;warm_cancelled<=2\'b11;end',
                        'if(error_barrier)begin active<=0;warm_done<=0;warm_cancelled<=2\'b11;end',ops)
    text=replace_record(text,'.out_error(child_error),.fault_pending(child_pending),',
                        '.out_error(child_error),.fault_pending(child_pending),.error_barrier(child_barrier),',ops)
    text=replace_record(text,old_arith+' #',new_arith+' #',ops)
    text=replace_record(text,'module '+old_warm+' #','module '+new_warm+' #',ops)
    need(restore(text,ops)==original,'WARM_ALL_BYTES_REVERSE')
    out['files'][new_warm+'.sv']=text;records[new_warm+'.sv']=ops
    oldtop=out['top'];top=f'genefer_stream27_host_contexts_aw{aw}_p16_storage_combo_registerederror_v1'
    original=out['files'].pop(oldtop+'.sv');text=original;ops=[]
    head,body=text.split(');\n',1)
    need(body.count(PUBLIC_ERROR)==1,'PUBLIC_ERROR_ASSIGN')
    body=once(body,PUBLIC_ERROR,' __R9_PUBLIC_ERROR_ASSIGN__\n')
    body=re.sub(r'(?<![\w.])error\b','safety_error',body)
    body=once(body,' __R9_PUBLIC_ERROR_ASSIGN__\n',PUBLIC_ERROR+
              ' assign safety_error=local_error || child_error_barrier || canon_error;\n')
    body=' wire child_error_barrier,safety_error;\n'+body
    modified=head+');\n'+body
    ops.append((text,modified));text=modified
    text=replace_record(text,' logic capture_req_d;\n',
                        ' logic capture_req_d;\n logic publish_pending,publish_context;logic [55:0] publish_owner;\n',ops)
    text=replace_record(text,'   local_error<=0;jobs<=0;job_feed<=0;job_double<=0;done_q<=0;published<=0;cycles<=0;\n',
                        '   local_error<=0;jobs<=0;job_feed<=0;job_double<=0;done_q<=0;published<=0;cycles<=0;\n   publish_pending<=0;publish_context<=0;publish_owner<=0;\n',ops)
    text=replace_record(text,'    jobs<=start_contexts;cycles<=0;anchor_valid<=0;first_cold_inflight<=0;published<=published & ~start_contexts;\n',
                        '    jobs<=start_contexts;cycles<=0;anchor_valid<=0;first_cold_inflight<=0;published<=published & ~start_contexts;\n    publish_pending<=0;publish_context<=0;publish_owner<=0;\n',ops)
    text=replace_record(text,PUB_COMMIT,PUB_PROPOSAL,ops)
    text=replace_record(text,'   if(shadow_commit_ack && canonical_owned)begin\n',
                        PUB_DRAIN+'   if(shadow_commit_ack && canonical_owned)begin\n',ops)
    text=replace_record(text,'.out_error(child_error),.fault_pending(child_pending),',
                        '.out_error(child_error),.fault_pending(child_pending),.error_barrier(child_error_barrier),',ops)
    text=replace_record(text,old_warm+' #',new_warm+' #',ops)
    text=replace_record(text,'module '+oldtop+' #','module '+top+' #',ops)
    text=replace_record(text,',CANONICAL_C0_DIRECT=1',',CANONICAL_C0_DIRECT=1,ERROR_AGGREGATION_REGISTERED=1',ops)
    need(restore(text,ops)==original,'HOST_ALL_BYTES_REVERSE_TO_DIRECTBOUND')
    need(text.count(PUBLIC_ERROR)==1 and 'output logic error,' in text and
         text.index('wire child_error_barrier,safety_error;')<text.index('!safety_error'),
         'PUBLIC_ABI_AND_EXPLICIT_BARRIER_DECLARATION')
    out['files'][top+'.sv']=text;records[top+'.sv']=ops
    out.update(top=top,parameters=dict(out['parameters'],ERROR_AGGREGATION_REGISTERED=1))
    out['source_dependencies']=list(dict.fromkeys(out['source_dependencies']+[MODEL,SELF]))
    out['source_sha256']={path:sha((ROOT/path).read_bytes()) for path in out['source_dependencies']}
    out['rtl_sources']=list(out['files']);out['generated_sha256']={name:sha(text) for name,text in out['files'].items()}
    need(len(out['files'])==55 and all(out['files'][name]==body for name,body in baseline.items()
         if name not in (old_arith+'.sv',old_warm+'.sv',oldtop+'.sv')),'ALL_OTHER_DIRECTBOUND_FILES_EXACT')
    out['context_registered_error']=dict(parent_top=parent['top'],parent_generated_sha256=parent['generated_sha256'],
        roster=['CANONICAL_C0_DIRECT','ERROR_AGGREGATION_REGISTERED'],model=proof,
        arithmetic_raw_field_checks_and_controllers_literal=True,early_barrier_registered_sources_only=True,
        public_error_max_added_edges=1,healthy_warm_and_cold_calendar_delta=0,
        publication_fence_edges_per_job=1,copy_cycles_extra_per_job=1,
        joint_publication_delta=[1,2],solo_publication_delta=1,healthy_equal_pair_extra_edges=2,
        full56_publication_owner_count_lease_check=True,reset_and_newjob_clear=True,
        public_ports_unchanged=True,reverse_to_directbound_all_bytes=True,
        reverse_to_protected_R7_exact=True,reversal_records=records,
        native_qualified=False,clock_or_area_claim=False,promotion_allowed=False)
    return out


def prepare(n=256,*,p=16,contexts=2,enabled=0):
    return bind(parent_api.prepare(n,p=p,contexts=contexts,enabled=1),enabled=enabled)
