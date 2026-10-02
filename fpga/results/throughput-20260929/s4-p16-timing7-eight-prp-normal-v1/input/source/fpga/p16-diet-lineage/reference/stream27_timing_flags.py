"""Shared r75 timing composition; named flags, real source, counted calendars.

The inverse final-pair input register adds one transform/carry edge. Field
correction ingress adds one cache edge. Small P8 feedback storage is resized
explicitly where the cache constraint changes the interval. All remaining
flags preserve their independently qualified interface/edge contracts.
"""
import copy
import hashlib
import re
from . import stream27_shared_field_flags as field
from . import stream27_fault_fanout_bind as fault
from . import stream27_host_chain_flags as host

ROOT=field.ROOT
SELF='reference/stream27_timing_flags.py'
FINAL='rtl/kernel/genefer_stream27_merged_final_gs_pair_inputreg_v1.sv'
CANONICAL='rtl/kernel/genefer_stream27_canonical_image_localbase_v1.sv'
CARRY='rtl/kernel/genefer_stream27_blockcarry_lane_localbase_v1.sv'
CELL='rtl/kernel/genefer_stream27_blockcarry_small_cell_localbase_v1.sv'


def flag(value,label):
    field.need(type(value) is int and value in (0,1),'S4_TIMING_FLAG:'+label)


def once(s,a,b):
    field.need(s.count(a)==1,'S4_TIMING_SOURCE_ANCHOR:'+a[:80])
    return s.replace(a,b,1)


def close(b,deps):
    b['source_dependencies']=list(dict.fromkeys(b['source_dependencies']+[SELF]+deps))
    b['source_sha256']={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in b['source_dependencies']}
    b['rtl_sources']=[name for name in b['files'] if name.endswith('.sv')]
    b['generated_sha256']={name:hashlib.sha256(text.encode()).hexdigest() for name,text in b['files'].items()}
    return b


def inverse_geometry(before):
    g=dict(before)
    for key in ('gs_output_latency','physical_first','sink_accept','last_sink','crt_accept','crt_output',
                'double_register','carry_accept','first_digit','last_digit','boundary_output','carry_done'):
        if key in g:g[key]+=1
    earliest=g['first_digit']+1;correction=g['boundary_output']+1
    interval=max(earliest,correction+g['correction_cache_latency']+1-g['pointwise_accept'])
    correction=max(correction,interval)
    g.update(earliest_next_frame=earliest,warm_interval=interval,feedback_delay=interval-earliest,
        feedback_fifo_rows=interval-earliest,next_correction_accept=correction,
        next_cache_capture=correction+g['correction_cache_latency'],
        cache_margin=interval+g['pointwise_accept']-correction-g['correction_cache_latency']-1,
        final_gs_inputreg=1)
    field.need(g['cache_margin']>=0,'S4_FINAL_INPUTREG_CACHE_DEADLINE')
    return g


