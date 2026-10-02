"""Additive timing7 transfer onto the corrected two-context P16 diet.

This is a new source lineage, not a rebase of the admitted C2/compact/storage
snapshots. Descriptor FFs are intrinsic in C2. The other six remedies retain
full25/full27 owners, two setup profiles and four logical leases. Only the
boundary ingress, counted small frontend, and final GS change edge calendars.
No native/area/clock qualification is inherited from the C1 record.
"""
from copy import deepcopy
import hashlib
import re
from pathlib import Path
from . import stream27_host_contexts as host
from . import stream27_shared_field_flags as field
from . import stream27_timing_flags as timing
from . import stream27_fault_fanout_bind as fault
from . import stream27_term_select_bind as selector
from . import stream27_term_select_p16_diet_bind as factored
from . import s4_two_context_model_v1 as ports

ROOT=host.ROOT
SELF='reference/stream27_context_timing_bind.py'
ROSTER=dict(BOUNDARY_INPUTREG=1,DESCRIPTOR_FIFO_FF=1,QUARANTINE_REPLICAS=1,
            FINAL_GS_INPUTREG=1,CANONICAL_LOCALBASE=1,CARRY_LOCALBASE=1,
            TERM_SELECT_TOKEN=1)
need,once=field.need,timing.once


def sha(raw):return hashlib.sha256(raw).hexdigest()


def close(b,deps=()):
    b['source_dependencies']=list(dict.fromkeys(b['source_dependencies']+[SELF]+list(deps)))
    b['source_sha256']={name:sha((ROOT/name).read_bytes()) for name in b['source_dependencies']}
    b['rtl_sources']=[name for name in b['files'] if name.endswith('.sv')]
    b['generated_sha256']={name:sha(text.encode()) for name,text in b['files'].items()}
    return b


def recalendar(g):
    g=dict(g)
    earliest=g['first_digit']+1
    correction=g['boundary_output']+1
    interval=max(earliest,correction+g['correction_cache_latency']+1-g['pointwise_accept'])
    correction=max(correction,interval)
    g.update(earliest_next_frame=earliest,warm_interval=interval,
        feedback_delay=interval-earliest,feedback_fifo_rows=interval-earliest,
        next_correction_accept=correction,next_cache_capture=correction+g['correction_cache_latency'],
        cache_margin=interval+g['pointwise_accept']-correction-g['correction_cache_latency']-1,
        initial_latest_correction=g['pointwise_accept']-g['correction_cache_latency']-1,
        carry_busy_edges=g['carry_done']-g['sink_accept']+1)
    need(g['cache_margin']>=0 and g['initial_latest_correction']>=0,'S4_C2_TIMING_CACHE_CALENDAR')
    return g


def geometry(before):
    """Real ingress/cache/final edges; no alteration of the four-cycle loop."""
    g=dict(before)
    added=max(0,g['correction_cache_latency']+2-g['pointwise_accept'])
    need(added in (0,1),'S4_C2_TIMING_COUNTED_FRONTEND')
    if added:
        need(g['input_delay'] in (7,40),'S4_C2_TIMING_SERIAL_FRONTEND_PARENT')
        for key in ('forward_accept','pointwise_accept','square_accept','inverse_accept',
                    'physical_first','sink_accept','last_sink','crt_accept','crt_output',
                    'double_register','carry_accept','first_digit','last_digit','boundary_output','carry_done'):
            g[key]+=added
        g['input_delay']+=added
    g['correction_cache_latency']+=1
    for key in ('term_seed_first','term_seed_last'):g[key]+=1
    for key in ('gs_output_latency','physical_first','sink_accept','last_sink','crt_accept','crt_output',
                'double_register','carry_accept','first_digit','last_digit','boundary_output','carry_done'):
        g[key]+=1
    g.update(boundary_frontend_added=added,boundary_inputreg=1,final_gs_inputreg=1)
    return recalendar(g)


