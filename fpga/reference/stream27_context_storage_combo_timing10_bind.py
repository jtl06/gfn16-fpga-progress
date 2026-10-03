"""R10 batch: source-own timing ports and coherent scratch profile selection.

Default OFF is the immutable captured protected R9. Optional lean is a fixed
private recipe applied BEFORE these timing changes, never fault-equivalent.
Only inverse final GS adds an arithmetic edge; R9 publication fence remains.
"""
import copy
import hashlib
import json
import re
from pathlib import Path

from . import stream27_context_timing_bind as c2
from . import stream27_timing_flags as timing
from . import stream27_term_select_bind as selector
from . import stream27_term_select_p16_diet_bind as factored
from . import stream27_canonical_begin_split_bind as split
from . import stream27_context_lean_r9_bind as lean
from . import stream27_context_timing10_model as model

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_context_storage_combo_timing10_bind.py'
MODEL='reference/stream27_context_timing10_model.py'
BASE='results/throughput-20260929/trackS-c2-storage-combo-registerederror-native-v1'
CAPTURES={256:('aw8-normal','810b778524fe709d5303ce0cb57cd4c9e9296a5acc4c72bcd19e143f69b22a46'),
          65536:('full-normal','01220c6efc522973786786eb5c65076d3bf396a9c290aa65464e3086e34d8bc9')}
PINS={'reference/stream27_context_storage_combo_registerederror_bind.py':'3a507134f0a68fa393653ca1f8c7ac6e7fe7288d1f5ad0e7e36dc9657cf2a865',
      c2.SELF:'d2e047d30d6290c46c622c2f69e51cd2c53c0cad36ca5de489696f9c6ef8756a',
      'reference/stream27_canonical_begin_split_bind.py':'2bdf2f8d9d931bfedcd8309967e9c7c7c41d0bf3ec3d671d515cd70a58d90185',
      lean.SELF:'1b16b252bd7dff67fb8d88f51bea60b560331751d48fab90056b0ba794a8c87b',
      timing.CANONICAL:'87264ca12a08cdf4b905ffdcc27d066b25333c0f0283904ac0cf9d36f707d70d',
      timing.CARRY:'cb3fcd665036a1d9028bc2d7e33e96c2e5f57e3e95e16a25460173d32560b236',
      timing.CELL:'2005d97a1b512c365b1b6494d8974d3f869d15ee7ce8713115eab8d713e69c1b',
      timing.FINAL:'a230a237c5650552e773cb06930ca5d90abb7f37209d4aae8973b6f2be059a5d'}
ROSTER=dict(FINAL_GS_INPUTREG=1,CANONICAL_LOCALBASE=1,CARRY_LOCALBASE=1,
            TERM_SELECT_TOKEN=1,CANONICAL_PROFILE_SNAPSHOT=1,CANONICAL_BEGIN_PAYLOAD_SPLIT=1)
SOURCE_READY=True


def need(ok,label):
    if not ok:raise ValueError('C2_TIMING10_'+label)


def sha(raw):return hashlib.sha256(raw if isinstance(raw,bytes) else raw.encode()).hexdigest()


def once(text,before,after):
    need(text.count(before)==1,'UNIQUE_ANCHOR:'+before[:90])
    return text.replace(before,after,1)


def capture(n):
    need(type(n) is int and n in CAPTURES,'AW8_FULL_ONLY')
    stage,pin=CAPTURES[n];raw=(ROOT/BASE/stage/'production-bundle.json').read_bytes()
    need(sha(raw)==pin,'IMMUTABLE_R9_CAPTURE')
    return json.loads(raw)


def edited(text,ops):
    original=text
    for before,after in ops:text=once(text,before,after)
    reverse=text
    for before,after in reversed(ops):reverse=once(reverse,after,before)
    need(reverse==original,'ALL_EDITED_BYTES_REVERSE')
    return text


