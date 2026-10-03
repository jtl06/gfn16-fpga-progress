"""R11 coherent transport boundaries on immutable R10.

Each transport switch is default OFF. No multiply/recurrence or arithmetic
profile changes; the four-edge term producer remains literal. Added edges
are counted, never presumed free. Optional all-stage BF splitting is not
implemented/enabled by this bounded batch.
"""
import copy
import hashlib
import re
from pathlib import Path

from . import stream27_context_storage_combo_timing10_bind as parent_api
from . import stream27_context_transport11_model as model
from . import stream27_context_lean_watchdog_bind as watchdog

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_context_storage_combo_transport11_bind.py'
MODEL='reference/stream27_context_transport11_model.py'
PARENT_PIN='8404e36c688c040f47433b7aff2b5fbee34e438968f41898fe8fee6818f51491'
WATCHDOG_PIN='90857abb24ed29925e5b3709ba2b274882848ba76a3b3f2d2272034e6c2203c3'
MODEL_PIN='2b047ff32c9e162ae437a37df871b99cf4bdd473a37e12bf7519772a82e963df'
SOURCE_READY=True
FLAGS=('CRT_TRANSPORT_REG','INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG')


def sha(raw):
    return hashlib.sha256(raw if isinstance(raw,bytes) else raw.encode()).hexdigest()


def need(ok,label):
    if not ok:raise ValueError('C2_TRANSPORT11_'+label)


def once(text,before,after):
    need(text.count(before)==1,'UNIQUE_ANCHOR:'+before[:90])
    return text.replace(before,after,1)


def edit(text,before,after,ops):
    text=once(text,before,after);ops.append((before,after));return text


def reverse(text,ops):
    for before,after in reversed(ops):text=once(text,after,before)
    return text


PAIR_DECL=''' // R11: joined data only; the original raw join checks stay at origin.
 logic pair_slot_q,pair_start_q;logic [24:0] pair_generation_q;
 logic [LANES*27-1:0] pair_lhs_q,pair_rhs_q;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin pair_slot_q<=0;pair_start_q<=0;end
  else begin
   pair_slot_q<=addA_slot && term_join_valid && !stop;
   pair_start_q<=addA_start && addA_slot && term_join_valid && !stop;
  end
 end
 always_ff @(posedge clk)if(rst_n && addA_slot && term_join_valid && !stop)begin
  pair_generation_q<=addA_generation;pair_lhs_q<=addA_data;pair_rhs_q<=term_data;
 end
'''
INVERSE_DECL=''' // R11: complete inverse ingress tuple; stop still fences sampling.
 logic inverse_slot_q,inverse_start_q;logic [24:0] inverse_generation_q;
 logic [LANES*28-1:0] inverse_data_q;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin inverse_slot_q<=0;inverse_start_q<=0;end
  else begin
   inverse_slot_q<=square_slot && !stop;
   inverse_start_q<=square_start && square_slot && !stop;
  end
 end
 always_ff @(posedge clk)if(rst_n && square_slot && !stop)begin
  inverse_generation_q<=square_generation;inverse_data_q<=square_wide;
 end
'''
CRT_DECL=''' // R11: full joined CRT ingress; origin join/lease checks are unchanged.
 logic crt_transport_slot,crt_transport_start,crt_transport_double;
 logic [P*27-1:0] crt_transport_data[0:2];
 logic [TAG_W-1:0] crt_transport_tag;
 logic [31:0] crt_transport_base;
 logic [95:0] crt_transport_reciprocal;
 logic [76:0] crt_transport_limit;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin crt_transport_slot<=0;crt_transport_start<=0;end
  else begin
   crt_transport_slot<=joined && !error_barrier;
   crt_transport_start<=joined && join_start && !error_barrier;
  end
 end
 always_ff @(posedge clk)if(rst_n && joined && !error_barrier)begin
  for(int f=0;f<3;f=f+1)crt_transport_data[f]<=field_data[f];
  crt_transport_tag<={field_context[0],field_epoch[0],field_generation[0],field_row[0]};
  crt_transport_double<=bank_double[bank];
  if(join_start)begin
   crt_transport_base<=profile_base[field_context[0]];
   crt_transport_reciprocal<=profile_reciprocal[field_context[0]];
   crt_transport_limit<=profile_limit[field_context[0]];
  end
 end
'''


