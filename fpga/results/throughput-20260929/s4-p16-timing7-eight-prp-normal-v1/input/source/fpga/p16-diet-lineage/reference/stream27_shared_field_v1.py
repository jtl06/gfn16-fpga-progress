"""One additive P8/P16 generator for lean merged probes and warm S4 fields.

Frozen probe generators and their evidence stay unchanged. This successor uses
their exact CT/GS/root emitters for both modes, plus parameterized registered
arithmetic and four-context late-correction glue. It never executes full-N NTT.
"""
import hashlib
from pathlib import Path

from .stream_ntt_model import FIELDS, bit_reverse
from .stream27_p16c_physical_probe_v1 import compile_probe
from .stream27_field_compile_param_v1 import compile_transform
from .stream27_p16_warm_contract_v1 import geometry as p16_geometry
from .merged_stream27_model_v1 import topology

ROOT=Path(__file__).resolve().parents[1]


def geometry(n=65536,p=16):
    if p not in (8,16) or n<p*p or n>65536 or n&(n-1):
        raise ValueError('S4_SHARED_GEOMETRY_T_GE_P')
    if p==16:return p16_geometry(n)
    rows=n//p;ct=topology(n,p)['first_output_edge'];gs=topology(n,p,inverse=True)['first_output_edge']
    pw=ct+5;physical=pw+6+gs;sink=physical+1
    carry=sink+17;digit=carry+25;boundary=carry+rows-1+28
    correction_latency=6*(p.bit_length()-1)+18
    earliest=digit+1;correction=boundary+1
    interval=max(earliest,correction+correction_latency+1-pw)
    correction=max(correction,interval)
    return dict(n=n,p=p,rows=rows,aw=n.bit_length()-1,pointwise_accept=pw,
        physical_first=physical,sink_accept=sink,last_sink=sink+rows-1,
        first_digit=digit,boundary_output=boundary,carry_done=boundary+1,
        earliest_next_frame=earliest,warm_interval=interval,feedback_delay=interval-earliest,
        feedback_fifo_rows=interval-earliest,next_correction_accept=correction,
        correction_cache_latency=correction_latency,next_cache_capture=correction+correction_latency,
        cache_margin=interval+pw-correction-correction_latency-1,
        full_N_numeric_NTT_performed=False)