def canonical(text,old,lean_mode):
    new='genefer_stream27_canonical_image_timing10_v1'
    local=(ROOT/timing.CANONICAL).read_text()
    start=local.index('    // A single accepted begin captures every threshold')
    end=local.index('    always_ff @(posedge clk or negedge rst_n)begin',start)
    snapshot=local[start:end]
    ops=[('module '+old+' #','module '+new+' #'),
         ('    logic stored_digit_bad;',
          '    logic signed [33:0] negative_base,negative_two_base,base_max;\n    logic stored_digit_bad;'),
         ("        base_ext=$signed({2'b00,base_reg});two_base=base_ext<<<1;three_base=two_base+base_ext;\n",
          '        // Thresholds are coherent accepted-BEGIN payload registers.\n'),
         ('else if(value>= -base_ext)','else if(value>=negative_base)'),
         ("remainder==base_ext-34'sd1;",'remainder==base_max;'),
         ('    always_ff @(posedge clk or negedge rst_n)begin',snapshot+'    always_ff @(posedge clk or negedge rst_n)begin'),
         ('                        base_reg<=base;address<=0;pass_index<=0;carry<=0;all_zero<=1;all_max<=1;state<=READ_WORD;',
          '                        address<=0;pass_index<=0;carry<=0;all_zero<=1;all_max<=1;state<=READ_WORD;'),
         ('            if(idle_reject)begin\n',split.CAPTURE+'            if(idle_reject)begin\n')]
    if not lean_mode:ops.append(('else if(value< -two_base','else if(value<negative_two_base'))
    return new,edited(text,ops),ops


def term(files):
    old='genefer_stream27_term_context_param_v1_contexts_v1_storage2_v1_payload_lookahead_v1'
    new=old+'_select_token_v1';newmul='genefer_stream27_mul_select_token_c2_timing10_v1'
    original=files.pop(old+'.sv')
    ops=[('module '+old+' #','module '+new+' #'),
         ('    wire product_slot,product_error,product_pending;',
          '    wire product_slot,product_error,product_pending,data_select_slot;'),
         ('    wire bypass_payload=product_slot && product_owner==payload_owner && product_row==payload_row;',
          '    wire bypass_payload=data_select_slot && product_owner==payload_owner && product_row==payload_row;'),
         (selector.MULT_PARENT+' #(.LANES(LANES),.P(P),.Q(Q),.GEN_W(TAG_W)) products (',
          newmul+' #(.LANES(LANES),.P(P),.Q(Q),.GEN_W(TAG_W)) products ('),
         ('.fault_pending(product_pending),.generation_out(product_tag),.result(product_data));',
          '.fault_pending(product_pending),.generation_out(product_tag),.result(product_data),\n        .data_select_slot(data_select_slot));'),
         ('endmodule\n',
          '    // synthesis translate_off\n    always @(negedge clk)if(rst_n && !stop &&\n        data_select_slot!=product_slot)$fatal(1,"C2_TIMING10_LIVE_SELECTOR_EQUIVALENCE");\n    // synthesis translate_on\nendmodule\n')]
    selected=edited(original,ops)
    leaf=(ROOT/selector.LEAF).read_text()
    leaf=factored.identifier(factored.identifier(leaf,selector.MULT_NEW,newmul),
                            'genefer_montgomery_mul27_sparse_pipe',factored.FACTORED)
    restored=selector.reverse_leaf(factored.identifier(factored.identifier(leaf,newmul,selector.MULT_NEW),
                                     factored.FACTORED,'genefer_montgomery_mul27_sparse_pipe'))
    restored=factored.identifier(restored,'genefer_montgomery_mul27_sparse_pipe',factored.FACTORED)
    arithmetic=files['genefer_stream27_row_arithmetic_param_v1.sv']
    start=arithmetic.index('module '+selector.MULT_PARENT+' #');end=arithmetic.index('endmodule\n',start)+len('endmodule\n')
    need(restored==arithmetic[start:end],'ACTUAL_FACTORED_PRODUCT_REVERSE')
    for anchor in ('    wire bypass=product_slot && product_owner==pointwise_owner && product_row==pointwise_row;',
                   "        if(bypass)consumer_missing=1'b0;",
                   'if(product_slot && bank_owner[prod_bank]==product_owner)',
                   'assign cache_ready=product_slot && product_row==ROW_W\'(3) && !stop'):
        need(anchor in selected and anchor in original,'QUALIFIED_TERM_AUTHORITY_LITERAL:'+anchor)
    files[new+'.sv']=selected;files[newmul+'.sv']=leaf
    return old,new,dict(parent=old+'.sv',edits=ops)