def field(text,flags,before,after):
    original=text;ops=[]
    if flags['TERM_JOIN_TRANSPORT_REG']:
        anchor=' genefer_stream27_add_param_v1 #(.GEN_W(25),.LANES(LANES),.P('
        starts=[m.start() for m in re.finditer(re.escape(anchor),text)]
        need(len(starts)==2,'EXACT_ADD_A_AND_B')
        pos=starts[1];marker=text[pos:text.index(' add_B (',pos)+len(' add_B (')]
        text=edit(text,marker,PAIR_DECL+marker,ops)
        old='''  .clk,.rst_n,.in_slot_valid(addA_slot && term_join_valid),.frame_start(addA_start),.quarantine(stop),
  .generation_in(addA_generation),.lhs(addA_data),.rhs(term_data),'''
        new='''  .clk,.rst_n,.in_slot_valid(pair_slot_q && !stop),.frame_start(pair_start_q),.quarantine(stop),
  .generation_in(pair_generation_q),.lhs(pair_lhs_q),.rhs(pair_rhs_q),'''
        text=edit(text,old,new,ops)
    if flags['INVERSE_INGRESS_REG']:
        # Before the literal GS call, after inverse_error and replica inputs
        # have been declared. No implicit forward nets are introduced.
        gs=re.search(r' (genefer_stream28_merged_gs_\w+) #\(.GEN_W\(25\)\) inverse_transform \(',text)
        need(gs is not None,'EXACT_INVERSE_CALL')
        text=edit(text,gs.group(0),INVERSE_DECL+gs.group(0),ops)
        text=edit(text,'.in_slot_valid(square_slot),.frame_start(square_start),.quarantine(transform_quarantine[1]),',
                  '.in_slot_valid(inverse_slot_q && !stop),.frame_start(inverse_start_q),.quarantine(transform_quarantine[1]),',ops)
        text=edit(text,'.generation_in(square_generation),.live_generation(',
                  '.generation_in(inverse_generation_q),.live_generation(',ops)
        text=edit(text,'.data_in(square_wide),','.data_in(inverse_data_q),',ops)
    if after['sink_accept']!=before['sink_accept']:
        text=edit(text,f'.SINK_FIRST({before["sink_accept"]})',f'.SINK_FIRST({after["sink_accept"]})',ops)
    need(reverse(text,ops)==original,'FIELD_REVERSE')
    # No changes to producer/coefficient/cache/raw PW authority or checks.
    for anchor in ('if(product_slot',):
        need(text.count(anchor)==original.count(anchor),'FIELD_TERM_AUTHORITY_COUNT')
    return text,ops