def term_weight(n,p,field,row,lane):
    aw=n.bit_length()-1;pw=p.bit_length()-1;rw=aw-pw;prime,g=FIELDS[field]
    frequency=bit_reverse(lane,pw)*(n//p)+bit_reverse(row,rw)
    psi=pow(g,(prime-1)//(2*n),prime)
    return pow(psi,2*frequency+1,prime)*(1<<32)%prime


def term_index(n,p,row):
    return bit_reverse(row,n.bit_length()-1-(p.bit_length()-1))%p


def term_roots_source(n,p,field):
    aw=n.bit_length()-1;pw=p.bit_length()-1;rw=aw-pw;rows=n//p;prime,g=FIELDS[field]
    width=p*27;name=f'genefer_stream27_shared_term_roots_aw{aw}_p{p}_f{field}_v1'
    # A segment shorter than four rows reseeds on every update. Its exact
    # seed constants are indexed by the complete row, with no overlapping-bit
    # address concatenation. Larger segments use P*4 bounded seed vectors.
    short=rows//p<4
    representatives=list(range(rows)) if short else [(s*(rows//p)+c) for s in range(p) for c in range(4)]
    packed=[sum(term_weight(n,p,field,r,l)<<(27*l) for l in range(p)) for r in representatives]
    addrw=max(1,(len(packed)-1).bit_length())
    def address(signal):
        return signal if short else '{'+signal+f'[{rw-1}-:{pw}],'+signal+'[1:0]}'
    omega=pow(g,(prime-1)//n,prime);factorwidth=rw-2
    factors=[pow(omega,-(1<<factorwidth)+3*(1<<(factorwidth-1-t)),prime)*(1<<32)%prime for t in range(factorwidth)]
    lines=[f'module {name} (',
        ' input logic clk,rst_n,seed_slot,seed_start,pw_slot,pw_start,',
        ' input logic [1:0] seed_row,',f' input logic [{rw-1}:0] pw_row,',
        f' output logic [{width-1}:0] seed_R_roots,next_seed_R_roots,',
        ' output logic [26:0] update_R_factor);',
        f' (* ramstyle="M20K" *) logic [{width-1}:0] roots[0:{len(packed)-1}];',
        f' logic [{width-1}:0] prefetched;',
        f" wire [{rw-1}:0] seed_target={rw}'(seed_row+2'd1);",
        f" wire [{rw-1}:0] following_target=pw_row+{rw}'d5;",
        f" wire [{rw-1}:0] first_target={rw}'d4;",
        f' wire [{addrw-1}:0] seed_address={addrw}\'({address("seed_target")});',
        f' wire [{addrw-1}:0] update_address={addrw}\'({address("following_target")});',
        f" assign seed_R_roots=seed_start ? {width}'h{packed[0]:0{(width+3)//4}x} : prefetched;",
        # First update is independently exact, and later updates use one-edge
        # registered prefetch. The initial vector is emitted as a constant.
        f" assign next_seed_R_roots=pw_start ? {width}'h{sum(term_weight(n,p,field,4,l)<<(27*l) for l in range(p)):0{(width+3)//4}x} : prefetched;",
        ' initial begin']
    lines += [f"  roots[{i}]={width}'h{word:0{(width+3)//4}x};" for i,word in enumerate(packed)]
    lines += [' end',' always_ff @(posedge clk)if(rst_n && (seed_slot || pw_slot))',
        '  prefetched<=roots[seed_slot ? seed_address : update_address];',
        f' wire [{rw-3}:0] group_index=pw_row[{rw-1}:2];',
        ' integer factor_index;', ' always_comb begin factor_index=0;']
    for t in range(1,len(factors)):
        lines.append(f"  if(group_index[{t-1}:0]=={t}'d{(1<<t)-1})factor_index={t};")
    lines+=['  case(factor_index)']+[f"   {i}:update_R_factor=27'd{value};" for i,value in enumerate(factors)]
    lines += [f"   default:update_R_factor=27'd{factors[0]};",'  endcase',' end','endmodule\n']
    return name,'\n'.join(lines)


def term_context_source():
    """Mechanical generalized successor of the frozen four-context v2 cell."""
    s=(ROOT/'rtl/kernel/genefer_stream27_term_context_v2.sv').read_text()
    s=s.replace('genefer_stream27_term_context_v2','genefer_stream27_term_context_param_v1')
    s=s.replace('parameter int unsigned AW=16,','parameter int unsigned AW=16, LANES=16,')
    s=s.replace('[AW-4:0]','[AW-$clog2(LANES)-1:0]').replace('[215:0]','[LANES*27-1:0]')
    s=s.replace('ROW_W=AW-3,','ROW_W=AW-$clog2(LANES), LANE_W=$clog2(LANES),')
    s=s.replace('[ROW_W-1-:3]','[ROW_W-1-:LANE_W]').replace('{8{update_R_factor}}','{LANES{update_R_factor}}')
    s=s.replace('genefer_stream27_mul8_v4_registered #(.P(P),.Q(Q),.GEN_W(TAG_W))',
        'genefer_stream27_mul_param_v1 #(.LANES(LANES),.P(P),.Q(Q),.GEN_W(TAG_W))')
    s=s.replace('if(AW<8 || AW>16)',
        'if(AW>16 || ROW_W<LANE_W || (LANES!=8 && LANES!=16))')
    return 'genefer_stream27_term_context_param_v1',s


def prepare(n=65536,p=16,field=0,*,mode='warm',contexts=1,allow_full_constants=False):
    if mode not in ('probe','warm') or contexts!=1:
        raise ValueError('S4_SHARED_MODE_CONTEXTS1_ONLY')
    if (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('brief PAUSE')
    probe=compile_probe(n,p,field,allow_full_constants=allow_full_constants)
    files=dict(probe['files']);deps=list(probe['source_dependencies'])
    if mode=='probe':
        top=probe['top'];g=probe['calendar']
    else:
        g=geometry(n,p)
        small=compile_transform(p,field,p,emit_numeric_roms=True)
        smallold=small['module'];smallname=smallold+'_shared_registered_v1'
        s=small['source'].replace('module '+smallold+' #','module '+smallname+' #')
        s=s.replace('wire accept=row_slot && !stop && !local_fault && !cadence_bad;',
            'wire accept=row_slot && !stop && !local_fault;')
        files[smallname+'.sv']=s
        files.update(small.get('rom_files',{}))
        deps += small['source_dependencies']
        rootsname,roots=term_roots_source(n,p,field);files[rootsname+'.sv']=roots
        termname,term=term_context_source();files[termname+'.sv']=term
        top,source=warm_source(n,p,field,g,smallname,rootsname,termname)
        files[top+'.sv']=source
        # The physical probe top is omitted from the warm build, but its exact
        # CT/GS/square definitions are shared, not reauthored variants.
        files.pop(probe['top']+'.sv')
        deps += ['rtl/kernel/genefer_digit_reduce27_pipe.sv',
            'rtl/kernel/genefer_stream27_signed_boundary_reduce27_pipe.sv',
            'rtl/kernel/genefer_stream27_epoch_protocol_v5.sv',
            'rtl/kernel/genefer_stream27_row_arithmetic_param_v1.sv',
            'rtl/kernel/genefer_stream27_term_context_v2.sv']
    deps += ['reference/stream27_shared_field_v1.py','reference/stream27_shared_field_source_v1.py',
        'reference/stream27_p16c_physical_probe_v1.py',
        'reference/stream27_field_compile_param_v1.py','reference/stream27_p16_warm_contract_v1.py',
        'reference/merged_stream27_root_compile_v1.py','reference/merged_stream27_model_v1.py',
        'reference/stream_ntt_model.py','reference/stream_ntt_schedule.py',
        'reference/stream27_field_plan.py','reference/stream27_field_compile.py']
    deps=list(dict.fromkeys(deps))
    for path in deps:
        if path.endswith('.sv') and Path(path).name not in files:
            files[Path(path).name]=(ROOT/path).read_text()
    return dict(top=top,files=files,rtl_sources=[name for name in files if name.endswith('.sv')],
        source_dependencies=deps,source_sha256={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in deps},
        generated_sha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in files.items()},
        geometry=g,parameters=dict(AW=n.bit_length()-1,P=p,CONTEXTS=contexts,FIELD=field),mode=mode,
        frozen_transform_definitions_shared=True,full_N_numeric_NTT_performed=False,
        native_run_performed=False,RTL_qualified=False)


def warm_source(n,p,field,g,small,roots,term):
    # Defined below as an explicit source template; no ancestor string surgery
    # changes the public warm interface or its arithmetic schedule.
    from .stream27_shared_field_source_v1 import source
    return source(n,p,field,g,small,roots,term)
