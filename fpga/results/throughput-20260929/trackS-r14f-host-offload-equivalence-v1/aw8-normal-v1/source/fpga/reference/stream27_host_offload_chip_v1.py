"""Private HOST_OFFLOAD boundary on the exact frozen protected R13 capture.

Default OFF returns every parent byte. ON retains setup validation, all warm
reducers/arithmetic/ownership, and exports fixed-cadence raw final packets.
No shared generator edit, full-N numeric work, or dispatch occurs here.
"""
import copy
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_host_offload_chip_v1.py'
LEAF='rtl/kernel/genefer_stream27_host_offload_ingress_v1.sv'
PARENTS={256:('aw8','151d34a10beed71441b23e7abf3b779d37eaae852a456bda37b6bb37302432d5'),
         65536:('full','229e07390fbed434131bba7e101c2492bde27f5a45ebceb7fa40e1d94fec5c53')}
def sha(raw):return hashlib.sha256(raw.encode() if isinstance(raw,str) else raw).hexdigest()
def need(ok,msg):
    if not ok:raise ValueError('HOST_OFFLOAD_CHIP_'+msg)
def change(text,old,new,ops):
    need(text.count(old)==1,'UNIQUE:'+old[:80]);ops.append((old,new));return text.replace(old,new,1)
def reverse(text,ops):
    for old,new in reversed(ops):
        need(text.count(new)==1,'REVERSE_UNIQUE');text=text.replace(new,old,1)
    return text
def capture(n):
    need(n in PARENTS,'AW8_FULL_ONLY')
    stage,pin=PARENTS[n]
    raw=(ROOT/f'results/throughput-20260929/trackS-c2-protected-relay13-native-v1/{stage}-normal/production-bundle.json').read_bytes()
    need(sha(raw)==pin,'CAPTURED_R13_BUNDLE')
    b=json.loads(raw)
    need(len(b['files'])==58 and all(sha(t)==b['generated_sha256'][name] for name,t in b['files'].items()),'EXACT58')
    return b

TRANSPORT=''' input logic off_cold_slot,off_cold_correction,
 input logic [3*P*32-1:0] off_planes,off_lows,off_highs,
 input logic [95:0] off_expected_reciprocal,off_expected_limit,
 output logic off_profile_good,
'''
PORTS=''' input logic off_begin,off_write,off_commit,off_context,
 input logic [AW+1:0] off_index,input logic [31:0] off_word,
 input logic [31:0] off_base,off_generation,
 input logic [95:0] off_reciprocal,off_limit,input logic [15:0] off_epoch,
 input logic off_raw_ready,off_boundary_ready,
 output logic [1:0] off_loaded,off_done,
 output logic off_error,off_raw_valid,off_raw_context,off_boundary_valid,off_boundary_context,
 output logic [55:0] off_raw_owner,off_boundary_owner,
 output logic [AW-$clog2(P)-1:0] off_raw_row,
 output logic [P*32-1:0] off_raw_data,off_c0,off_c1,
'''

