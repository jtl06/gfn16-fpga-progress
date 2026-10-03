"""Default-OFF coherent feedback/correction ingress on frozen R11.

Cold host correction retirement and publication fences stay literal. Raw
command/collision faults retain their original edge; queued descriptors are
checked again before actual frame acceptance. Numeric C0 reexpression is
exact for every unsigned32 base and signed32 word, including base0.
"""
import copy
import hashlib
import re
from pathlib import Path

from . import stream27_context_storage_combo_transport11_source_v2 as parent_api
from . import stream27_context_feedback12_model as model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_context_feedback12_bind.py'
MODEL='reference/stream27_context_feedback12_model.py'
PARENT_PIN='792851152b0a637a83885a72fb33a972601547470ae377723228411a188c2262'
MODEL_PIN='917c809ac2ffabdae99be409ac0808882b613f912c06d2b8e8053b6db24fa546'
SOURCE_READY=True
FLAGS=('FEEDBACK_INGRESS_REG','AUTO_CORRECTION_INGRESS_REG','C0_ADMISSION_DIRECT')


def sha(raw):return hashlib.sha256(raw if isinstance(raw,bytes) else raw.encode()).hexdigest()
def need(ok,label):
    if not ok:raise ValueError('C2_FEEDBACK12_'+label)
def once(text,old,new):
    need(text.count(old)==1,'UNIQUE_ANCHOR:'+old[:90]);return text.replace(old,new,1)
def edit(text,old,new,ops):
    text=once(text,old,new);ops.append((old,new));return text
def reverse(text,ops):
    for old,new in reversed(ops):text=once(text,new,old)
    return text


C0_FUNCTION=''' // Exact uint32(base-1) identity: base0 must retain unsigned underflow.
 function automatic logic correction_c0_ok(input logic [31:0] word,input logic [31:0] base);
  logic signed [32:0] wide_value;logic [32:0] magnitude;
  begin wide_value=$signed({word[31],word});magnitude=word[31] ? 33'(-wide_value) : 33'(wide_value);
   correction_c0_ok=(base==32'd0) || magnitude<{1'b0,base};end
 endfunction
'''

OLD_CONTROLS=''' wire feedback_context=feedback_owner[24];
 wire command_needed=feedback_slot && feedback_start && latched_feed[feedback_context] && !local_error;
 wire command_bad=command_needed && (!command_valid[feedback_context] ||
  command_index[feedback_context*32+:32]!=launched[feedback_context] ||
  command_generation[feedback_context*8+:8]!=chain_generation[feedback_context]);
 wire collision=(cold_slot && feedback_slot) || (cold_correction && auto_correction);
 wire count_bad=cold_slot && frame_start && (square_count==0 || (!feed_mode && square_count>32'd32));
 wire cold_request_bad=in_slot_valid && active[context_in] && cold_remaining[context_in]==0;
 wire child_error,child_pending,child_barrier,child_frame_accept,child_correction_accept;
 wire arithmetic_digit_valid,arithmetic_digit_start,arithmetic_digit_eligible;
 wire arithmetic_boundary_valid,arithmetic_boundary_eligible,arithmetic_frame_done;
 wire child_slot=(cold_slot || feedback_slot) && !command_bad;
 wire child_start=(feedback_slot ? feedback_start : frame_start) && !command_bad;
 wire child_context=feedback_slot ? feedback_context : context_in;
 wire selected_double=feedback_start ? (latched_feed[feedback_context] ? command_double[feedback_context] :
  latched_mask[feedback_context][launched[feedback_context][4:0]]) : current_double[feedback_context];
'''