def host_profile(text):
    decl=''' logic canonical_config_valid;logic [31:0] canonical_config_base;
 logic [55:0] canonical_config_owner;
 wire canonical_config_bad=(canonical_load || canonical_begin || canonical_read || publish_pending) &&
  (!canonical_config_valid || canonical_config_owner!=live_owner[canonical_owner*56+:56]);
'''
    # All declarations precede this instantiated port use; the checker is later
    # than the original canonical controls so there are no implicit nets.
    ops=[(' genefer_stream27_canonical_image_timing10_v1 #(.AW(AW),.P(P)) scratch (',
          decl+' genefer_stream27_canonical_image_timing10_v1 #(.AW(AW),.P(P)) scratch ('),
         ('.begin_canonical(canonical_begin),.base(job_base[canonical_owner]),',
          '.begin_canonical(canonical_begin),.base(canonical_config_base),'),
         ('   canonical_owner<=0;canonical_owned<=0;load_row<=0;',
          '   canonical_config_valid<=0;canonical_config_base<=2;canonical_config_owner<=0;\n   canonical_owner<=0;canonical_owned<=0;load_row<=0;'),
         ('    publish_pending<=0;publish_context<=0;publish_owner<=0;\n',
          '    publish_pending<=0;publish_context<=0;publish_owner<=0;canonical_config_valid<=0;\n'),
         ('    canonical_owner<=phase[0]!=RAW_READY;canonical_owned<=1;load_row<=0;load_requested<=0;',
          '    canonical_owner<=phase[0]!=RAW_READY;canonical_owned<=1;load_row<=0;load_requested<=0;\n'
          '    canonical_config_valid<=1;canonical_config_base<=job_base[phase[0]!=RAW_READY];\n'
          '    canonical_config_owner<=live_owner[(phase[0]!=RAW_READY)*56+:56];'),
         ('   capture_req_d<=capture_fire;\n',
          '   capture_req_d<=capture_fire;\n   if(canonical_config_bad)local_error<=1;\n   if(safety_error)canonical_config_valid<=0;\n')]
    return edited(text,ops),ops