def field(text,prime):
    ops=[]
    def edit(a,b):
        nonlocal text;text=change(text,a,b,ops)
    edit(' input logic [511:0] data_in,c0_in,c1_in,',
         ' input logic off_cold_slot,off_cold_correction,\n input logic [511:0] off_plane,off_low,off_high,\n input logic [511:0] data_in,c0_in,c1_in,')
    # Keep the real shared reducers and their validity/tags/range checks. Cold
    # numeric words use a latency-matched canonical transport instead of their
    # zero placeholder residues. Warm path is literally unchanged.
    insert=''' logic [511:0] off_high_q;
 logic off_high_select;
 logic [3:0] off_digit_select;logic [5:0] off_boundary_select;
 logic [431:0] off_digit_data[0:3],off_boundary_data[0:5];
 wire off_boundary_input=accepted_correction ? off_cold_correction : off_high_select;
 function automatic integer off_reverse(input integer value);
  integer result;
  begin result=0;for(integer k=0;k<4;k++)begin result=(result<<1)|(value&1);value=value>>1;end off_reverse=result;end
 endfunction
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin off_digit_select<=0;off_boundary_select<=0;off_high_select<=0;end
  else begin
   off_digit_select<={off_digit_select[2:0],accepted && off_cold_slot};
   off_boundary_select<={off_boundary_select[4:0],boundary_slot && off_boundary_input};
   if(accepted_correction)off_high_select<=off_cold_correction;
  end
 end
 always_ff @(posedge clk)begin
  if(rst_n && accepted_correction)off_high_q<=off_high;
  if(rst_n && accepted && off_cold_slot)
   for(int lane=0;lane<LANES;lane++)off_digit_data[0][lane*27+:27]<=off_plane[lane*32+:27];
  if(rst_n && boundary_slot && off_boundary_input)
   for(int lane=0;lane<LANES;lane++)off_boundary_data[0][lane*27+:27]<=
    accepted_correction ? off_low[off_reverse(lane)*32+:27] : off_high_q[off_reverse(lane)*32+:27];
  for(int d=1;d<4;d++)if(rst_n && off_digit_select[d-1])off_digit_data[d]<=off_digit_data[d-1];
  for(int d=1;d<6;d++)if(rst_n && off_boundary_select[d-1])off_boundary_data[d]<=off_boundary_data[d-1];
 end
'''
    edit(' for(genvar lane=0;lane<LANES;lane=lane+1)begin: reducers',insert+' for(genvar lane=0;lane<LANES;lane=lane+1)begin: reducers')
    edit('assign digit_data[lane*27+:27]=digit_residue[26:0];',
         'assign digit_data[lane*27+:27]=off_digit_select[3] ? off_digit_data[3][lane*27+:27] : digit_residue[26:0];')
    edit('assign boundary_data[lane*27+:27]=boundary_residue[26:0];',
         'assign boundary_data[lane*27+:27]=off_boundary_select[5] ? off_boundary_data[5][lane*27+:27] : boundary_residue[26:0];')
    # Full-word residue guard also protects private transport faults; no trim.
    edit('  if(in_slot_valid)begin',f'''  if(in_slot_valid && off_cold_slot)for(int lane=0;lane<LANES;lane++)
   if(off_plane[lane*32+:32]>=32'd{prime})admission_bad=1;
  if(correction_valid && off_cold_correction)for(int lane=0;lane<LANES;lane++)
   if(off_low[lane*32+:32]>=32'd{prime} || off_high[lane*32+:32]>=32'd{prime})admission_bad=1;
  if(in_slot_valid)begin''')
    return text,ops

def transport(text,kind):
    ops=[]
    def edit(a,b):
        nonlocal text;text=change(text,a,b,ops)
    edit(' input logic [P*32-1:0] data_in,c0_in,c1_in,',TRANSPORT+' input logic [P*32-1:0] data_in,c0_in,c1_in,')
    if kind=='warm':
        edit('  .data_in(delayed_feedback_slot ? feedback_data_q : data_in),',
             '  .off_cold_slot(off_cold_slot && !delayed_feedback_slot),.off_cold_correction(off_cold_correction && !delayed_auto_correction),\n  .off_planes,.off_lows,.off_highs,.off_expected_reciprocal,.off_expected_limit,.off_profile_good,\n  .data_in(delayed_feedback_slot ? feedback_data_q : data_in),')
    else:
        for f in range(3):
            old=f'  .data_in,.c0_in,.c1_in,.out_slot_valid(field_valid[{f}]),'
            edit(old,f'  .off_cold_slot,.off_cold_correction,.off_plane(off_planes[{f}*P*32+:P*32]),\n  .off_low(off_lows[{f}*P*32+:P*32]),.off_high(off_highs[{f}*P*32+:P*32]),\n'+old)
        edit('  if(!rst_n)begin', '  if(!rst_n)begin off_profile_good<=0;')
        edit('   if(unit_setup_done && unit_config_valid && !error_barrier)begin',
             '   if(unit_setup_done && unit_config_valid && !error_barrier)begin\n    off_profile_good<=reciprocal==off_expected_reciprocal && {19\'d0,coefficient_limit}==off_expected_limit;')
    return text,ops