NEW_CONTROLS=''' // R12: keep raw feedback/cold origins; transport only complete accepted proposals.
 wire raw_feedback_context=feedback_owner[24];
 wire raw_command_needed=feedback_slot && feedback_start && latched_feed[raw_feedback_context] && !local_error;
 wire raw_command_bad=raw_command_needed && (!command_valid[raw_feedback_context] ||
  command_index[raw_feedback_context*32+:32]!=launched[raw_feedback_context] ||
  command_generation[raw_feedback_context*8+:8]!=chain_generation[raw_feedback_context]);
 wire raw_collision=(cold_slot && feedback_slot) || (cold_correction && auto_correction);
 wire count_bad=cold_slot && frame_start && (square_count==0 || (!feed_mode && square_count>32'd32));
 wire cold_request_bad=in_slot_valid && active[context_in] && cold_remaining[context_in]==0;
 wire child_error,child_pending,child_barrier,child_frame_accept,child_correction_accept;
 wire arithmetic_digit_valid,arithmetic_digit_start,arithmetic_digit_eligible;
 wire arithmetic_boundary_valid,arithmetic_boundary_eligible,arithmetic_frame_done;
 logic feedback_slot_q,feedback_start_q,feedback_double_q,feedback_feed_q;
 logic [P*32-1:0] feedback_data_q;logic [24:0] feedback_owner_q;
 logic [31:0] feedback_base_q,feedback_index_q;logic [7:0] feedback_command_generation_q;
 logic auto_correction_q;logic [P*32-1:0] auto_c0_q,auto_c1_q;
 logic auto_context_q;logic [15:0] auto_epoch_q;logic [7:0] auto_generation_q;
 wire feedback_context=feedback_owner_q[24];
 wire delayed_feedback_slot=feedback_slot_q && !error_barrier;
 wire delayed_auto_correction=auto_correction_q && !error_barrier;
 wire command_needed=delayed_feedback_slot && feedback_start_q && feedback_feed_q;
 wire queued_command_bad=command_needed && (!command_valid[feedback_context] ||
  command_index[feedback_context*32+:32]!=feedback_index_q ||
  command_generation[feedback_context*8+:8]!=feedback_command_generation_q ||
  launched[feedback_context]!=feedback_index_q ||
  chain_generation[feedback_context]!=feedback_command_generation_q);
 wire command_bad=raw_command_bad || queued_command_bad;
 wire collision=raw_collision || (cold_slot && delayed_feedback_slot) ||
  (cold_correction && delayed_auto_correction);
 wire child_slot=(cold_slot || delayed_feedback_slot) && !command_bad;
 wire child_start=(delayed_feedback_slot ? feedback_start_q : frame_start) && !command_bad;
 wire child_context=delayed_feedback_slot ? feedback_context : context_in;
 wire raw_selected_double=feedback_start ? (latched_feed[raw_feedback_context] ? command_double[raw_feedback_context] :
  latched_mask[raw_feedback_context][launched[raw_feedback_context][4:0]]) : current_double[raw_feedback_context];
 wire selected_double=feedback_double_q;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin feedback_slot_q<=0;feedback_start_q<=0;auto_correction_q<=0;end
  else if(error_barrier || collision || command_bad || count_bad || cold_request_bad)begin
   feedback_slot_q<=0;feedback_start_q<=0;auto_correction_q<=0;
  end else begin
   feedback_slot_q<=feedback_slot;feedback_start_q<=feedback_slot && feedback_start;
   auto_correction_q<=auto_correction;
  end
 end
 always_ff @(posedge clk)if(rst_n && !error_barrier && !collision && !command_bad && !count_bad && !cold_request_bad)begin
  if(feedback_slot)begin
   feedback_data_q<=feedback_data;feedback_owner_q<=feedback_owner;
   if(feedback_start)begin
    feedback_double_q<=raw_selected_double;feedback_feed_q<=latched_feed[raw_feedback_context];
    feedback_base_q<=chain_base[raw_feedback_context];feedback_index_q<=launched[raw_feedback_context];
    feedback_command_generation_q<=chain_generation[raw_feedback_context];
   end
  end
  if(auto_correction)begin
   auto_c0_q<=next_c0;auto_c1_q<=next_c1;auto_context_q<=boundary_context;
   auto_epoch_q<=next_epoch;auto_generation_q<=next_generation;
  end
 end
'''