def schedule(g,counts=(4,4)):
    """Own two-context shared-port proof using the full, possibly odd I."""
    interval=g['warm_interval'];offset=interval//2
    need(len(counts)==2 and all(type(c) is int and 1<=c<=16 for c in counts),'S4_C2_TIMING_COUNTS')
    frames=sorted([ports.Frame(ctx,11+12*ctx,(65534+ordinal)&65535,ordinal,
        ordinal*interval+ctx*offset,(604832956,999999937)[ctx])
        for ctx in range(2) for ordinal in range(counts[ctx])],key=lambda f:f.start)
    for label,key,width in (('INPUT',None,g['rows']),('PW','pointwise_accept',g['rows']),
                            ('SINK','sink_accept',g['rows']),('DIGIT','first_digit',g['rows']),
                            ('CARRY','sink_accept',g['carry_busy_edges'])):
        ports.disjoint([(f.start+(g[key] if key else 0),
            f.start+(g[key] if key else 0)+width-1,f.tag) for f in frames],label)
    correction=ports.correction_calendar(frames,g,pair_interval=g['correction_pair_interval'])
    feedback=ports.feedback_queues(frames,g)
    live={};allocation=[];peak=0
    for f in frames:
        live={bank:old for bank,old in live.items() if old.start+g['last_sink']>=f.start}
        free=[bank for bank in range(4) if bank not in live]
        need(bool(free),'S4_C2_TIMING_PREFREE_LEASE')
        bank=free[0];live[bank]=f
        live={bank:old for bank,old in live.items() if old.start+g['last_sink']>f.start}
        peak=max(peak,len(live));allocation.append(dict(context=f.context,ordinal=f.ordinal,start=f.start,bank=bank))
    return dict(status='PASS_MODEL_ONLY',n=g['n'],p=16,geometry=g,
        per_context_interval=interval,context_offset=offset,launch_gaps=[offset,interval-offset],
        frame_starts=[f.start for f in frames],correction=correction,
        lease_allocation=allocation,lease_peak=peak,feedback_peak_rows=feedback,
        correction_pair_interval=g['correction_pair_interval'],full_N_numeric_performed=False,
        scope='Counted timing C2 ports/cache/full-period recurrence only; excludes native and physical evidence.')


def pad_root(text,before,after):
    old=before['input_delay'];new=after['input_delay']
    if old==new:return text
    start=text.index(f' // Explicit {old}-edge input delay: serialized corrections precede first pointwise read.')
    end=re.search(r' \w+ term_roots \(',text[start:]).start()+start
    part=text[start:end]
    for a,c,count in [(f'Explicit {old}-edge',f'Explicit {new}-edge',1),
            (f'logic [{old-1}:0] front_valid;',f'logic [{new-1}:0] front_valid;',1),
            (f'[0:{old-1}]',f'[0:{new-1}]',2),
            (f'front_valid[{old-1}]',f'front_valid[{new-1}]',1),
            (f'front_data[{old-1}]',f'front_data[{new-1}]',1),
            (f'front_tag[{old-1}]',f'front_tag[{new-1}]',1),
            (f'front_valid[{old-2}:0]',f'front_valid[{new-2}:0]',1),
            (f'd<{old};',f'd<{new};',1)]:
        need(part.count(a)==count,'S4_C2_TIMING_FRONTPAD_ANCHOR:'+a)
        part=part.replace(a,c)
    return text[:start]+part+text[end:]