def arithmetic(text):
    original=text;ops=[]
    anchor=' wire begin_carry=joined && join_start && !error_barrier;\n'
    # Put new ingress declarations AFTER local_fault declarations and before
    # all consumers, but before the old begin_carry wire is unnecessary: it is
    # moved to the insertion site along with the declaration to avoid implicit
    # nets in tools that do not infer forward widths correctly.
    text=edit(text,anchor,'',ops)
    insert=' assign coefficient_valid=doubled_valid && !error_barrier;'
    text=edit(text,insert,CRT_DECL+
              ' wire raw_begin_carry=joined && join_start && !error_barrier;\n'
              ' wire begin_carry=crt_transport_slot && crt_transport_start && !error_barrier;\n'+insert,ops)
    text=edit(text,'  if(begin_carry && (|lane_busy))carry_bad=1;\n',
              '  // Keep raw origin admission, including the queued BEGIN reservation.\n'
              '  if(raw_begin_carry && ((|lane_busy) || (crt_transport_slot && crt_transport_start)))carry_bad=1;\n'
              '  if(begin_carry && (|lane_busy))carry_bad=1;\n',ops)
    text=edit(text,'.in_valid(joined && !error_barrier),','.in_valid(crt_transport_slot && !error_barrier),',ops)
    for f in range(3):
        text=edit(text,f'field_data[{f}][27*PHYSICAL+:27]',f'crt_transport_data[{f}][27*PHYSICAL+:27]',ops)
    text=edit(text,'.base(profile_base[field_context[0]]),.reciprocal(profile_reciprocal[field_context[0]]),.coefficient_limit(profile_limit[field_context[0]]),',
              '.base(crt_transport_base),.reciprocal(crt_transport_reciprocal),.coefficient_limit(crt_transport_limit),',ops)
    text=edit(text,'if(joined)begin crt_tag[0]<={field_context[0],field_epoch[0],field_generation[0],field_row[0]};crt_double[0]<=bank_double[bank];end',
              'if(crt_transport_slot)begin crt_tag[0]<=crt_transport_tag;crt_double[0]<=crt_transport_double;end',ops)
    text=edit(text,'if(begin_carry)begin carry_epoch<=field_epoch[0];carry_generation<=field_generation[0];carry_context<=field_context[0];end',
              'if(begin_carry)begin carry_epoch<=crt_transport_tag[ROW_W+8+:16];carry_generation<=crt_transport_tag[ROW_W+:8];carry_context<=crt_transport_tag[TAG_W-1];end',ops)
    # The empty replacement was position-sensitive; undo every other edit
    # first, then restore old begin_carry immediately after the bank wire.
    restored=text
    for old,new in reversed(ops[1:]):restored=once(restored,new,old)
    restored=once(restored,' wire [1:0] bank=field_sink_bank[0];\n',
                  ' wire [1:0] bank=field_sink_bank[0];\n'+anchor)
    need(restored==original,'CRT_ARITHMETIC_REVERSE')
    return text,ops