def bind(bundle,*,enabled=0,lean_production=0):
    for flag in (enabled,lean_production):need(type(flag) is int and flag in (0,1),'BOOLEAN_SWITCHES')
    out=copy.deepcopy(bundle)
    if not enabled:
        need(not lean_production,'DEFAULT_PROTECTED_NO_LEAN')
        return out
    for path,pin in PINS.items():need(sha((ROOT/path).read_bytes())==pin,'IMMUTABLE_RECIPE:'+path)
    parent=capture(out['geometry']['n']);need(out==parent,'EXACT_CAPTURED_R9_NO_MIXTURE')
    if lean_production:out=lean.bind(out,enabled=1)
    proof=model.prove()
    baseline=copy.deepcopy(out['files']);before=copy.deepcopy(out['geometry']);records={}
    files=out['files'];aw=out['parameters']['AW'];g=timing.inverse_geometry(before)
    g['carry_busy_edges']=g['carry_done']-g['sink_accept']+1
    plan=c2.schedule(g)
    need(g['feedback_delay']==before['feedback_delay'],'FEEDBACK_DEPTH_UNCHANGED')
    oldterm,newterm,record=term(files);records[newterm+'.sv']=record
    names=[name for name in files if name.startswith('genefer_stream27_shared_warm_aw')]
    need(len(names)==3,'THREE_FIELDS')
    renames={oldterm:newterm}
    for name in names:
        old=name[:-3];original=files.pop(name)
        # Trusted GS wrapper helper changes only final8 pairs and coherent
        # full25 slot/start/generation alignment from six to seven edges.
        gs=re.findall(r' (genefer_stream28_merged_gs_\w+) #\(.GEN_W\(25\)\) inverse_transform \(',original)
        need(len(gs)==1,'ACTUAL_FULL25_GS_CALL')
        gs_original=files[gs[0]+'.sv']
        text=c2.inverse(files,original,aw,16)
        newgs=gs[0]+'_c2_inputreg_v1'
        records[newgs+'.sv']=dict(parent=gs[0]+'.sv',edits=[(gs_original,files[newgs+'.sv'])])
        text=once(text,f'.SINK_FIRST({before["sink_accept"]})',f'.SINK_FIRST({g["sink_accept"]})')
        new=old+'_timing10_v1'
        text=once(text,'module '+old+' #','module '+new+' #')
        files[new+'.sv']=text;renames[old]=new
        records[new+'.sv']=dict(parent=name,edits=[(original,text)])
    oldcarry='genefer_stream27_blockcarry_lane_param_v1'
    need(files[oldcarry+'.sv']==(ROOT/'rtl/kernel'/ (oldcarry+'.sv')).read_text(),
         'EXACT_CARRY_PARENT_INTERNAL_AUTHORITY')
    carry_original=files.pop(oldcarry+'.sv');newcarry=Path(timing.CARRY).stem
    for path in (timing.CARRY,timing.CELL):files[Path(path).name]=(ROOT/path).read_text()
    records[newcarry+'.sv']=dict(parent=oldcarry+'.sv',edits=[(carry_original,files[newcarry+'.sv'])])
    renames[oldcarry]=newcarry
    oldcanon='genefer_stream27_canonical_image_lean_r9_v1' if lean_production else 'genefer_stream27_canonical_image_directbound_v1'
    newcanon,text,ops=canonical(files.pop(oldcanon+'.sv'),oldcanon,lean_production)
    files[newcanon+'.sv']=text;renames[oldcanon]=newcanon
    records[newcanon+'.sv']=dict(parent=oldcanon+'.sv',edits=ops)
    oldtop=out['top'];top=f'genefer_stream27_host_contexts_aw{aw}_p16_timing10_v1'+('_lean' if lean_production else '')
    renames[oldtop]=top
    for name,text in list(files.items()):
        changed=text
        for old,new in renames.items():changed=re.sub(r'\b'+re.escape(old)+r'\b',new,changed)
        if changed!=text:
            if name not in records:records[name]=dict(parent=name,edits=[])
            records[name]['edits'].append((text,changed))
        files[name]=changed
    files[top+'.sv']=files.pop(oldtop+'.sv')
    records[top+'.sv']=records.pop(oldtop+'.sv')
    oldsecond=next(c['accept'] for c in out['two_context_schedule']['correction'] if c['tag'][0]==1 and c['tag'][3]==0)
    second=next(c['accept'] for c in plan['correction'] if c['tag'][0]==1 and c['tag'][3]==0)
    host=files[top+'.sv']
    ops=[(f'CONTEXT_OFFSET={before["warm_interval"]//2},SECOND_CORRECTION={oldsecond};',
          f'CONTEXT_OFFSET={g["warm_interval"]//2},SECOND_CORRECTION={second};')]
    for key in ROSTER:ops.append((',CONTEXTS=2',',CONTEXTS=2,'+key+'=1'))
    host=edited(host,ops);records[top+'.sv']['edits']+=ops
    host,ops=host_profile(host);records[top+'.sv']['edits']+=ops;files[top+'.sv']=host
    # Per-file reverse to the exact lean/protected parent before any caller
    # rebinding. New dependency leaf bodies are separately pinned below.
    for name,row in records.items():
        if name not in files:continue
        restored=files[name]
        for before_text,after_text in reversed(row['edits']):restored=once(restored,after_text,before_text)
        need(restored==baseline[row['parent']],'SOURCE_REVERSE:'+name)
    captures=[BASE+'/'+stage+'/production-bundle.json' for stage,_ in CAPTURES.values()]
    deps=[SELF,MODEL]+list(PINS)+captures+[timing.SELF,selector.SELF,selector.LEAF,factored.SELF,
                                         'rtl/kernel/genefer_stream27_blockcarry_lane_param_v1.sv']
    out.update(top=top,geometry=g,two_context_schedule=plan,
               parameters=dict(out['parameters'],**ROSTER))
    out['source_dependencies']=list(dict.fromkeys(out['source_dependencies']+deps))
    out['source_sha256']={path:sha((ROOT/path).read_bytes()) for path in out['source_dependencies']}
    out['rtl_sources']=list(files);out['generated_sha256']={name:sha(text) for name,text in files.items()}
    out['context_timing10']=dict(source_ready=SOURCE_READY,parent_top=parent['top'],
        parent_bundle_sha256=CAPTURES[g['n']][1],already_present=['BOUNDARY_INPUTREG','DESCRIPTOR_FIFO_FF','QUARANTINE_REPLICAS'],
        new_roster=ROSTER,lean_production=bool(lean_production),calendar_before=before,
        final_gs_added_edges=1,term_selector_added_edges=0,publication_fence_edges_per_job=1,
        copy_edges='N+4',all_logical_owners_and_routing_retained=True,
        selector_is_payload_only=True,coherent_profile_owner_snapshot=True,
        model=proof,healthy_calendars={str(count):model.event_calendar(g,count) for count in (2,100,1000,1911814)},
        solo2=model.event_calendar(g,2,solo=True),
        default_off_exact=True,reversal_records=records,native_qualified=False,
        clock_or_area_gain_claim=False,promotion_allowed=False)
    return out


def prepare(n=256,*,p=16,contexts=2,enabled=0,lean_production=0):
    need(p==16 and contexts==2,'P16_C2_ONLY')
    return bind(capture(n),enabled=enabled,lean_production=lean_production)