def host(text):
    ops=[]
    def edit(a,b):
        nonlocal text;text=change(text,a,b,ops)
    edit(' input logic clk,rst_n,host_context,load_we,read_en,',PORTS+' input logic clk,rst_n,host_context,load_we,read_en,')
    declarations=''' wire off_ingress_error,off_profile_good;
 logic [1:0] off_boundary_seen;
 logic [55:0] off_active_owner[0:1];
 wire [63:0] off_saved_base;wire [15:0] off_saved_generation;wire [31:0] off_saved_epoch;
 wire [191:0] off_saved_reciprocal,off_saved_limit;
 wire [3*P*32-1:0] off_row_data,off_lows,off_highs;
 logic [3*P*32-1:0] off_source_planes;
 wire off_transfer_bad=(final_valid && !off_raw_ready) || (final_boundary_valid && !off_boundary_ready);
 assign off_error=error || off_ingress_error;
 assign off_raw_valid=capture_fire && off_raw_ready;
 assign off_raw_context=final_context;assign off_raw_owner=final_owner;
 assign off_raw_row=digit_row;assign off_raw_data=digit_data;
 assign off_boundary_valid=final_boundary_valid && !safety_error && off_boundary_ready &&
  {boundary_sequence,16'(boundary_epoch-16'd1),boundary_generation}==live_owner[boundary_context*56+:56];
 assign off_boundary_context=boundary_context;
 assign off_boundary_owner={boundary_sequence,16'(boundary_epoch-16'd1),boundary_generation};
 assign off_c0=next_c0;assign off_c1=next_c1;assign off_done=done;
'''
    edit(' wire child_error_barrier,safety_error;',declarations+' wire child_error_barrier,safety_error;')
    edit('assign error=local_error || child_error || canon_error;',
         'assign error=local_error || child_error || canon_error || off_ingress_error;')
    edit('assign safety_error=local_error || child_error_barrier || canon_error;',
         'assign safety_error=local_error || child_error_barrier || canon_error || off_ingress_error;')
    edit('wire capture_fire=final_valid && !capture_bad && !safety_error;',
         'wire capture_fire=final_valid && off_raw_ready && !capture_bad && !safety_error;')
    begin=text.index(' genefer_stream27_host_image_rowwrite_v1 #(')
    end=text.index(' logic canonical_config_valid;',begin)
    old=text[begin:end]
    leaf=''' genefer_stream27_host_offload_ingress_v1 #(.AW(AW),.P(P)) off_ingress (
  .clk,.rst_n,.quarantine(local_error || child_error_barrier),.begin_packet(off_begin),
  .write_valid(off_write),.commit_packet(off_commit),.context_in(off_context),.context_busy(busy),
  .word_index(off_index),.word_data(off_word),.profile_base(off_base),.profile_generation(off_generation),
  .profile_reciprocal(off_reciprocal),.profile_limit(off_limit),.profile_epoch(off_epoch),
  .loaded(off_loaded),.error(off_ingress_error),.saved_base(off_saved_base),
  .saved_generation(off_saved_generation),.saved_epoch(off_saved_epoch),
  .saved_reciprocal(off_saved_reciprocal),.saved_limit(off_saved_limit),
  .row_request(shadow_row_request),.row_context(shadow_row_context),.row_address(shadow_row_address),
  .row_owner(live_owner[shadow_row_context*56+:56]),.expected_owners({off_active_owner[1],off_active_owner[0]}),
  .row_valid(shadow_row_valid),.row_response_context(shadow_response_context),.row_response_owner(shadow_response_owner),.row_data(off_row_data),
  .correction_context(cold_correction_context),.correction_low(off_lows),.correction_high(off_highs));
 assign shadow_row_data='0;assign shadow_capture_ack=1'b0;
 assign shadow_commit_ack=1'b0;assign shadow_rejected=1'b0;
 assign shadow_scalar_valid=1'b0;assign shadow_scalar_context=1'b0;
 assign shadow_scalar_data='0;assign shadow_scalar_owner='0;
 always_ff @(posedge clk)if(rst_n && shadow_row_valid && row_kind_d && !response_bad && !safety_error)
  off_source_planes<=off_row_data;
'''
    edit(old,leaf)
    edit('    (capture_req_d && !shadow_capture_ack) || (|child_cancelled))local_error<=1;',
         '    (|child_cancelled))local_error<=1;')
    begin=text.index(' genefer_stream27_canonical_image_foldpayload100_v1 #(')
    end=text.index(' genefer_stream27_warm_contexts_',begin)
    edit(text[begin:end],''' // Final canonicalization and copy-to-shadow are off chip in this branch.
 assign canon_busy=0;assign canon_done=0;assign canon_error=0;assign canon_image_valid=0;
 assign canon_read_valid=0;assign canon_error_code=0;assign canon_cycles=0;assign canon_data=0;assign canon_address=0;
''')
    edit('  .data_in(source_data),.c0_in(cold_c0[cold_correction_context]),.c1_in(cold_c1[cold_correction_context]),',
         '''  .off_cold_slot(1'b1),.off_cold_correction(1'b1),.off_planes(off_source_planes),.off_lows,.off_highs,
  .off_expected_reciprocal(off_saved_reciprocal[selected_setup_context*96+:96]),
  .off_expected_limit(off_saved_limit[selected_setup_context*96+:96]),.off_profile_good,
  .data_in(source_data),.c0_in(cold_c0[cold_correction_context]),.c1_in(cold_c1[cold_correction_context]),''')
    edit('   local_error<=0;jobs<=0;', '   off_active_owner[0]<=0;off_active_owner[1]<=0;off_boundary_seen<=0;local_error<=0;jobs<=0;')
    edit('   done_q<=0;source_valid<=', '   if(off_transfer_bad || load_we || read_en)local_error<=1;\n   done_q<=0;source_valid<=')
    edit('     cold_c0[c]<=initial_c0[c*P*32+:P*32];cold_c1[c]<=initial_c1[c*P*32+:P*32];',
         '''     cold_c0[c]<='0;cold_c1[c]<='0;off_boundary_seen[c]<=0;
     off_active_owner[c]<={batch_mode[c] ? warm_count[c*32+:32]-32'd1 : 32'd0,
      16'(next_epoch[c]+(batch_mode[c] ? 16'(warm_count[c*32+:32]-32'd1) : 16'd0)),job_generation[c]+8'd1};
     if(!off_loaded[c] || off_saved_base[c*32+:32]!=base[c*32+:32] ||
        off_saved_generation[c*8+:8]!=job_generation[c]+8'd1 || off_saved_epoch[c*16+:16]!=next_epoch[c])local_error<=1;''')
    edit('if(!setup_inflight || setup_done_context!=setup_context || !config_valid[setup_context])local_error<=1;',
         'if(!setup_inflight || setup_done_context!=setup_context || !config_valid[setup_context] || !off_profile_good)local_error<=1;')
    edit('   if(final_boundary_valid)begin','   if(final_boundary_valid)begin\n    if(!off_boundary_ready || off_boundary_seen[boundary_context])local_error<=1;\n    else off_boundary_seen[boundary_context]<=1;')
    edit('    else phase[c]<=RAW_READY;','    else if(!off_boundary_seen[c])local_error<=1;\n    else phase[c]<=RAW_READY;')
    start=text.index('   if(!canonical_owned && (phase[0]==RAW_READY')
    finish=text.index('   if(canonical_owned && phase[canonical_owner]==CANON_LOAD',start)
    edit(text[start:finish],'''   // One final packet fence; no canonical image is published in B mode.
   for(int c=0;c<2;c++)if(phase[c]==RAW_READY && !safety_error)begin
    if(raw_rows[c]!=(ROW_W+1)'(ROWS) || !off_boundary_seen[c])local_error<=1;
    else begin done_q[c]<=1;phase[c]<=IDLE;
     next_epoch[c]<=job_epoch[c]+16'(job_count[c]);end
   end
''')
    # OFF legacy assertion refers to canonical publication, intentionally
    # replaced by raw complete-packet fence above, not silently waived.
    edit('if((|done) && (!(&((~done)|canonical_ready))))$fatal(1,"S4_CONTEXT_DONE_PUBLICATION");',
         'if((|done) && (|canonical_ready))$fatal(1,"HOST_OFFLOAD_NO_CANONICAL_PUBLICATION");')
    return text,ops

