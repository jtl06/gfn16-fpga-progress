"""Additive scalable warm-field source, AW8..16, not RTL qualification.

Reuses native-supported tiny v4 ownership semantics without editing it. Uses
real full transform/IO ROM source and the new four-context correction producer.
No numeric NTT is executed here; full-size work is exact ROM constants only.
"""
from pathlib import Path
import hashlib
import re

from .stream27_field_square_warm_v4_compile import prepare as tiny_bundle
from .stream27_field_square_warm_v3_compile import replace_once
from .stream27_field_physical_probe_v1 import compile_probe
from .stream27_term_context_contract_v1 import seed_vectors,factors,production_calendar
from .stream27_epoch_protocol_v3 import geometry


def term_roots_source(n):
    aw=n.bit_length()-1;tw=aw-3;weights=seed_vectors(n);fs=factors(n)
    packed=[sum(word<<(27*lane) for lane,word in enumerate(vector)) for vector in weights]
    name=f'genefer_stream27_term_roots_aw{aw}_f0_v1'
    first_update=4;address=((first_update>>(tw-3))<<2)|(first_update&3)
    lines=[f'module {name} (',
           ' input logic clk,rst_n,seed_slot,seed_start,pw_slot,pw_start,',
           ' input logic [1:0] seed_row,',f' input logic [{tw-1}:0] pw_row,',
           ' output logic [215:0] seed_R_roots,next_seed_R_roots,',
           ' output logic [26:0] update_R_factor);',
           ' (* ramstyle = "M20K" *) logic [215:0] roots[0:31];',
           ' logic [215:0] prefetched;',
           f" wire [{tw-1}:0] following_target=pw_row+{tw}'d5;",
           f' wire [4:0] following_address={{following_target[{tw-1}-:3],following_target[1:0]}};',
           " wire [1:0] following_context=seed_row+2'd1;",
           f" assign seed_R_roots=seed_start ? 216'h{packed[0]:054x} : prefetched;",
           f" assign next_seed_R_roots=pw_start ? 216'h{packed[address]:054x} : prefetched;",
           ' initial begin']
    lines += [f" roots[{i}]=216'h{word:054x};" for i,word in enumerate(packed)]
    lines += [' end',' always_ff @(posedge clk)begin',
              "   if(rst_n && seed_slot)prefetched<=roots[{3'b0,following_context}];",
              '   else if(rst_n && pw_slot)prefetched<=roots[following_address];',' end',
              ' // Exact factor for m -> m+4, indexed by trailing ones of m>>2.',
              f' wire [{tw-3}:0] group_index=pw_row[{tw-1}:2];',
              ' integer factor_index;',
              ' always_comb begin', '   factor_index=0;']
    for trailing in range(1,len(fs)):
        lines.append(f"   if(group_index[{trailing-1}:0]=={trailing}'d{(1<<trailing)-1})factor_index={trailing};")
    lines += ['   case(factor_index)']
    lines += [f"     {i}:update_R_factor=27'd{word};" for i,word in enumerate(fs)]
    lines += [f"     default:update_R_factor=27'd{fs[0]};",'   endcase',' end','endmodule\n']
    return name,'\n'.join(lines)


