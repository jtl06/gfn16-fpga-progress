"""Practical A10 read-only packed lookup; no recurrence arithmetic/context.

Fixed compiled N/field profile. One active packed ROM read at issue E0,
structured XOR lane route and destination register E1, BF consumes E2.
No engine/controller rewrite, dispatch, cycle record or physical inference.
Full-N generation is modular-power ROM constants only, never a numeric NTT.
"""
from pathlib import Path
import hashlib

from fpga.reference import merged_negacyclic27_model as math
from fpga.reference import merged_negacyclic27_issue_model_v1 as physical
from fpga.reference.stream_ntt_schedule import m20k


def need(ok, message):
    if not ok:
        raise ValueError(message)


def layout(n=65536, lanes=64, field=0):
    aw, kw, active, groups = physical.geometry(n, lanes)
    need(field in (0,1,2), 'A10_LOOKUP_FIELD')
    stages=[]
    for stage in range(aw):
        streams=1 << max(0,min(aw,kw)-stage-1)
        shift=max(0,stage+1-kw)
        depth=groups if stage<kw else n>>(stage+1)
        stages.append(dict(stage=stage,streams=streams,width=27*streams,depth=depth,
            issue_address_shift=shift,route='((lane>>stage) XOR (base_bank>>(stage+1)))' if stage<kw else 'broadcast',
            M20K_tiling_proxy=m20k(depth,27*streams) if depth>1 else 0))
    return dict(n=n,lanes=lanes,field=field,aw=aw,kw=kw,active=active,issues=groups,stages=stages,
                profile='merged-negacyclic27-ctgs-ordinary-fixed-ROM-v1',
                transform_roots_M20K_per_field_both_directions_proxy=2*sum(s['M20K_tiling_proxy'] for s in stages),
                runtime_geometry='exact compiled N and field only; reject different size/profile at engine admission',
                recurrence_multiplier_pipes=0,recurrence_feedback_contexts=0,
                root_read_ports='one active ROM per accepted issue; width-dependent legal tiling, no multi-read assumption',
                edge_ledger=dict(data_and_root_read_issue=0,root_route_and_data_destination_register=1,
                                 BF_accept=2,BF_output=7,RAM_write_consume=8),
                extra_transform_stage_boundary_edges_vs_frozen=1,
                engine_setup_cycles='unassigned until engine/controller RTL binds fixed ROM profile',
                physical_inference_or_clock=False)


def table_word(plan,stage,address,stream,*,inverse=False):
    spec=plan['stages'][stage];need(0<=address<spec['depth'] and 0<=stream<spec['streams'],'A10_LOOKUP_ADDRESS')
    group=address*spec['streams']+stream if stage<plan['kw'] else address
    exponent=math.bit_reverse((plan['n']>>(stage+1))+group,plan['aw'])
    f=math.FIELDS[plan['field']];root=pow(math.psi_for(plan['n'],f),-exponent if inverse else exponent,f.p)
    if inverse and stage==plan['aw']-1:
        return root*math.normalization_constant(plan['n'],f)%f.p
    return f.encode(root,1)


def base_bank(plan,stage,number):
    source=0;base=0
    for bit in range(plan['aw']):
        fixed=bit!=stage and not(bit<plan['kw'] and bit!=stage%plan['kw'])
        if fixed:
            base|=((number>>source)&1)<<bit;source+=1
    return physical.bank_of(base,plan['kw'])


def roots_for_request(plan,stage,number,*,inverse=False):
    spec=plan['stages'][stage];need(0<=number<plan['issues'],'A10_LOOKUP_ISSUE')
    address=number>>spec['issue_address_shift']
    words=[table_word(plan,stage,address,stream,inverse=inverse) for stream in range(spec['streams'])]
    bank=base_bank(plan,stage,number)
    result=[]
    for lane in range(plan['lanes']):
        if lane>=plan['active']:result.append(0);continue
        stream=(((lane>>stage)^(bank>>(stage+1)))&(spec['streams']-1)) if stage<plan['kw'] else 0
        result.append(words[stream])
    return result