def prepare(n=256,*,host_offload=0):
    need(type(host_offload) is int and host_offload in (0,1),'BOOLEAN_FLAG')
    b=capture(n)
    if not host_offload:return b
    out=copy.deepcopy(b);files=out['files'];records={};renames={}
    for name,original in list(files.items()):
        if name==b['top']+'.sv':changed,ops=host(original)
        elif name.startswith('genefer_stream27_shared_warm_aw'):
            f=int(re.search(r'_f([0-2])_',name).group(1));changed,ops=field(original,(104857601,69206017,67239937)[f])
        elif name.startswith('genefer_stream27_warm_contexts_aw'):changed,ops=transport(original,'warm')
        elif name.startswith('genefer_stream27_threefield_carry_aw'):changed,ops=transport(original,'arithmetic')
        else:continue
        need(reverse(changed,ops)==original,'ALL_FUNCTIONAL_BYTES_REVERSE')
        records[name]=dict(edits=ops,changed=changed);renames[name[:-3]]=name[:-3]+'_host_offload_v1'
    for name,record in records.items():
        text=record.pop('changed')
        for old,new in renames.items():text=re.sub(r'\b'+re.escape(old)+r'\b',new,text)
        newname=renames[name[:-3]]+'.sv';files.pop(name);files[newname]=text
        record['new_file']=newname
    files[Path(LEAF).name]=(ROOT/LEAF).read_text()
    # Public flag also defaults OFF in RTL. Preserve the original modules so
    # the OFF generate branch instantiates the literal protected parent.
    files.update({name:text for name,text in b['files'].items() if name not in files})
    private_top=renames[b['top']]
    top=b['top']+'_r14_v1'
    parent_text=b['files'][b['top']+'.sv']
    start=parent_text.index('module '+b['top']+' #(')
    header=parent_text[start:parent_text.index(');',start)+2]
    params=re.findall(r'\b([A-Z][A-Z0-9_]*)=\d+',header)
    need(len(params)==len(set(params)),'WRAPPER_PARAMETERS')
    header=header.replace('module '+b['top']+' #(', 'module '+top+' #(',1)
    header=header.replace('parameter int AW=', 'parameter int HOST_OFFLOAD=0,AW=',1)
    header=header.replace(' input logic clk,rst_n,host_context,load_we,read_en,',PORTS+' input logic clk,rst_n,host_context,load_we,read_en,',1)
    connections=','.join('.'+p+'('+p+')' for p in params)
    wrapper=header+'\n generate if(HOST_OFFLOAD==0)begin: protected_parent\n'
    wrapper+=f' {b["top"]} #({connections}) candidate (.*);\n'
    for port in ('off_loaded','off_done','off_error','off_raw_valid','off_raw_context','off_boundary_valid','off_boundary_context',
                 'off_raw_owner','off_boundary_owner','off_raw_row','off_raw_data','off_c0','off_c1'):
        wrapper+=f" assign {port}='0;\n"
    wrapper+=f' end else begin: offloaded\n {private_top} #({connections}) candidate (.*);\n end endgenerate\n'
    wrapper+=' // synthesis translate_off\n initial if(HOST_OFFLOAD!=0 && HOST_OFFLOAD!=1)$fatal(1,"HOST_OFFLOAD_FLAG");\n // synthesis translate_on\nendmodule\n'
    files[top+'.sv']=wrapper
    deps=list(dict.fromkeys(b['source_dependencies']+[SELF,LEAF]))
    out.update(top=top,parameters=dict(b['parameters'],HOST_OFFLOAD=1),rtl_sources=list(files),source_dependencies=deps,
        source_sha256={path:sha((ROOT/path).read_bytes()) for path in deps},
        generated_sha256={name:sha(t) for name,t in files.items()})
    out['host_offload']=dict(enabled=True,default_off_exact_captured_parent=True,
        parent_bundle_sha256=PARENTS[n][1],parent_top=b['top'],source_edits=records,
        cold_reducers_retained_for_warm=True,setup_hardware_retained=True,
        cold_numeric_upperbits_checked=True,canonical_output=False,
        raw_output='fixed cadence, ready-low is fault/no publication; host finalizes only complete packet',
        unqualified=True,no_clock_or_area_claim=True)
    return out