def warm(text):
    original=text;ops=[]
    text=edit(text,OLD_CONTROLS,NEW_CONTROLS,ops)
    replacements=(
        ('assign internal_frame_accept=feedback_slot && feedback_start && child_frame_accept;',
         'assign internal_frame_accept=delayed_feedback_slot && feedback_start_q && child_frame_accept;'),
        ('assign internal_correction_accept=auto_correction && child_correction_accept;',
         'assign internal_correction_accept=delayed_auto_correction && child_correction_accept;'),
        ('.correction_context(auto_correction ? boundary_context : correction_context)',
         '.correction_context(delayed_auto_correction ? auto_context_q : correction_context)'),
        ('.double_in(feedback_slot ? selected_double : double_in)',
         '.double_in(delayed_feedback_slot ? selected_double : double_in)'),
        ('.generation_in(feedback_slot ? feedback_owner[7:0] : generation_in)',
         '.generation_in(delayed_feedback_slot ? feedback_owner_q[7:0] : generation_in)'),
        ('.base_in(feedback_slot ? chain_base[feedback_context] : base_in)',
         '.base_in(delayed_feedback_slot ? feedback_base_q : base_in)'),
        ('.epoch_in(feedback_slot ? feedback_owner[23:8] : epoch_in)',
         '.epoch_in(delayed_feedback_slot ? feedback_owner_q[23:8] : epoch_in)'),
        ('.correction_epoch(auto_correction ? next_epoch : correction_epoch)',
         '.correction_epoch(delayed_auto_correction ? auto_epoch_q : correction_epoch)'),
        ('.correction_generation(auto_correction ? next_generation : correction_generation)',
         '.correction_generation(delayed_auto_correction ? auto_generation_q : correction_generation)'),
        ('.correction_valid((cold_correction || auto_correction) && !local_error)',
         '.correction_valid((cold_correction || delayed_auto_correction) && !local_error)'),
        ('.data_in(feedback_slot ? feedback_data : data_in),.c0_in(auto_correction ? next_c0 : c0_in),.c1_in(auto_correction ? next_c1 : c1_in)',
         '.data_in(delayed_feedback_slot ? feedback_data_q : data_in),.c0_in(delayed_auto_correction ? auto_c0_q : c0_in),.c1_in(delayed_auto_correction ? auto_c1_q : c1_in)'))
    for old,new in replacements:text=edit(text,old,new,ops)
    need(reverse(text,ops)==original,'WARM_REVERSE')
    return text,ops


def field(text):
    original=text;ops=[]
    text=edit(text,' always_comb begin\n  admission_bad=',C0_FUNCTION+' always_comb begin\n  admission_bad=',ops)
    text=edit(text,"!correction_ok(c0_in[lane*32+:32],protocol_correction_base-32'd1)",
        '!correction_c0_ok(c0_in[lane*32+:32],protocol_correction_base)',ops)
    need(reverse(text,ops)==original,'C0_FIELD_REVERSE')
    return text,ops