def prepare(n=256,*,p=16,contexts=2,enabled=0,lean_production=0,
            crt_transport_reg=0,inverse_ingress_reg=0,term_join_transport_reg=0,
            lean_progress_watchdog=0):
    need(p==16 and contexts==2 and n in (256,65536),'CLOSED_GEOMETRY')
    flags=dict(CRT_TRANSPORT_REG=crt_transport_reg,INVERSE_INGRESS_REG=inverse_ingress_reg,
               TERM_JOIN_TRANSPORT_REG=term_join_transport_reg)
    for value in (enabled,lean_production,lean_progress_watchdog,*flags.values()):
        need(type(value) is int and value in (0,1),'BOOLEAN_SWITCHES')
    need(sha((ROOT/parent_api.SELF).read_bytes())==PARENT_PIN,'FROZEN_R10_PARENT')
    parent=parent_api.prepare(n,p=p,contexts=contexts,enabled=1,lean_production=lean_production)
    if not enabled:
        need(not any(flags.values()) and not lean_progress_watchdog,'DISABLED_NO_REQUESTED_TRANSPORTS')
        return copy.deepcopy(parent)
    need(any(flags.values()),'SELECT_ONE_TRANSPORT')
    need(sha((ROOT/MODEL).read_bytes())==MODEL_PIN,'FROZEN_CALENDAR_MODEL')
    if lean_progress_watchdog:
        need(lean_production==1 and sha((ROOT/watchdog.SELF).read_bytes())==WATCHDOG_PIN,
             'EXACT_PRIVATE_LEAN_PROGRESS_RECIPE')
        # Only canonical JSON representation differs between a pure emitted
        # graph and its saved capture; verify the complete normalized bundle.
        import json
        normalized=json.loads(json.dumps(parent))
        need(normalized==watchdog.capture(n),'EXACT_CAPTURED_R10_LEAN_NORMALIZATION')
        parent=watchdog.bind(normalized,enabled=1)
    out=copy.deepcopy(parent);before=copy.deepcopy(out['geometry'])
    after=model.geometry(before,crt_transport_reg=crt_transport_reg,
                         inverse_ingress_reg=inverse_ingress_reg,
                         term_join_transport_reg=term_join_transport_reg)
    plan=model.prove_schedule(after)
    files=out['files'];records={};renames={}
    for name in list(files):
        if name.startswith('genefer_stream27_shared_warm_aw'):
            changed,ops=field(files[name],flags,before,after)
            old=name[:-3];new=old+'_transport11_v1'
            original=files[name]
            changed=edit(changed,'module '+old+' #','module '+new+' #',ops)
            need(reverse(changed,ops)==original,'FIELD_AND_NAMESPACE_REVERSE')
            files.pop(name);files[new+'.sv']=changed;renames[old]=new
            records[new+'.sv']=dict(parent=name,edits=ops)
    arith=next(name for name in files if name.startswith('genefer_stream27_threefield_carry_aw'))
    if crt_transport_reg:
        files[arith],ops=arithmetic(files[arith]);records[arith]=dict(parent=arith,edits=ops)
    # Rebind only graph identifiers. Every arithmetic module body other than
    # field ingress and CRT ingress above is byte-literal to the chosen mode.
    for name in list(files):
        if name.startswith(('genefer_stream27_threefield_carry_aw','genefer_stream27_warm_contexts_aw')):
            renames[name[:-3]]=name[:-3]+'_transport11_v1'
    oldtop=out['top'];newtop=f'genefer_stream27_host_contexts_aw{after["aw"]}_p16_transport11_v1'+('_lean' if lean_production else '')
    renames[oldtop]=newtop
    for name,text in list(files.items()):
        changed=text
        for old,new in renames.items():changed=re.sub(r'\b'+re.escape(old)+r'\b',new,changed)
        newname=renames.get(name[:-3],name[:-3])+'.sv'
        if changed!=text:records.setdefault(name,dict(parent=name,edits=[]))['edits'].append((text,changed))
        if newname!=name:files.pop(name)
        files[newname]=changed
    # Header cadence, watchdog contracts and cold peer timing derive from the
    # new proved geometry; the R6 accepted one-shot section is not changed.
    oldsecond=next(c['accept'] for c in parent['two_context_schedule']['correction'] if c['tag'][0]==1 and c['tag'][3]==0)
    second=next(c['accept'] for c in plan['correction'] if c['tag'][0]==1 and c['tag'][3]==0)
    host=files[newtop+'.sv'];ops=[]
    host=edit(host,f'CONTEXT_OFFSET={before["warm_interval"]//2},SECOND_CORRECTION={oldsecond};',
              f'CONTEXT_OFFSET={after["warm_interval"]//2},SECOND_CORRECTION={second};',ops)
    for key,value in flags.items():host=edit(host,',CONTEXTS=2',f',CONTEXTS=2,{key}={value}',ops)
    host=edit(host,',CONTEXTS=2',f',CONTEXTS=2,LEAN_PROGRESS_WATCHDOG={lean_progress_watchdog}',ops)
    files[newtop+'.sv']=host
    deps=[SELF,MODEL]
    if lean_progress_watchdog:deps.append(watchdog.SELF)
    out['source_dependencies']=list(dict.fromkeys(out['source_dependencies']+deps))
    out['source_sha256']={path:sha((ROOT/path).read_bytes()) for path in out['source_dependencies']}
    out.update(top=newtop,geometry=after,two_context_schedule=plan,
        parameters=dict(out['parameters'],LEAN_PROGRESS_WATCHDOG=lean_progress_watchdog,**flags),
        rtl_sources=list(files),generated_sha256={name:sha(text) for name,text in files.items()})
    out['context_transport11']=dict(source_ready=SOURCE_READY,parent_top=parent['top'],flags=flags,
        lean_production=bool(lean_production),calendar_before=before,calendar_after=after,
        ntt_compare_reg=0,ntt_compare_not_implemented=True,term_recurrence_edges=4,
        lean_progress_watchdog=bool(lean_progress_watchdog),
        field_protocol_sink_added_edges=inverse_ingress_reg+term_join_transport_reg,
        crt_ingress_added_edges=crt_transport_reg,full_owner_transport_literal=True,
        raw_join_checks_retirement_and_fault_origin_preserved=True,
        publication_fence_edges_per_job=1,copy_edges=after['n']+4,
        source_declared_cold_first_edges=[204,204+after['warm_interval']//2],
        source_declared_solo_first_edge=104,
        declared_new_register_bits=3*(891*term_join_transport_reg+475*inverse_ingress_reg)+
            crt_transport_reg*(3+3*16*27+25+(after['aw']-4)+205)+64*lean_progress_watchdog,
        declared_bits_not_mapped_savings=True,
        model_only=True,native_qualified=False,clock_or_area_gain_claim=False,
        source_edits=records,host_calendar_edits=ops)
    return out