def inverse(files,root,aw,p):
    names=re.findall(r' (genefer_stream28_merged_gs_\w+) #\(.GEN_W\(25\)\) inverse_transform \(',root)
    need(len(names)==1,'S4_C2_TIMING_GS_FULL25')
    old=names[0];text=files.pop(old+'.sv');stage=aw-1
    start=text.index(f' if(1)begin: stage{stage}\n');end=text.index(' assign data_out[',start)
    part=text[start:end];pair='genefer_stream27_merged_final_gs_pair_v1'
    need(part.count(pair+' #(')==p//2 and pair+'.sv' in files,'S4_C2_TIMING_FINAL_ALL_PAIRS')
    wrapper=(ROOT/timing.FINAL).read_text();newpair=Path(timing.FINAL).stem
    part=part.replace(pair+' #(',newpair+' #(')
    part=once(part,'logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];',
        'logic [6:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:6];')
    part=part.replace('slot_pipe[5]','slot_pipe[6]').replace('start_pipe[5]','start_pipe[6]').replace('generation_pipe[5]','generation_pipe[6]')
    part=part.replace('slot_pipe[4:0]','slot_pipe[5:0]').replace('start_pipe[4:0]','start_pipe[5:0]')
    part=once(part,'k<6;k=k+1)generation_pipe','k<7;k=k+1)generation_pipe')
    new=old+'_c2_inputreg_v1';text=text[:start]+part+text[end:]
    files[new+'.sv']=once(text,'module '+old+' #','module '+new+' #')
    files[newpair+'.sv']=wrapper
    return once(root,old+' #(.GEN_W(25)) inverse_transform (',new+' #(.GEN_W(25)) inverse_transform (')


def term(files,root):
    matches=re.findall(r' (genefer_stream27_term_context_param_v[12]_contexts_v1) #\(',root)
    need(len(matches)==1,'S4_C2_TIMING_TERM_FULL27')
    old=matches[0];original=files.pop(old+'.sv')
    new,selected=selector.select_term(old,original)
    arith=files['genefer_stream27_row_arithmetic_param_v1.sv']
    start=arith.index('module '+selector.MULT_PARENT+' #');end=arith.index('endmodule\n',start)+len('endmodule\n')
    actual=arith[start:end];need(factored.FACTORED+' #(' in actual,'S4_C2_TIMING_TERM_FACTORED')
    leaf=(ROOT/selector.LEAF).read_text();newmul='genefer_stream27_mul_select_token_c2_factored_v1'
    leaf=factored.identifier(factored.identifier(leaf,selector.MULT_NEW,newmul),
        'genefer_montgomery_mul27_sparse_pipe',factored.FACTORED)
    restored=selector.reverse_leaf(factored.identifier(factored.identifier(leaf,newmul,selector.MULT_NEW),
        factored.FACTORED,'genefer_montgomery_mul27_sparse_pipe'))
    restored=factored.identifier(restored,'genefer_montgomery_mul27_sparse_pipe',factored.FACTORED)
    need(restored==actual,'S4_C2_TIMING_TERM_ACTUAL_MUL_REVERSE')
    selected=factored.identifier(selected,selector.MULT_NEW,newmul)
    need(factored.reverse_term(new,selected,selector.MULT_PARENT,newmul)==(old,original),
         'S4_C2_TIMING_TERM_EXACT_REVERSE')
    files[new+'.sv']=selected;files[newmul+'.sv']=leaf
    return once(root,old+' #(',new+' #('),old


def bind_field(bundle,enabled=1):
    timing.flag(enabled,'C2_TIMING7')
    b=deepcopy(bundle)
    if not enabled:return b
    need(b['parameters']['P']==16 and b['parameters']['CONTEXTS']==2 and
         b['parameters'].get('CORR_SERIAL_BFS')==2 and b['parameters'].get('MONT_FACTORED')==1,
         'S4_C2_TIMING_FIELD_DIET')
    need('context_timing' not in b,'S4_C2_TIMING_NOT_ALREADY_BOUND')
    before=b['geometry'];g=geometry(before);old=b['top'];root=b['files'].pop(old+'.sv')
    root=pad_root(root,before,g)
    root=once(root,'genefer_stream27_signed_boundary_reduce27_pipe #(',
        'genefer_stream27_signed_boundary_inputreg_v1 #(')
    root=once(root,'.clk,.rst_n,.in_valid(boundary_slot),','.clk,.rst_n,.quarantine(stop),.in_valid(boundary_slot),')
    need(root.count('.PAYLOAD_W(27)) boundary (')==1,'S4_C2_TIMING_BOUNDARY_OWNER27')
    need(root.count(fault.DECL)==1 and root.count('if('+fault.SETTER+')')==1,
         'S4_C2_TIMING_SAME_ORIGIN_SETTER')
    original=root;root=once(root,fault.DECL,fault.DECL+fault.INSERT)
    for i,name in enumerate(('forward_transform','inverse_transform')):
        root=fault.connect_transform(root,name,'.quarantine(stop)',f'.quarantine(transform_quarantine[{i}])')
    root=once(root,'endmodule\n',fault.ASSERT+'endmodule\n')
    reverse=root.replace(fault.INSERT,'',1).replace(fault.ASSERT,'',1)
    for i,name in enumerate(('forward_transform','inverse_transform')):
        reverse=fault.connect_transform(reverse,name,f'.quarantine(transform_quarantine[{i}])','.quarantine(stop)')
    need(reverse==original,'S4_C2_TIMING_FAULT_REVERSE')
    root=inverse(b['files'],root,b['parameters']['AW'],16)
    root,parent_term=term(b['files'],root)
    for key,param in (('pointwise_accept','POINTWISE_FIRST'),('sink_accept','SINK_FIRST')):
        root=once(root,f'.{param}({before[key]})',f'.{param}({g[key]})')
    f=b['parameters'].get('FIELD')
    if f is None:
        match=re.search(r'_f([012])_',old);need(match is not None,'S4_C2_TIMING_FIELD_INDEX');f=int(match[1])
    top=f'genefer_stream27_shared_warm_aw{b["parameters"]["AW"]}_p16_f{f}_v1_timing_c2_v1'
    root=once(root,'module '+old+' #','module '+top+' #')
    for name in ('BOUNDARY_INPUTREG','QUARANTINE_REPLICAS','FINAL_GS_INPUTREG','TERM_SELECT_TOKEN'):
        root=once(root,',CONTEXTS=2',',CONTEXTS=2,'+name+'=1')
        root=once(root,'CONTEXTS!=2','CONTEXTS!=2 || '+name+'!=1')
    b['files'][top+'.sv']=root
    for path in (field.BOUNDARY,fault.LEAF):b['files'][Path(path).name]=(ROOT/path).read_text()
    b.update(top=top,geometry=g,parameters=dict(b['parameters'],FIELD=f,
        BOUNDARY_INPUTREG=1,QUARANTINE_REPLICAS=1,FINAL_GS_INPUTREG=1,TERM_SELECT_TOKEN=1))
    b['context_timing']=dict(parent_top=old,parent_term=parent_term,roster=ROSTER,
        full_main_owner_bits=25,full_term_owner_bits=27,four_logical_leases=True,
        setter_same_origin_edge=True,recurrence_edges=4,II=1,native_pass_inherited=False,
        physical_gain_claim=False,clock_claim=False)
    return close(b,[field.BOUNDARY,fault.SELF,fault.LEAF,timing.SELF,timing.FINAL,
                    selector.SELF,selector.LEAF,factored.SELF])


def bind(bundle,enabled=0):
    timing.flag(enabled,'C2_TIMING7')
    b=deepcopy(bundle)
    if not enabled:return b
    need(b['parameters']['P']==16 and b['parameters']['CONTEXTS']==2 and
         b['parameters'].get('CORR_SERIAL_BFS')==2 and b['parameters'].get('MONT_FACTORED')==1 and
         b['parameters'].get('COLD_LAUNCH_FENCE')==1 and b['parameters'].get('EXPLICIT_NET_DECLARATIONS')==1,
         'S4_C2_TIMING_EXACT_CORRECTED_DIET')
    need(not any(key in b for key in ('context_timing','context_tagcompact','context_storage2',
                                    'context_stage_pipe','context_storage_banks')),'S4_C2_TIMING_CLEAN_PARENT')
    names=[name for name in b['files'] if name.startswith('genefer_stream27_shared_warm_')]
    need(len(names)==3,'S4_C2_TIMING_THREE_FIELDS')
    before=deepcopy(b['geometry']);contracts=[];parents=set();original_files=deepcopy(b['files'])
    for name in names:
        view=deepcopy(b);view.update(top=name[:-3],geometry=before,mode='warm_signed')
        selected=bind_field(view)
        b['files']=selected['files'];b['source_dependencies']=selected['source_dependencies']
        parent_term=selected['context_timing']['parent_term'];parents.add(parent_term)
        b['files'][parent_term+'.sv']=original_files[parent_term+'.sv']
        for filename,text in list(b['files'].items()):
            b['files'][filename]=text.replace(name[:-3]+' #',selected['top']+' #')
        contracts.append(selected['context_timing'])
    for name in parents:b['files'].pop(name+'.sv')
    g=geometry(before);need(g['feedback_delay']==before['feedback_delay'],'S4_C2_TIMING_FEEDBACK_DEPTH_UNCHANGED')
    plan=schedule(g)
    top=b['top'];text=b['files'][top+'.sv']
    oldplan=b['two_context_schedule']
    oldsecond=next(c['accept'] for c in oldplan['correction'] if c['tag'][0]==1 and c['tag'][3]==0)
    second=next(c['accept'] for c in plan['correction'] if c['tag'][0]==1 and c['tag'][3]==0)
    text=once(text,f'CONTEXT_OFFSET={before["warm_interval"]//2},SECOND_CORRECTION={oldsecond}',
        f'CONTEXT_OFFSET={g["warm_interval"]//2},SECOND_CORRECTION={second}')
    b['files'][top+'.sv']=text
    for old,path in (('genefer_stream27_canonical_image_pipe_v1',timing.CANONICAL),
                     ('genefer_stream27_blockcarry_lane_param_v1',timing.CARRY)):
        need(old+'.sv' in b['files'],'S4_C2_TIMING_LOCALBASE_PARENT:'+old)
        new=Path(path).stem;b['files'].pop(old+'.sv')
        for filename,text in list(b['files'].items()):b['files'][filename]=text.replace(old+' #',new+' #')
        b['files'][new+'.sv']=(ROOT/path).read_text()
    b['files'][Path(timing.CELL).name]=(ROOT/timing.CELL).read_text()
    newtop=f'genefer_stream27_host_contexts_aw{b["parameters"]["AW"]}_p16_timing7_v1'
    text=b['files'].pop(top+'.sv');text=once(text,'module '+top+' #','module '+newtop+' #')
    for key in ROSTER:
        if key=='DESCRIPTOR_FIFO_FF':continue
        text=once(text,',CONTEXTS=2',',CONTEXTS=2,'+key+'=1')
        text=once(text,'CONTEXTS!=2','CONTEXTS!=2 || '+key+'!=1')
    b['files'][newtop+'.sv']=text
    b.update(top=newtop,geometry=g,two_context_schedule=plan,
        parameters=dict(b['parameters'],**{key:value for key,value in ROSTER.items() if key!='DESCRIPTOR_FIFO_FF'}))
    b['context_timing']=dict(parent_top=top,parent_generated_sha256=bundle['generated_sha256'],
        field_contracts=contracts,roster=ROSTER,calendar_before=before,
        frontend_added=g['boundary_frontend_added'],cache_added=1,final_gs_added=1,
        feedback_depth_unchanged=True,setup_profiles_preserved=True,
        descriptor_intrinsic=True,logical_leases=4,native_pass_inherited=False,
        whole_resource_go=False,whole_clock_claim=False)
    b['scope']='New C2 timing7 source/calendar only; own normal/fault/resource/clock gates required.'
    return close(b,[timing.CANONICAL,timing.CARRY,timing.CELL,ports.__name__.replace('fpga.','').replace('.','/')+'.py'])


def prepare(n=256,*,enabled=0,allow_full_constants=False):
    return bind(host.prepare(n,16,contexts=2,allow_full_constants=allow_full_constants,
        ram_closure=1,corr_serial_bfs=2,mont_factored=1,cold_launch_fence=1,
        explicit_net_declarations=1),enabled=enabled)
