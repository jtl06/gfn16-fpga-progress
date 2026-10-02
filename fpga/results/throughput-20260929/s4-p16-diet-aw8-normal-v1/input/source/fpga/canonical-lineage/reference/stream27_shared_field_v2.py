"""Additive shared small-geometry extension for S4-b; P is never reduced.

Large AW8/P16 through AW16 compositions return the exact v1 RTL definitions.
Small frames use min(4,T) initial term seeds, lane-dependent correction table
indices and an explicit cold input delay when correction setup is longer than
the main forward path. The feedback delay is separately counted, never hidden.
"""
import hashlib
from pathlib import Path

from . import stream27_shared_field_v1 as parent
from .stream27_shared_field_source_v1 import source as parent_source
from .stream_ntt_model import FIELDS,bit_reverse
from .merged_stream27_model_v1 import topology
from .stream27_p16c_physical_probe_v1 import compile_probe
from .stream27_field_compile_param_v1 import compile_transform

ROOT=parent.ROOT
PINS={'reference/stream27_shared_field_v1.py':'4e7f7dab9ed263bf63866cbbec74590d9fb6da8d4794b06e0138a7456075d9b3',
      'reference/stream27_shared_field_source_v1.py':'9a447cf96a88236714a68d4bbfb9edef152c063d48dcb5357cfdba31766ae0a4'}


def replace(s,old,new):
    if s.count(old)!=1:raise ValueError('S4_SMALL_SOURCE_ANCHOR:'+old[:70])
    return s.replace(old,new)