def pad_boundary_frontend(bundle):
    """Count the one cold-input edge needed by zero-margin CORR_SERIAL2.

    This moves the real digit/tag delay, not the correction admission edge.
    Warm intervals are recomputed from the same cache inequality. Full-size
    P16 has margin and returns the original bundle without any padding.
    """
    before=bundle['geometry'];added=max(0,before['correction_cache_latency']+2-before['pointwise_accept'])
    if not added:return bundle
    field.need(bundle['parameters']['P']==16 and bundle['parameters'].get('CORR_SERIAL_BFS')==2
               and added==1 and before['input_delay'] in (7,40),'S4_TIMING_EXPLICIT_SERIAL_FRONTPAD')
    b=copy.deepcopy(bundle);old=before['input_delay'];new=old+1
    top=b['top'];text=b['files'].pop(top+'.sv')
    start=text.index(f' // Explicit {old}-edge input delay: serialized corrections precede first pointwise read.')
    end=re.search(r' \w+ term_roots \(',text[start:]).start()+start
    part=text[start:end]
    changes=[(f'Explicit {old}-edge',f'Explicit {new}-edge',1),
             (f'logic [{old-1}:0] front_valid;',f'logic [{new-1}:0] front_valid;',1),
             (f'[0:{old-1}]',f'[0:{new-1}]',2),
             (f'front_valid[{old-1}]',f'front_valid[{new-1}]',1),
             (f'front_data[{old-1}]',f'front_data[{new-1}]',1),
             (f'front_tag[{old-1}]',f'front_tag[{new-1}]',1),
             (f'front_valid[{old-2}:0]',f'front_valid[{new-2}:0]',1),
             (f'd<{old};',f'd<{new};',1)]
    for a,c,count in changes:
        field.need(part.count(a)==count,'S4_TIMING_FRONTPAD_ANCHOR:'+a)
        part=part.replace(a,c)
    g=dict(before)
    for key in ('forward_accept','pointwise_accept','square_accept','inverse_accept','physical_first',
                'sink_accept','last_sink','crt_accept','crt_output','double_register','carry_accept',
                'first_digit','last_digit','boundary_output','carry_done'):
        if key in g:g[key]+=1
    earliest=g['first_digit']+1;correction=g['boundary_output']+1
    interval=max(earliest,correction+g['correction_cache_latency']+1-g['pointwise_accept'])
    correction=max(correction,interval)
    g.update(input_delay=new,earliest_next_frame=earliest,warm_interval=interval,
        feedback_delay=interval-earliest,feedback_fifo_rows=interval-earliest,
        next_correction_accept=correction,next_cache_capture=correction+g['correction_cache_latency'],
        cache_margin=interval+g['pointwise_accept']-correction-g['correction_cache_latency']-1,
        initial_latest_correction=g['pointwise_accept']-g['correction_cache_latency']-1,
        boundary_frontend_added=1)
    text=text[:start]+part+text[end:]
    for parameter,key in (('POINTWISE_FIRST','pointwise_accept'),('SINK_FIRST','sink_accept')):
        text=once(text,f'.{parameter}({before[key]})',f'.{parameter}({g[key]})')
    newtop=top+'_boundary_frontpad_v1'
    text=once(text,'module '+top+' #','module '+newtop+' #')
    b['files'][newtop+'.sv']=text;b.update(top=newtop,geometry=g)
    return close(b,[])


def bind_inverse(bundle):
    b=copy.deepcopy(bundle);aw=b['parameters']['AW'];p=b['parameters']['P']
    root=b['files'][b['top']+'.sv']
    names=re.findall(r' (genefer_stream28_merged_gs_\w+) inverse_transform \(',root)
    field.need(len(names)==1 and names[0]+'.sv' in b['files'],'S4_FINAL_INPUTREG_FIELD_GS')
    old=names[0];text=b['files'].pop(old+'.sv');stage=aw-1
    start=text.index(f' if(1)begin: stage{stage}\n');end=text.index(' assign data_out[',start)
    part=text[start:end]
    pairs=re.findall(r'\b(genefer_stream27_merged_final_gs_pair_v1(?:_p16_diet_v1)?) #\(',part)
    field.need(len(pairs)==p//2 and len(set(pairs))==1,'S4_FINAL_INPUTREG_ALL_PAIRS')
    pair=pairs[0];field.need(pair+'.sv' in b['files'],'S4_FINAL_INPUTREG_PARENT_CLOSURE')
    wrapper=(ROOT/FINAL).read_text();wrapper_top=FINAL.rsplit('/',1)[1][:-3]
    if pair!='genefer_stream27_merged_final_gs_pair_v1':
        field.need(p==16 and pair=='genefer_stream27_merged_final_gs_pair_v1_p16_diet_v1',
                   'S4_FINAL_INPUTREG_PRIVATE_PARENT')
        private=wrapper_top+'_p16_diet_v1'
        qualified=wrapper
        wrapper=once(wrapper,'module '+wrapper_top+' #','module '+private+' #')
        wrapper=once(wrapper,'genefer_stream27_merged_final_gs_pair_v1 #(',pair+' #(')
        field.need(wrapper.replace('module '+private+' #','module '+wrapper_top+' #',1)
                   .replace(pair+' #(','genefer_stream27_merged_final_gs_pair_v1 #(',1)==qualified,
                   'S4_FINAL_INPUTREG_PRIVATE_IDENTIFIER_PROOF')
        wrapper_top=private
    part=part.replace(pair+' #(',wrapper_top+' #(')
    part=once(part,'logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];',
              'logic [6:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:6];')
    part=part.replace('slot_pipe[5]','slot_pipe[6]').replace('start_pipe[5]','start_pipe[6]').replace('generation_pipe[5]','generation_pipe[6]')
    part=part.replace('slot_pipe[4:0]','slot_pipe[5:0]').replace('start_pipe[4:0]','start_pipe[5:0]')
    part=once(part,'k<6;k=k+1)generation_pipe','k<7;k=k+1)generation_pipe')
    text=text[:start]+part+text[end:];new=old+'_inputreg_v1'
    text=once(text,'module '+old+' #','module '+new+' #');b['files'][new+'.sv']=text
    oldtop=b['top'];top=oldtop+'_final_inputreg_v1';root=b['files'].pop(oldtop+'.sv')
    root=once(root,old+' inverse_transform (',new+' inverse_transform (')
    before=b['geometry'];g=inverse_geometry(before)
    root=once(root,f'.SINK_FIRST({before["sink_accept"]})',f'.SINK_FIRST({g["sink_accept"]})')
    root=once(root,'module '+oldtop+' #','module '+top+' #')
    root=once(root,',CONTEXTS=1',',CONTEXTS=1,FINAL_GS_INPUTREG=1')
    root=once(root,'CONTEXTS!=1','CONTEXTS!=1 || FINAL_GS_INPUTREG!=1')
    b['files'][top+'.sv']=root;b['files'][wrapper_top+'.sv']=wrapper
    b.update(top=top,geometry=g,parameters=dict(b['parameters'],FINAL_GS_INPUTREG=1))
    b['inverse_inputreg_contract']='Final GS only: complete canonical u/v/original root captured, all pair results +1; final-stage slot/start/gen six-index alignment and sink calendar +1. No root scale substitution.'
    b['inverse_inputreg_parent']=dict(parent_module=pair,wrapper_module=wrapper_top,
        parent_sha256=hashlib.sha256(b['files'][pair+'.sv'].encode()).hexdigest(),
        qualified_wrapper_identifier_only=True)
    return close(b,[FINAL])


def bind_field(bundle, *, boundary_inputreg=0,quarantine_replicas=0,final_gs_inputreg=0):
    for value,name in ((boundary_inputreg,'BOUNDARY_INPUTREG'),(quarantine_replicas,'QUARANTINE_REPLICAS'),(final_gs_inputreg,'FINAL_GS_INPUTREG')):flag(value,name)
    if not(boundary_inputreg or quarantine_replicas or final_gs_inputreg):return bundle
    field.need(bundle['parameters']['P'] in (8,16) and bundle['parameters']['CONTEXTS']==1,'S4_TIMING_P8_P16_CONTEXTS1')
    b=copy.deepcopy(bundle)
    if boundary_inputreg:b=field.bind_boundary(pad_boundary_frontend(b),boundary_inputreg=1,allow_recalendar=True)
    if quarantine_replicas:
        if b['parameters']['P']==8:b=fault.bind(b)
        else:
            from . import stream27_fault_fanout_p16_bind as p16_fault
            b=p16_fault.bind(b)
    if final_gs_inputreg:b=bind_inverse(b)
    return close(b,[])


def prepare_field(n=256,p=8,f=0,*,mode='warm',contexts=1,allow_full_constants=False,
                  boundary_inputreg=0,quarantine_replicas=0,final_gs_inputreg=0):
    b=field.prepare(n,p,f,mode=mode,contexts=contexts,allow_full_constants=allow_full_constants)
    return bind_field(b,boundary_inputreg=boundary_inputreg,quarantine_replicas=quarantine_replicas,
                      final_gs_inputreg=final_gs_inputreg)


def replace_field_roots(b, *, quarantine_replicas,final_gs_inputreg):
    before_geometry=copy.deepcopy(b['geometry']);after_geometry=None
    names=[name for name in b['files'] if name.startswith('genefer_stream27_shared_warm_') and name.endswith('.sv')]
    field.need(len(names)==3,'S4_TIMING_WHOLE_THREE_FIELDS')
    for name in names:
        view=copy.deepcopy(b);view['top']=name[:-3];view['geometry']=before_geometry;view['mode']='warm_signed'
        new=bind_field(view,quarantine_replicas=quarantine_replicas,final_gs_inputreg=final_gs_inputreg)
        oldtop=name[:-3];newtop=new['top']
        b['files']=new['files']
        for filename,text in list(b['files'].items()):
            b['files'][filename]=text.replace(oldtop+' #',newtop+' #')
        b['source_dependencies']=new['source_dependencies']
        if after_geometry is not None:field.need(after_geometry==new['geometry'],'S4_TIMING_FIELD_CALENDAR_JOIN')
        after_geometry=new['geometry']
    b['geometry']=after_geometry
    if quarantine_replicas:b['parameters']=dict(b['parameters'],QUARANTINE_REPLICAS=1)
    if final_gs_inputreg:b['parameters']=dict(b['parameters'],FINAL_GS_INPUTREG=1)
    return b


def resize_feedback(b,before,after):
    old=before['feedback_delay'];new=after['feedback_delay']
    if old==new:return b
    # The qualified N32/P8 parent has four stored rows. Serialized-cache
    # successor uses five, explicitly adding one accepted feedback edge.
    field.need(old==4 and new==5,'S4_TIMING_FEEDBACK_4_TO5_ONLY')
    names=[name for name in b['files'] if name.startswith('genefer_stream27_warm_chain_') and name.endswith('.sv')]
    field.need(len(names)==1,'S4_TIMING_WARM_FEEDBACK_ROOT')
    text=b['files'][names[0]]
    text=once(text,'logic [3:0] fifo_valid,fifo_start;logic [P*32-1:0] fifo_data[0:3];',
              'logic [4:0] fifo_valid,fifo_start;logic [P*32-1:0] fifo_data[0:4];')
    text=once(text,'logic [23:0] fifo_owner[0:3];','logic [23:0] fifo_owner[0:4];')
    text=text.replace('fifo_valid[3]','fifo_valid[4]').replace('fifo_start[3]','fifo_start[4]').replace('fifo_data[3]','fifo_data[4]').replace('fifo_owner[3]','fifo_owner[4]')
    text=once(text,'fifo_valid[2:0],feedback_issue','fifo_valid[3:0],feedback_issue')
    text=once(text,'fifo_start[2:0],digit_start','fifo_start[3:0],digit_start')
    text=once(text,'d<4;d=d+1)if(fifo_valid','d<5;d=d+1)if(fifo_valid')
    text=text.replace('Four explicit accepted-edge pipeline rows: carry output k -> field accept k+5.',
                      'Five explicit accepted-edge pipeline rows: carry output k -> field accept k+6.')
    b['files'][names[0]]=text
    return b


def bind(bundle, *, boundary_inputreg=0,descriptor_fifo_ff=0,quarantine_replicas=0,
         final_gs_inputreg=0,canonical_localbase=0,carry_localbase=0):
    roster=dict(BOUNDARY_INPUTREG=boundary_inputreg,DESCRIPTOR_FIFO_FF=descriptor_fifo_ff,
        QUARANTINE_REPLICAS=quarantine_replicas,FINAL_GS_INPUTREG=final_gs_inputreg,
        CANONICAL_LOCALBASE=canonical_localbase,CARRY_LOCALBASE=carry_localbase)
    for name,value in roster.items():flag(value,name)
    if not any(roster.values()):return bundle
    field.need(bundle['parameters']['P'] in (8,16) and bundle['parameters']['CONTEXTS']==1,'S4_TIMING_WHOLE_P8_P16_CONTEXTS1')
    b=copy.deepcopy(bundle);before_geometry=copy.deepcopy(b['geometry']);deps=[]
    if boundary_inputreg:
        # Whole helper's generous-margin default stays immutable. This branch
        # admits explicitly recounted N32/P8 feedback storage as well.
        names=[name for name in b['files'] if name.startswith('genefer_stream27_shared_warm_') and name.endswith('.sv')]
        field.need(len(names)==3,'S4_TIMING_BOUNDARY_THREE_FIELDS')
        for name in names:
            old=name[:-3];view=copy.deepcopy(b);view['top']=old
            view=pad_boundary_frontend(view)
            new,text=field.boundary_root(view['files'].pop(view['top']+'.sv'),view['top'])
            b['files']=view['files'];b['files'][new+'.sv']=text
            for filename,text in list(b['files'].items()):b['files'][filename]=text.replace(old+' #',new+' #')
            padded=view['geometry']
        b['files'][field.BOUNDARY.rsplit('/',1)[1]]=(ROOT/field.BOUNDARY).read_text();deps += [field.SELF,field.BOUNDARY]
        b['geometry']=field.boundary_geometry(padded,allow_recalendar=True)
        b['parameters']=dict(b['parameters'],BOUNDARY_INPUTREG=1)
    if descriptor_fifo_ff:b=host.bind_descriptor(b,descriptor_fifo_ff=1)
    if quarantine_replicas or final_gs_inputreg:b=replace_field_roots(b,quarantine_replicas=quarantine_replicas,final_gs_inputreg=final_gs_inputreg)
    if canonical_localbase:
        old='genefer_stream27_canonical_image_pipe_v1';new=CANONICAL.rsplit('/',1)[1][:-3]
        field.need(old+'.sv' in b['files'],'S4_TIMING_CANONICAL_PIPE_PARENT');b['files'].pop(old+'.sv')
        b['files']={name:text.replace(old+' #',new+' #') for name,text in b['files'].items()}
        b['files'][new+'.sv']=(ROOT/CANONICAL).read_text();deps.append(CANONICAL)
    if carry_localbase:
        old='genefer_stream27_blockcarry_lane_param_v1';new=CARRY.rsplit('/',1)[1][:-3]
        if b['parameters']['P']==16 and old+'.sv' not in b['files']:
            old='genefer_track_a4_blockcarry_lane_v1'
            field.need(old+'.sv' in b['files'],'S4_TIMING_FIXED_P16_CARRY_PARENT')
            for name,text in list(b['files'].items()):
                text,count=re.subn(r'\b'+old+r' #\(\.AW\(AW\)\)',new+' #(.AW(AW),.P(P))',text)
                b['files'][name]=text
            field.need(sum(text.count(new+' #(.AW(AW),.P(P)) carry (') for text in b['files'].values())==1,
                       'S4_TIMING_FIXED_P16_LANE_BINDING')
        field.need(old+'.sv' in b['files'],'S4_TIMING_CARRY_PARENT');b['files'].pop(old+'.sv')
        b['files']={name:text.replace(old+' #',new+' #') for name,text in b['files'].items()}
        for path in (CARRY,CELL):b['files'][path.rsplit('/',1)[1]]=(ROOT/path).read_text()
        deps += [CARRY,CELL]
    b=resize_feedback(b,before_geometry,b['geometry'])
    host_names=[name[:-3] for name in b['files'] if name.startswith('genefer_stream27_host_chain_') and name.endswith('.sv')]
    renames={old:old+'_timing_r75_v1' for old in host_names}
    def rename(text):
        for old,new in renames.items():text=text.replace(old,new)
        return text
    b['files']={rename(name):rename(text) for name,text in b['files'].items()};b['top']=rename(b['top'])
    for name in renames.values():
        text=b['files'][name+'.sv']
        for key,value in roster.items():
            if not value or key in ('DESCRIPTOR_FIFO_FF',):continue
            text=once(text,'#(parameter ',f'#(parameter int {key}=1,parameter ')
            text=text.replace('endmodule',f' // synthesis translate_off\n initial if({key}!=1)$fatal(1,"S4_TIMING_{key}_BUILD_FLAG");\n // synthesis translate_on\nendmodule')
        b['files'][name+'.sv']=text
    b['parameters']=dict(b['parameters'],**{key:value for key,value in roster.items() if value})
    n=1<<b['parameters']['AW'];canonical_stages=b['parameters'].get('CANONICAL_PIPE_STAGES',0)
    b['cycle_contract']=host.parent.cycle_contract(n,b['geometry'],canonical_pipe_stages=canonical_stages)
    b['timing_roster']=roster
    b['scope']='Source-bound r75 timing composition; actual source-specific native/physical gates required, not inherited component clocks or promotion.'
    return close(b,deps)


def prepare(n=65536,p=8,*,paired=False,contexts=1,allow_full_constants=False,canonical_pipe_stages=1,**flags):
    b=host.prepare(n,p,paired=paired,contexts=contexts,allow_full_constants=allow_full_constants,
                   canonical_pipe_stages=canonical_pipe_stages)
    return bind(b,**flags)