def prepare(n=65536,*,allow_full_constants=False):
    if n<256 or n>65536 or n&(n-1):raise ValueError('WARM_FULL_AW8_16')
    aw=n.bit_length()-1;tw=aw-3;rows=n//8;bound=2*n+192
    minimum_base=max(2*n+5,(2*bound+2)//3+1)
    parent=tiny_bundle();physical=compile_probe(n,allow_full_constants=allow_full_constants)
    source=parent['files'][parent['top']+'.sv'];top=f'genefer_stream27_field_square_warm_aw{aw}_p8_f0_v1'
    source=replace_once(source,'module '+parent['top']+' (','module '+top+' (')
    source=source.replace('// Complete source-only tiny one-field square. No RTL/clock claim.',
        '// Scalable source-only warm field. Term recurrence and full composition remain unqualified.')
    # Unlike the frozen v4 comparison, this new public interface explicitly
    # suppresses admission handshakes while reset is asserted, even if request
    # pins remain high. Pending-fault values during reset remain unqualified.
    source=replace_once(source,'wire raw_frame_begin=in_slot_valid && frame_start',
        'wire raw_frame_begin=rst_n && in_slot_valid && frame_start')
    source=replace_once(source,'wire accepted_correction=correction_valid &&',
        'wire accepted_correction=rst_n && correction_valid &&')
    source=replace_once(source,'wire accepted=in_slot_valid &&',
        'wire accepted=rst_n && in_slot_valid &&')
    source=replace_once(source,'logic [2:0] remaining_input;',f'logic [{tw}:0] remaining_input;')
    source=replace_once(source,'logic [1:0] input_row,x_row,seed_issue,seed_capture,sink_row;',
        f'logic [{tw-1}:0] input_row,x_row,sink_row; logic [1:0] seed_issue;')
    source=replace_once(source,'logic [1:0] protocol_pw_row,protocol_sink_row;',
        f'logic [{tw-1}:0] protocol_pw_row,protocol_sink_row;')
    source=replace_once(source,"wire [1:0] digit_row=frame_start ? 2'd0 : input_row;",
        f"wire [{tw-1}:0] digit_row=frame_start ? {tw}'d0 : input_row;")
    source=source.replace("digit_base<32'd172",f"digit_base<32'd{minimum_base}").replace("32'd256)",f"32'd{bound})")
    source=source.replace('logic [10:0] digit_tag',f'logic [{tw+8}:0] digit_tag')
    source=source.replace('.PAYLOAD_W(11)',f'.PAYLOAD_W({tw+9})').replace('.AW(5),.BLOCKS(8)',f'.AW({aw}),.BLOCKS(8)')
    source=source.replace('digit_tag[0][2]',f'digit_tag[0][{tw}]').replace('digit_tag[0][10:3]',f'digit_tag[0][{tw+8}:{tw+1}]')
    source=source.replace('genefer_stream27_dif_aw5_p8_f0','genefer_stream27_dif_aw'+str(aw)+'_p8_f0')
    source=source.replace('genefer_stream27_dit_aw5_p8_f0','genefer_stream27_dit_aw'+str(aw)+'_p8_f0')
    g=geometry(n)
    source=replace_once(source,'.ROWS(4),.POINTWISE_FIRST(43),.SINK_FIRST(88)',
        f".ROWS({rows}),.POINTWISE_FIRST({g['pointwise_accept']}),.SINK_FIRST({g['sink_accept']})")
    source=source.replace('remaining_input<=3;input_row<=1;',f"remaining_input<={tw+1}'d{rows-1};input_row<={tw}'d1;")
    source=source.replace("remaining_input<=remaining_input-3'd1;input_row<=input_row+2'd1;",
        f"remaining_input<=remaining_input-{tw+1}'d1;input_row<=input_row+{tw}'d1;")
    source=source.replace("sink_row<=sink_row+2'd1;",f"sink_row<=sink_row+{tw}'d1;").replace('if(sink_row==3)',f"if(sink_row=={tw}'d{rows-1})")
    source=source.replace("if(fwd_slot)x_row<=correction_row+2'd1;",f"if(fwd_slot)x_row<=correction_row+{tw}'d1;")
    source=replace_once(source,"logic [1:0] addA_row; logic addA_bank; wire [1:0] correction_row=fwd_start ? 2'd0 : x_row;",
        f"logic [{tw-1}:0] addA_row; logic addA_bank; wire [{tw-1}:0] correction_row=fwd_start ? {tw}'d0 : x_row;")
    source=replace_once(source,'logic [26:0] A_table[0:1][0:7],B_table[0:1][0:7],term_table[0:1][0:3][0:7];',
        'logic [26:0] A_table[0:1][0:7],B_table[0:1][0:7];')
    # Remove all old tiny IO/seed root readers and fixed four-row term cache.
    pattern=r'  genefer_stream27_root_rom_prefetch #\(\.PERIOD\(4\),\.FIRST_ROOT\(27\x27d[0-9]+\),\s*\.HEX_FILE\("field-aw5-(?:twist|untwist|term)-lane[0-7]\.hex"\)\) [a-z_]+[0-7] \(\s*\.clk,\.rst_n,\.in_slot_valid\([^;]+?\);'
    source,count=re.subn(pattern,'',source)
    if count!=24:raise ValueError('WARM_FULL_OLD_ROM_ANCHORS: '+str(count))
    block_start=source.index('  genefer_stream27_mul8_v3 #(.GEN_W(24)) term_seed (')
    block_end=source.index('  logic [',block_start)
    source=source[:block_start]+source[block_end:]
    for lane in range(8):
        seed_select=f"  assign term_lhs[{27*lane}+:27]=B_table[seed_owner[8]][{{1'b{(lane>>2)&1},seed_issue[0],seed_issue[1]}}];"
        source=replace_once(source,seed_select,f'  assign term_lhs[{27*lane}+:27]=B_table[seed_owner[8]][0];')
        old=f"  assign addA_rhs[{27*lane}+:27]=A_table[protocol_pw_epoch[0]][{{1'b{(lane>>2)&1},correction_row[0],correction_row[1]}}];"
        source=replace_once(source,old,f'  assign addA_rhs[{27*lane}+:27]=A_table[protocol_pw_epoch[0]][{{correction_row[{tw-3}],correction_row[{tw-2}],correction_row[{tw-1}]}}];')
        source=replace_once(source,f'term_table[addA_bank][addA_row][{lane}]',f'term_result[{27*lane}+:27]')
    old='''        if(term_slot)begin
          for(int lane=0;lane<8;lane=lane+1)term_table[term_generation[8]][seed_capture][lane]<=term_result[lane*27+:27];
          seed_capture<=seed_capture+2'd1;
          if(seed_capture==3)tables_ready[term_generation[8]]<=1;
        end'''
    source=replace_once(source,old,'''        if(term_cache_ready)tables_ready[term_cache_owner[8]]<=1;''')
    source=source.replace('seed_issue<=0;seed_capture<=0;','seed_issue<=0;')
    source=replace_once(source,'.cache_ready(term_slot && seed_capture==3),.cache_epoch(term_generation[23:8]),.cache_generation(term_generation[7:0])',
        '.cache_ready(term_cache_ready),.cache_epoch(term_cache_owner[23:8]),.cache_generation(term_cache_owner[7:0])')
    roots_name,roots_source=term_roots_source(n)
    extra=f'''  logic term_cache_ready;
  logic [23:0] term_cache_owner;
  logic [{tw-1}:0] term_output_row;
  wire [{tw-1}:0] term_target_row=correction_row+{tw}'d4;
  wire [215:0] term_next_coeff,term_next_roots;
  wire [26:0] term_factor;
  for(genvar lane=0;lane<8;lane=lane+1)begin : term_coefficient
    assign term_next_coeff[lane*27+:27]=B_table[protocol_pw_epoch[0]][{{term_target_row[{tw-3}],term_target_row[{tw-2}],term_target_row[{tw-1}]}}];
  end
  {roots_name} term_roots (
    .clk,.rst_n,.seed_slot(seed_running),.seed_start(seed_running && seed_issue==0),.seed_row(seed_issue),
    .pw_slot(fwd_slot),.pw_start(fwd_start),.pw_row(correction_row),
    .seed_R_roots(term_rhs),.next_seed_R_roots(term_next_roots),.update_R_factor(term_factor));
  genefer_stream27_term_context_v1 #(.AW({aw})) term_producer (
    .clk,.rst_n,.quarantine(stop),.seed_slot(seed_running),.seed_start(seed_running && seed_issue==0),
    .seed_owner(seed_owner),.seed_row(seed_issue),.seed_coeff(term_lhs),.seed_R_roots(term_rhs),
    .pointwise_slot(fwd_slot),.pointwise_start(fwd_start),.pointwise_owner({{protocol_pw_epoch,fwd_generation}}),
    .pointwise_row(correction_row),.next_coeff(term_next_coeff),.next_seed_R_roots(term_next_roots),.update_R_factor(term_factor),
    .term_slot,.term_start,.term_owner(term_generation),.term_row(term_output_row),.term_data(term_result),
    .cache_ready(term_cache_ready),.cache_owner(term_cache_owner),.out_error(child_error[2]),.fault_pending(child_pending[2]));
  genefer_stream27_p2_twist_aw{aw}_f0_rom_v1 twist_roots_wide (
    .clk,.rst_n,.in_slot_valid(digit_slot && !stop),.frame_start(digit_tag[0][{tw}]),.root(twist_rhs));
  genefer_stream27_p2_untwist_aw{aw}_f0_rom_v1 untwist_roots_wide (
    .clk,.rst_n,.in_slot_valid(inv_slot && !stop),.frame_start(inv_start),.root(untwist_rhs));
'''
    source=replace_once(source,'  genefer_stream27_add8_v2 add_A (',extra+'  genefer_stream27_add8_v2 add_A (')
    oldjoin='''      (term_slot && (table_epoch[term_generation[8]]!=term_generation[23:8] ||
                    table_generation[term_generation[8]]!=term_generation[7:0]));'''
    source=replace_once(source,oldjoin,'''      (term_slot && (table_epoch[term_generation[8]]!=term_generation[23:8] ||
                    table_generation[term_generation[8]]!=term_generation[7:0])) ||
      (addA_slot && (!term_slot || term_output_row!=addA_row ||
        term_generation!={table_epoch[addA_bank],addA_generation}));''')
    if 'seed_capture' in source or 'term_table' in source:raise ValueError('WARM_FULL_TINY_STATE_REMAINS')
    files={name:text for name,text in parent['files'].items()
           if name in ('genefer_stream27_dif_aw3_p8_f0.sv','genefer_stream27_row_arithmetic_v3.sv')}
    for name,text in physical['files'].items():
        if name.startswith(('genefer_stream27_dif_aw','genefer_stream27_dit_aw','genefer_stream27_p2_initialized')):
            files[name]=text
    files[roots_name+'.sv']=roots_source;files[top+'.sv']=source
    deps=list(parent['source_dependencies'])+[
        'reference/stream27_field_square_warm_full_v1_compile.py','reference/stream27_term_context_contract_v1.py',
        'reference/stream27_field_physical_probe_v1.py','rtl/kernel/genefer_stream27_term_context_v1.sv',
        'tests/test_stream27_term_context_contract_v1.py','tests/test_stream27_field_square_warm_full_v1_compile.py']
    root=Path(__file__).resolve().parents[1]
    rtl_deps=[name for name in deps if name.endswith('.sv') and not name.endswith('genefer_stream27_epoch_protocol_v3.sv')]
    rtl_sources=list(dict.fromkeys(rtl_deps))+[name for name in files if name.endswith('.sv')]
    return dict(files=files,source_dependencies=deps,rtl_sources=rtl_sources,top=top,n=n,aw=aw,
        source_sha256={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in deps},
        generated_sha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in files.items()},
        geometry=g,term_calendar=production_calendar(n),full_N_numeric_NTT_performed=False,
        arithmetic_source_complete=True,RTL_qualified=False,native_run_performed=False,
        limits=['Source draft: new context/root glue needs bounded native pilot before AW16 correctness.',
                'Seed/update collisions quarantine rather than stall; production calendar has no collision.',
                'Finite epoch/generation reuse requires all producer messages drained, not descriptor retirement alone.'])