def guard():
    if (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('brief PAUSE')
    for path,pin in PINS.items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=pin:raise ValueError('S4_SMALL_PARENT:'+path)


def geometry(n=65536,p=16):
    if p not in (8,16) or n<32 or n<p*2 or n>65536 or n&(n-1):raise ValueError('S4_SHARED_AW5_16_T_GE_2')
    if n>=p*p:
        g=dict(parent.geometry(n,p));g.update(input_delay=0,initial_term_seeds=4)
        return g
    rows=n//p;pw=p.bit_length()-1
    ct=topology(n,p)['first_output_edge'];gs=topology(n,p,inverse=True)['first_output_edge']
    seeds=min(4,rows);cache_latency=6*pw+14+seeds
    input_delay=max(0,cache_latency+1-(ct+5));pointwise=ct+5+input_delay
    physical=pointwise+6+gs;sink=physical+1;carry=sink+17;digit=carry+25
    boundary=carry+rows-1+28;earliest=digit+1;correction=boundary+1
    interval=max(earliest,correction+cache_latency+1-pointwise);correction=max(correction,interval)
    return dict(n=n,p=p,rows=rows,aw=n.bit_length()-1,contexts=1,variant='p16c' if p==16 else 'p8b',
        ct_output_latency=ct,gs_output_latency=gs,input_delay=input_delay,initial_term_seeds=seeds,
        forward_accept=4+input_delay,pointwise_accept=pointwise,square_accept=pointwise+2,
        inverse_accept=pointwise+6,physical_first=physical,sink_accept=sink,last_sink=sink+rows-1,
        crt_accept=sink,crt_output=sink+15,double_register=sink+16,carry_accept=carry,
        first_digit=digit,last_digit=digit+rows-1,boundary_output=boundary,carry_done=boundary+1,
        earliest_next_frame=earliest,warm_interval=interval,feedback_delay=interval-earliest,
        feedback_fifo_rows=interval-earliest,next_correction_accept=correction,
        correction_cache_latency=cache_latency,next_cache_capture=correction+cache_latency,
        cache_margin=interval+pointwise-correction-cache_latency-1,
        initial_latest_correction=pointwise-cache_latency-1,
        minimum_transform_frame_spacing=rows+max(s['shuffle_depth_per_buffer']
            for inverse in (False,True) for s in topology(n,p,inverse=inverse)['stages']),
        term_seed_first=6*pw+11,term_seed_last=6*pw+10+seeds,term_contexts=4,
        full_N_numeric_NTT_performed=False,scope='small geometry source/event proposal; native controller/carry gates pending')


def small_term_roots(n,p,field):
    rows=n//p;rw=rows.bit_length()-1;width=p*27;prime,_=FIELDS[field]
    packed=[sum(parent.term_weight(n,p,field,row,lane)<<(27*lane) for lane in range(p)) for row in range(rows)]
    name=f'genefer_stream27_shared_term_roots_aw{n.bit_length()-1}_p{p}_f{field}_v2'
    lines=[f'module {name} (',
        ' input logic clk,rst_n,seed_slot,seed_start,pw_slot,pw_start,',
        ' input logic [1:0] seed_row,',f' input logic [{rw-1}:0] pw_row,',
        f' output logic [{width-1}:0] seed_R_roots,next_seed_R_roots,',
        ' output logic [26:0] update_R_factor);',
        f' logic [{width-1}:0] roots[0:{rows-1}],prefetched;',
        f" wire [{rw-1}:0] seed_address={rw}'(seed_row+2'd1);",
        f" wire [{rw-1}:0] following_address=pw_row+{rw}'(5);",
        f" assign seed_R_roots=seed_start ? {width}'h{packed[0]:0{(width+3)//4}x} : prefetched;",
        f" assign next_seed_R_roots=pw_start ? {width}'h{packed[4%rows]:0{(width+3)//4}x} : prefetched;",
        # When T<P every legal row+4 update changes coefficient index. This
        # identity factor is unused, and not a replacement for reseeding.
        f" assign update_R_factor=27'd{(1<<32)%prime};",' initial begin']
    lines += [f"  roots[{row}]={width}'h{word:0{(width+3)//4}x};" for row,word in enumerate(packed)]
    lines += [' end',' always_ff @(posedge clk)if(rst_n && (seed_slot || pw_slot))',
        '  prefetched<=roots[seed_slot ? seed_address : following_address];','endmodule\n']
    return name,'\n'.join(lines)


def small_term_context():
    _,s=parent.term_context_source()
    s=s.replace('genefer_stream27_term_context_param_v1','genefer_stream27_term_context_param_v2')
    s=replace(s,'localparam int ROW_W=AW-$clog2(LANES), LANE_W=$clog2(LANES),ROWS=1<<ROW_W,TAG_W=24+ROW_W;',
        'localparam int ROW_W=AW-$clog2(LANES), LANE_W=$clog2(LANES),ROWS=1<<ROW_W,TAG_W=24+ROW_W;\n'
        '    localparam int INDEX_SHIFT=ROW_W>LANE_W ? ROW_W-LANE_W : 0;\n'
        '    localparam int TARGET_W=ROW_W+1<3 ? 3 : ROW_W+1;\n'
        "    localparam logic [2:0] SEEDS=ROWS<4 ? 3'(ROWS) : 3'd4;")
    s=replace(s,"wire [ROW_W:0] wide_target={1'b0,pointwise_row}+(ROW_W+1)'(4);",
        "wire [TARGET_W-1:0] wide_target=TARGET_W'(pointwise_row)+TARGET_W'(4);")
    s=replace(s,"wire update_slot=pointwise_slot && wide_target<(ROW_W+1)'(ROWS);",
        "wire update_slot=pointwise_slot && wide_target<TARGET_W'(ROWS);")
    s=replace(s,'wire reseed=next_row[ROW_W-1-:LANE_W]!=pointwise_row[ROW_W-1-:LANE_W];',
        'wire reseed=(next_row>>INDEX_SHIFT)!=(pointwise_row>>INDEX_SHIFT);')
    s=s.replace('pointwise_row[1:0]',"2'(pointwise_row)").replace('product_row[1:0]',"2'(product_row)")
    s=replace(s,"seed_row!=2'(3'd4-seed_remaining)","seed_row!=2'(SEEDS-seed_remaining)")
    s=replace(s,"product_row==ROW_W'(3)","product_row==ROW_W'(SEEDS-3'd1)")
    s=replace(s,'active_seed_owner<=seed_owner;seed_remaining<=3;',"active_seed_owner<=seed_owner;seed_remaining<=SEEDS-3'd1;")
    s=replace(s,'ROW_W<LANE_W','ROW_W<1')
    return 'genefer_stream27_term_context_param_v2',s


def small_source(n,p,field,g,small,roots,term):
    top,s=parent_source(n,p,field,g,small,roots,term);newtop=top[:-2]+'v2'
    s=replace(s,'module '+top+' #','module '+newtop+' #')
    pw=p.bit_length()-1;rw=(n//p).bit_length()-1;rows=n//p;width=p*27;delay=g['input_delay']
    def original_index(signal):return '{'+','.join(f'{signal}[{rw-pw+i}]' for i in range(pw))+'}'
    def index(signal,lane):
        reverse='{'+','.join(f'{signal}[{i}]' for i in range(rw))+'}'
        fixed=bit_reverse(lane,pw)*rows%p
        return f"({pw}'d{fixed} | {pw}'({reverse}))"
    for lane in range(p):
        for target,owner,signal in [('addA_rhs','protocol_pw_epoch[0]','pw_row'),
            ('term_seed_coeff','seed_owner[8]','seed_target'),('term_next_coeff','protocol_pw_epoch[0]','term_target')]:
            table='A_table' if target=='addA_rhs' else 'B_table'
            s=replace(s,f'{target}[{27*lane}+:27]={table}[{owner}][{original_index(signal)}];',
                f'{target}[{27*lane}+:27]={table}[{owner}][{index(signal,lane)}];')
    s=replace(s,'if(seed_row==3)seed_running<=0;',f"if(seed_row==2'd{g['initial_term_seeds']-1})seed_running<=0;")
    s=replace(s,'wire digit_slot=&digit_valid,boundary_out_slot=&boundary_valid;',
        'wire raw_digit_slot=&digit_valid,boundary_out_slot=&boundary_valid;\n'
        ' wire digit_slot;wire [ROW_W+8:0] launch_tag;\n'+f' wire [{width-1}:0] launch_data;')
    # Per-lane reducer alignment checks still inspect the raw producer row.
    s=s.replace('if(digit_slot && digit_tag[lane]!=digit_tag[0])','if(raw_digit_slot && digit_tag[lane]!=digit_tag[0])')
    for lane in range(p):
        s=replace(s,f"assign input_wide[{28*lane}+:28]={{1'b0,digit_data[{27*lane}+:27]}};",
            f"assign input_wide[{28*lane}+:28]={{1'b0,launch_data[{27*lane}+:27]}};")
    s=replace(s,'.frame_start(digit_tag[0][ROW_W])','.frame_start(launch_tag[ROW_W])')
    s=replace(s,'.generation_in(digit_tag[0][ROW_W+8:ROW_W+1])','.generation_in(launch_tag[ROW_W+8:ROW_W+1])')
    if delay:
        front=f''' // Explicit {delay}-edge small-frame input delay; correction cache is not read on its capture edge.
 logic [{delay-1}:0] front_valid;
 logic [{width-1}:0] front_data[0:{delay-1}];logic [ROW_W+8:0] front_tag[0:{delay-1}];
 assign digit_slot=front_valid[{delay-1}] && !stop;assign launch_data=front_data[{delay-1}];assign launch_tag=front_tag[{delay-1}];
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)front_valid<=0;
  else if(stop)front_valid<=0;
  else begin
   front_valid<={{front_valid[{delay-2}:0],raw_digit_slot}};
   if(raw_digit_slot)begin front_data[0]<=digit_data;front_tag[0]<=digit_tag[0];end
   for(int d=1;d<{delay};d=d+1)if(front_valid[d-1])begin front_data[d]<=front_data[d-1];front_tag[d]<=front_tag[d-1];end
  end
 end
'''
    else:front=' assign digit_slot=raw_digit_slot;assign launch_data=digit_data;assign launch_tag=digit_tag[0];\n'
    s=replace(s,f' {roots} term_roots (',front+f' {roots} term_roots (')
    return newtop,s


def prepare(n=65536,p=16,field=0,*,mode='warm',contexts=1,allow_full_constants=False):
    guard()
    if mode not in ('probe','warm') or contexts!=1:raise ValueError('S4_SHARED_MODE_CONTEXTS1_ONLY')
    if mode=='probe' or n>=p*p:
        b=parent.prepare(n,p,field,mode=mode,contexts=contexts,allow_full_constants=allow_full_constants)
        b['shared_small_geometry_extension']=True
        return b
    g=geometry(n,p);probe=compile_probe(n,p,field,allow_full_constants=allow_full_constants)
    files=dict(probe['files']);files.pop(probe['top']+'.sv');deps=list(probe['source_dependencies'])
    small=compile_transform(p,field,p,emit_numeric_roms=True);old=small['module'];smallname=old+'_shared_registered_v1'
    s=small['source'].replace('module '+old+' #','module '+smallname+' #').replace(
        'wire accept=row_slot && !stop && !local_fault && !cadence_bad;','wire accept=row_slot && !stop && !local_fault;')
    files[smallname+'.sv']=s;files.update(small.get('rom_files',{}));deps+=small['source_dependencies']
    rootsname,roots=small_term_roots(n,p,field);files[rootsname+'.sv']=roots
    termname,term=small_term_context();files[termname+'.sv']=term
    top,s=small_source(n,p,field,g,smallname,rootsname,termname);files[top+'.sv']=s
    deps += ['rtl/kernel/genefer_digit_reduce27_pipe.sv','rtl/kernel/genefer_stream27_signed_boundary_reduce27_pipe.sv',
        'rtl/kernel/genefer_stream27_epoch_protocol_v5.sv','rtl/kernel/genefer_stream27_row_arithmetic_param_v1.sv',
        'rtl/kernel/genefer_stream27_term_context_v2.sv',*PINS,'reference/stream27_shared_field_v2.py',
        'reference/stream27_p16c_physical_probe_v1.py','reference/stream27_field_compile_param_v1.py',
        'reference/merged_stream27_root_compile_v1.py','reference/merged_stream27_model_v1.py',
        'reference/stream_ntt_model.py','reference/stream_ntt_schedule.py','reference/stream27_field_plan.py',
        'reference/stream27_field_compile.py','reference/merged_negacyclic27_model.py']
    deps=list(dict.fromkeys(deps))
    for path in deps:
        if path.endswith('.sv') and Path(path).name not in files:files[Path(path).name]=(ROOT/path).read_text()
    return dict(top=top,files=files,rtl_sources=[name for name in files if name.endswith('.sv')],
        source_dependencies=deps,source_sha256={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in deps},
        generated_sha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in files.items()},
        geometry=g,parameters=dict(AW=n.bit_length()-1,P=p,CONTEXTS=1,FIELD=field),mode=mode,
        frozen_transform_definitions_shared=True,full_N_numeric_NTT_performed=False,native_run_performed=False,RTL_qualified=False)