def compile_lookup(n=32,lanes=64,field=0,*,allow_full_constants=False):
    physical.source_guard()
    need(n<=256 or allow_full_constants,'A10_LOOKUP_FULL_CONSTANTS_EXPLICIT_ONLY')
    plan=layout(n,lanes,field);aw,kw=plan['aw'],plan['kw'];iw=max(1,(plan['issues']-1).bit_length())
    name=f'genefer_a10_packed_root_lookup_aw{aw}_l{lanes}_f{field}_v1'
    width=27*lanes
    out=[f'// SOURCE-ONLY fixed N={n}/field{field}; no numeric NTT/RTL qualification.',
         f'module {name} #(parameter int TAG_W=32) (',
         ' input logic clk,rst_n,request_valid,inverse,',
         ' input logic [4:0] stage,',f' input logic [{iw-1}:0] issue_index,',
         ' input logic [TAG_W-1:0] request_tag,',
         ' output logic request_ready,out_valid,out_error,',
         ' output logic [TAG_W-1:0] out_tag,',f' output logic [{width-1}:0] roots);',
         ' logic valid_q,inverse_q;', ' logic [4:0] stage_q;',f' logic [{kw-1}:0] base_bank_q;',
         ' logic [TAG_W-1:0] tag_q;',f' wire bad=stage>=5\'d{aw} || int\'(issue_index)>={plan["issues"]};',
         ' wire accept=request_valid && request_ready && !bad;',
         ' assign request_ready=rst_n && !out_error;',
         f' function automatic logic [{kw-1}:0] request_base_bank(input logic[4:0] s,input logic[{iw-1}:0] number);',
         f'  logic [{aw-1}:0] a;logic [{kw-1}:0] b;integer src;',
         "  begin a='0;b='0;src=0;",
         f'   for(int j=0;j<{aw};j=j+1)if(j!=int\'(s) && !(j<{kw} && j!=(int\'(s)%{kw})))begin',
         "    a[j]=1'((int'(number)>>src)&1);src=src+1;end",
         f'   for(int j=0;j<{aw};j=j+1)b[j%{kw}]=b[j%{kw}]^a[j];',
         '   request_base_bank=b;end', ' endfunction',
         f' wire [{width-1}:0] selected_stage_roots[0:{aw-1}];']
    table_hashes={}
    for spec in plan['stages']:
        s,streams,w,depth=spec['stage'],spec['streams'],spec['width'],spec['depth'];digits=(w+3)//4
        for inverse in (False,True):
            direction='gs' if inverse else 'ct';stem=f'{direction}_s{s}'
            words=tuple(sum(table_word(plan,s,row,k,inverse=inverse)<<(27*k) for k in range(streams)) for row in range(depth))
            text=''.join(f'{word:0{digits}x}\n' for word in words)
            table_hashes[stem]=hashlib.sha256(text.encode()).hexdigest()
            out.append(f' logic [{w-1}:0] {stem}_q;')
            if depth==1:
                out.append(f" assign {stem}_q={w}'h{words[0]:0{digits}x};")
            else:
                out+=[f' (* ramstyle="M20K" *) logic [{w-1}:0] {stem}_rom[0:{depth-1}];', ' initial begin']
                out += [f"  {stem}_rom[{row}]={w}'h{word:0{digits}x};" for row,word in enumerate(words)]
                out+=[' end',' always_ff @(posedge clk)',
                      f"  if(rst_n && accept && stage==5'd{s} && inverse==1'b{int(inverse)})",
                      f"   {stem}_q<={stem}_rom[int'(issue_index)>>{spec['issue_address_shift']}];"]
        levels=streams.bit_length()-1
        out+=[f' wire [{w-1}:0] s{s}_packed=inverse_q ? gs_s{s}_q : ct_s{s}_q;',
              f' wire [26:0] s{s}_route[0:{levels}][0:{streams-1}];']
        for k in range(streams):out.append(f' assign s{s}_route[0][{k}]=s{s}_packed[{27*k}+:27];')
        for level in range(1,levels+1):
            for k in range(streams):
                out.append(f' assign s{s}_route[{level}][{k}]=base_bank_q[{s+level}] ? s{s}_route[{level-1}][{k^(1<<(level-1))}] : s{s}_route[{level-1}][{k}];')
        for lane in range(lanes):
            expression=f's{s}_route[{levels}][{lane>>s if s<kw else 0}]' if lane<plan['active'] else "27'd0"
            out.append(f' assign selected_stage_roots[{s}][{27*lane}+:27]={expression};')
    out+=[' always_ff @(posedge clk or negedge rst_n)begin',
          "  if(!rst_n)begin valid_q<=0;out_valid<=0;out_error<=0;out_tag<='0;roots<='0;end",
          '  else begin', '   valid_q<=accept;', '   if(request_valid && bad)out_error<=1;',
          '   if(accept)begin stage_q<=stage;inverse_q<=inverse;tag_q<=request_tag;',
          '    base_bank_q<=request_base_bank(stage,issue_index);end',
          '   out_valid<=valid_q && !out_error;',
          '   if(valid_q && !out_error)begin roots<=selected_stage_roots[stage_q];out_tag<=tag_q;end',
          '  end', ' end','endmodule\n']
    source='\n'.join(out)
    return dict(module=name,source=source,source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                root_table_sha256=table_hashes,layout=plan,
                final_upper_scale=math.normalization_constant(n,math.FIELDS[field]),
                engine_binding='issue E0 with data RAM, register both routed roots/data E1, BF E2, write E8; update row/valid/orientation tags.',
                profile_binding='new fixed-ROM format admission must validate exact compiled N/P; not a format2 upload cache.',
                native_or_engine_qualified=False)


def prepare(output,n=32,lanes=64,field=0,*,allow_full_constants=False):
    import json
    root=Path(__file__).resolve().parents[1]
    need(not(root/'docs/briefs/PAUSE').exists(),'brief PAUSE')
    output=Path(output).resolve();need(not output.exists(),'A10_LOOKUP_FRESH_OUTPUT')
    bundle=compile_lookup(n,lanes,field,allow_full_constants=allow_full_constants)
    output.mkdir(parents=True)
    path=output/(bundle['module']+'.sv');path.write_text(bundle['source'])
    receipt={k:v for k,v in bundle.items() if k!='source'}
    receipt.update(status='prepared_source_only_A10_root_lookup_not_executed',
        generated_bytes=path.stat().st_size,generated_source_file=path.name,
        author_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        geometry_source_sha256=physical.ENGINE_SHA,arithmetic_source_sha256=physical.MODEL_SHA,
        full_N_numeric_NTT_performed=False,promotion_allowed=False)
    (output/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt
