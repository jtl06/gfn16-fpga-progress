"""Shared CORR_SERIAL_BFS=0|2 flag with an exact correction-cache calendar.

Zero preserves the frozen field compiler. Two binds the independently tested
two-butterfly correction component; small geometries receive explicit counted
input delay. No main CT/GS/root/square arithmetic definition is changed.
"""
import hashlib
import importlib.util
import re
from . import stream27_shared_field_v4 as parent
from . import stream27_shared_field_v2 as small

ROOT=parent.ROOT
HERE='results/throughput-20260929/trackS-p16-diet-analysis-v1/corr-serial-v1'
SELF='reference/stream27_shared_field_v5.py'


def need(ok,label):
    if not ok:raise ValueError(label)


def geometry(n=65536,p=16,*,corr_serial_bfs=0):
    need(type(corr_serial_bfs) is int and corr_serial_bfs in (0,2),'S4_CORR_SERIAL_FLAG')
    g=dict(small.geometry(n,p))
    if corr_serial_bfs==0:return g
    delta=35 if p==16 else 15
    latency=g['correction_cache_latency']+delta
    added=max(0,latency+1-g['pointwise_accept'])
    for key in ('forward_accept','pointwise_accept','square_accept','inverse_accept','physical_first','sink_accept','last_sink',
        'crt_accept','crt_output','double_register','carry_accept','first_digit','last_digit','boundary_output','carry_done'):
        if key in g:g[key]+=added
    g['input_delay']=g.get('input_delay',0)+added
    g['correction_cache_latency']=latency
    earliest=g['first_digit']+1
    correction=g['boundary_output']+1
    interval=max(earliest,correction+latency+1-g['pointwise_accept'])
    correction=max(correction,interval)
    g.update(earliest_next_frame=earliest,warm_interval=interval,feedback_delay=interval-earliest,
        feedback_fifo_rows=interval-earliest,next_correction_accept=correction,next_cache_capture=correction+latency,
        cache_margin=interval+g['pointwise_accept']-correction-latency-1,
        initial_latest_correction=g['pointwise_accept']-latency-1,corr_serial_bfs=2,
        correction_pair_interval=60 if p==16 else 34)
    for key in ('term_seed_first','term_seed_last'):
        if key in g:g[key]+=delta
    need(g['cache_margin']>=0 and g['initial_latest_correction']>=0,'S4_CORR_SERIAL_CACHE_CALENDAR')
    return g