def prepare(n=256,*,p=16,contexts=2,enabled=0,lean_production=1,
            feedback_ingress_reg=0,auto_correction_ingress_reg=0,c0_admission_direct=0):
    flags=dict(zip(FLAGS,(feedback_ingress_reg,auto_correction_ingress_reg,c0_admission_direct)))
    need(n in (256,65536) and p==16 and contexts==2,'CLOSED_GEOMETRY')
    for value in (enabled,lean_production,*flags.values()):need(type(value) is int and value in (0,1),'BOOLEAN_FLAGS')
    need(sha((ROOT/parent_api.SELF).read_bytes())==PARENT_PIN,'FROZEN_PARENT')
    parent=parent_api.prepare(n,p=p,contexts=contexts,enabled=1,lean_production=lean_production,
        crt_transport_reg=1,inverse_ingress_reg=1,term_join_transport_reg=1,
        lean_progress_watchdog=lean_production)
    if not enabled:
        need(not any(flags.values()),'DISABLED_NO_REQUESTED_CHANGES');return copy.deepcopy(parent)
    need((feedback_ingress_reg,auto_correction_ingress_reg)==(1,1), 'PAIRED_COMPLETE_INGRESS_ONLY')
    need(sha((ROOT/MODEL).read_bytes())==MODEL_PIN,'FROZEN_MODEL')
    out=copy.deepcopy(parent);before=copy.deepcopy(parent['geometry'])
    after=model.geometry(before,feedback_ingress_reg=feedback_ingress_reg,
        auto_correction_ingress_reg=auto_correction_ingress_reg,c0_admission_direct=c0_admission_direct)
    plan=model.schedule(after);files=out['files'];records={};renames={}
    for name,text in list(files.items()):
        ops=[];changed=text
        if name.startswith('genefer_stream27_warm_contexts_aw'):changed,ops=warm(text)
        elif name.startswith('genefer_stream27_shared_warm_aw') and c0_admission_direct:changed,ops=field(text)
        if ops:
            files[name]=changed;records[name]=dict(parent=name,edits=ops)
            renames[name[:-3]]=name[:-3]+'_feedback12_v1'
    oldtop=out['top'];newtop=f'genefer_stream27_host_contexts_aw{after["aw"]}_p16_feedback12_v1'+('_lean' if lean_production else '')
    renames[oldtop]=newtop
    # Rebind the arithmetic graph when its field call identifiers change.
    if c0_admission_direct:
        arith=next(name for name in files if name.startswith('genefer_stream27_threefield_carry_aw'))
        renames[arith[:-3]]=arith[:-3]+'_feedback12_v1'
    for name,text in list(files.items()):
        changed=text
        for old,new in renames.items():changed=re.sub(r'\b'+re.escape(old)+r'\b',new,changed)
        newname=renames.get(name[:-3],name[:-3])+'.sv'
        if changed!=text:records.setdefault(name,dict(parent=name,edits=[]))['edits'].append((text,changed))
        if newname!=name:files.pop(name)
        files[newname]=changed
    host=files[newtop+'.sv'];ops=[]
    oldsecond=next(c['accept'] for c in parent['two_context_schedule']['correction'] if c['tag'][0]==1 and c['tag'][3]==0)
    second=next(c['accept'] for c in plan['correction'] if c['tag'][0]==1 and c['tag'][3]==0)
    host=edit(host,f'CONTEXT_OFFSET={before["warm_interval"]//2},SECOND_CORRECTION={oldsecond};',
        f'CONTEXT_OFFSET={after["warm_interval"]//2},SECOND_CORRECTION={second};',ops)
    for key,value in flags.items():host=edit(host,',CONTEXTS=2',f',CONTEXTS=2,{key}={value}',ops)
    files[newtop+'.sv']=host
    # All three new flags live at top for an explicit build contract; the
    # emitted module graph is fixed and disabled prepare is exact R11.
    out['source_dependencies']=list(dict.fromkeys(out['source_dependencies']+[SELF,MODEL]))
    out['source_sha256']={path:sha((ROOT/path).read_bytes()) for path in out['source_dependencies']}
    out.update(top=newtop,geometry=after,two_context_schedule=plan,parameters=dict(out['parameters'],**flags),
        rtl_sources=list(files),generated_sha256={name:sha(text) for name,text in files.items()})
    out['context_feedback12']=dict(source_ready=SOURCE_READY,parent_top=parent['top'],flags=flags,
        lean_production=bool(lean_production),calendar_before=before,calendar_after=after,
        existing_feedback_fifo_rows=before['feedback_fifo_rows'],explicit_feedback_register_rows=1,
        cold_correction_retirement_literal=True,raw_command_collision_fault_origins_retained=True,
        queued_descriptor_rechecked_at_accept=True,full25_data_owner_double_base_tuple=True,
        automatic_correction_full_tuple=True,reset_valid_kill=True,
        host_watchdog_is_not_field_flush=True,publication_fence_edges_per_job=1,copy_edges=n+4,
        source_declared_cold_first_edges=[204,204+after['warm_interval']//2],
        source_declared_solo_first_edge=104,declared_new_register_bits=613+1050,
        declared_bits_not_mapped_cost=True,source_edits=records,host_calendar_edits=ops,
        native_qualified=False,clock_or_area_gain_claim=False)
    return out