def component(p,field):
    path=ROOT/HERE/'compiler.py'
    spec=importlib.util.spec_from_file_location('s4_owned_correction_serial',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    name=f'genefer_stream27_correction_serial_p{p}_f{field}_v1'
    return name,module.wrappers()['rtl/'+name+'.sv']


def prepare(n=65536,p=16,field=0,*,mode='warm',contexts=1,allow_full_constants=False,corr_serial_bfs=0):
    need(type(corr_serial_bfs) is int and corr_serial_bfs in (0,2),'S4_CORR_SERIAL_FLAG')
    b=parent.prepare(n,p,field,mode=mode,contexts=contexts,allow_full_constants=allow_full_constants)
    if corr_serial_bfs==0:return b
    need(mode in ('warm','warm_signed'),'S4_CORR_SERIAL_WARM_ONLY')
    before=b['geometry'];g=geometry(n,p,corr_serial_bfs=2)
    oldtop=b['top'];s=b['files'].pop(oldtop+'.sv');top=oldtop+'_corr_serial2_v5'
    s=s.replace('module '+oldtop+' #','module '+top+' #',1)
    anchor=',CONTEXTS=1) (';need(s.count(anchor)==1,'S4_CORR_SERIAL_BUILD_PARAM')
    s=s.replace(anchor,',CONTEXTS=1,CORR_SERIAL_BFS=2) (')
    matched=re.search(r' (\w+) #\(.GEN_W\(24\)\) correction_transform \(',s)
    need(matched is not None,'S4_CORR_SERIAL_CHILD_ABI')
    old_child=matched.group(1);name,wrapper=component(p,field)
    need(old_child+'.sv' in b['files'],'S4_CORR_SERIAL_OLD_CHILD')
    b['files'].pop(old_child+'.sv');s=s.replace(old_child+' #(.GEN_W(24)) correction_transform',name+' #(.GEN_W(24)) correction_transform')
    b['files'][name+'.sv']=wrapper
    leaf='genefer_stream27_correction_serial_v1.sv'
    b['files'][leaf]=(ROOT/HERE/'rtl'/leaf).read_text()
    width=p*27;delay=g['input_delay']
    if 'wire raw_digit_slot=&digit_valid' not in s:
        a='wire digit_slot=&digit_valid,boundary_out_slot=&boundary_valid;'
        need(s.count(a)==1,'S4_CORR_SERIAL_INPUT_DELAY_ABI')
        s=s.replace(a,'wire raw_digit_slot=&digit_valid,boundary_out_slot=&boundary_valid;\n wire digit_slot;wire [ROW_W+8:0] launch_tag;\n'+f' wire [{width-1}:0] launch_data;')
        s=s.replace('if(digit_slot && digit_tag[lane]!=digit_tag[0])','if(raw_digit_slot && digit_tag[lane]!=digit_tag[0])')
        for lane in range(p):
            s=s.replace(f"assign input_wide[{28*lane}+:28]={{1'b0,digit_data[{27*lane}+:27]}};",
                        f"assign input_wide[{28*lane}+:28]={{1'b0,launch_data[{27*lane}+:27]}};")
        s=s.replace('.frame_start(digit_slot && digit_tag[0][ROW_W])','.frame_start(digit_slot && launch_tag[ROW_W])')
        s=s.replace('.generation_in(digit_tag[0][ROW_W+8:ROW_W+1])','.generation_in(launch_tag[ROW_W+8:ROW_W+1])')
        front_start=None
    elif ' // Explicit ' in s:front_start=s.index(' // Explicit ')
    else:front_start=s.index(' assign digit_slot=raw_digit_slot;')
    root=re.search(r' (?P<name>\w+) term_roots \(',s);need(root is not None,'S4_CORR_SERIAL_ROOT_PORT')
    front_end=root.start()
    if delay:
        shift=f'{{front_valid[{delay-2}:0],raw_digit_slot}}' if delay>1 else 'raw_digit_slot'
        front=f''' // Explicit {delay}-edge input delay: serialized corrections precede first pointwise read.
 logic [{delay-1}:0] front_valid;
 logic [{width-1}:0] front_data[0:{delay-1}];logic [ROW_W+8:0] front_tag[0:{delay-1}];
 assign digit_slot=front_valid[{delay-1}] && !stop;assign launch_data=front_data[{delay-1}];assign launch_tag=front_tag[{delay-1}];
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)front_valid<=0;
  else if(stop)front_valid<=0;
  else begin
   front_valid<={shift};
   if(raw_digit_slot)begin front_data[0]<=digit_data;front_tag[0]<=digit_tag[0];end
   for(int d=1;d<{delay};d=d+1)if(front_valid[d-1])begin front_data[d]<=front_data[d-1];front_tag[d]<=front_tag[d-1];end
  end
 end
'''
    else:front=' assign digit_slot=raw_digit_slot;assign launch_data=digit_data;assign launch_tag=digit_tag[0];\n'
    s=s[:front_start if front_start is not None else front_end]+front+s[front_end:]
    for parameter,key in (('POINTWISE_FIRST','pointwise_accept'),('SINK_FIRST','sink_accept')):
        a=f'.{parameter}({before[key]})';need(s.count(a)==1,'S4_CORR_SERIAL_EPOCH_CALENDAR')
        s=s.replace(a,f'.{parameter}({g[key]})')
    s=s.replace('CONTEXTS!=1)$fatal','CONTEXTS!=1 || CORR_SERIAL_BFS!=2)$fatal')
    b['files'][top+'.sv']=s;b['top']=top;b['geometry']=g
    b['parameters']=dict(b['parameters'],CORR_SERIAL_BFS=2)
    deps=[SELF,HERE+'/compiler.py',HERE+'/model.py',HERE+'/rtl/'+leaf]
    b['source_dependencies']=list(dict.fromkeys(b['source_dependencies']+deps))
    b['source_sha256']={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in b['source_dependencies']}
    b['rtl_sources']=[name for name in b['files'] if name.endswith('.sv')]
    b['generated_sha256']={name:hashlib.sha256(text.encode()).hexdigest() for name,text in b['files'].items()}
    b['scope']='Shared correction serialization flag plus explicitly counted small input padding; source only until native field/whole qualification; no arithmetic profile or physical saving inheritance.'
    return b
