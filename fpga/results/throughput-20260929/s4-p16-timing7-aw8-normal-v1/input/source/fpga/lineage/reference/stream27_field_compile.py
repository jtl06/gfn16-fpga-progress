"""Emit additive S3 transform source without claiming a complete field.

This generator owns no commutator/BF source. Generated transforms use settled
v2 physical-slot ports and PAYLOAD1 constant-zero specialization. Small-N ROMs
can be emitted for local source review. Full-N emits only its source/ROM ledger
until a separately authorized native root preparation supplies exact files.
"""
from __future__ import annotations

from .stream27_field_plan import topology, root_word
from .stream_ntt_model import FIELDS


def compile_transform(n=32, field=0, *, inverse=False, emit_numeric_roms=True,
                      allow_large_root_tables=False):
    plan = topology(n, inverse=inverse)
    if field not in (0, 1, 2):
        raise ValueError('FIELD_PRIME')
    if emit_numeric_roms and n > 256 and not allow_large_root_tables:
        raise ValueError('FIELD_LOCAL_NUMERIC_ROOT_LIMIT: full-size root preparation is a separate native step')
    aw, ticks = plan['aw'], plan['frame_ticks']
    direction = 'dit' if inverse else 'dif'
    name = f'genefer_stream27_{direction}_aw{aw}_p8_f{field}'
    prime = FIELDS[field][0]
    out = [f'// SOURCE-ONLY generated transform: {name}; no RTL/clock qualification.',
           '// Payload is constant zero. Physical slot/frame tags survive cancellation.',
           '// Root files must all exist before this source can be staged for HDL.',
           f'module {name} #(parameter int GEN_W=8) (',
           '  input logic clk,rst_n,in_slot_valid,frame_start,quarantine,context_enabled,',
           '  input logic [GEN_W-1:0] generation_in,live_generation,',
           '  input logic [215:0] data_in,',
           '  output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,',
           '  output logic [GEN_W-1:0] generation_out,',
           '  output logic [215:0] data_out);',
           f'  localparam int STAGES={aw}, FRAME_T={ticks};',
           '  logic [STAGES:0] slot,start;',
           '  logic [GEN_W-1:0] generation[0:STAGES];',
           '  logic [215:0] data[0:STAGES];',
           '  logic [STAGES-1:0] stage_error,stage_pending;',
           '  wire stop=quarantine || (|stage_error);',
           '  assign slot[0]=in_slot_valid; assign start[0]=frame_start;',
           '  assign generation[0]=generation_in; assign data[0]=data_in;',
           '  assign out_error=|stage_error; assign fault_pending=|stage_pending;',
           '  assign out_slot_valid=slot[STAGES] && !stop;',
           '  assign out_frame_start=start[STAGES] && out_slot_valid;',
           '  assign generation_out=generation[STAGES];',
           '  assign out_eligible=out_slot_valid && context_enabled && generation_out==live_generation;',
           '// Recheck current generation and fault_pending at the external commit edge.']
    rom_files = {}
    rom_ledger = []
    for spec in plan['stages']:
        s = spec['stage']
        out += [f'  if (1) begin : stage{s}',
                '    logic row_slot,row_start;',
                '    logic [GEN_W-1:0] row_generation;',
                '    logic [215:0] row_data;',
                '    logic local_fault,shuffle_fault,shuffle_pending;',
                '    logic [5:0] slot_pipe,start_pipe;',
                '    logic [GEN_W-1:0] generation_pipe[0:5];',
                '    logic [3:0] bf_valid;',
                '    logic [215:0] bf_data;',
                '    localparam int COUNT_W=$clog2(FRAME_T+1);',
                '    logic [COUNT_W-1:0] remaining;',
                '    logic [GEN_W-1:0] owner_generation;',
                '    wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||',
                '      (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||',
                '      (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);',
                '    wire accept=row_slot && !stop && !local_fault && !cadence_bad;',
                f'    assign stage_error[{s}]=local_fault || shuffle_fault;',
                f'    assign stage_pending[{s}]=local_fault || shuffle_pending ||',
                '      (!stop && (cadence_bad || bf_valid!={4{slot_pipe[5]}}));']
        depth = spec['shuffle_depth_per_buffer']
        if depth:
            pos = spec['commutator_lane_position']
            shuffle_pairs = [(lane, lane ^ (1 << pos)) for lane in range(8)
                             if not lane & (1 << pos)]
            out += ['    logic [3:0] sh_slot,sh_start,sh_error,sh_pending;',
                    '    logic [GEN_W-1:0] sh_generation[0:3];',
                    f'    assign row_slot=sh_slot[0]; assign row_start=sh_start[0];',
                    '    assign row_generation=sh_generation[0];',
                    '    wire shuffle_alignment_bad=(|sh_slot) && ((!(&sh_slot)) ||',
                    '      sh_start!={4{sh_start[0]}} || sh_generation[1]!=sh_generation[0] ||',
                    '      sh_generation[2]!=sh_generation[0] || sh_generation[3]!=sh_generation[0]);',
                    '    assign shuffle_fault=|sh_error;',
                    '    assign shuffle_pending=(|sh_pending) || shuffle_alignment_bad;']
            for k, (lower, upper) in enumerate(shuffle_pairs):
                out += [f'    genefer_stream27_mdc_commutator_slots_v2 #(.DATA_W(27),.PAYLOAD_W(1),',
                        f'      .GEN_W(GEN_W),.DEPTH({depth}),.FRAME_T(FRAME_T),.CONTEXTS(1)) shuffle{k} (',
                        f'      .clk,.rst_n,.in_slot_valid(slot[{s}]),.frame_start(start[{s}]),',
                        f'      .upper_in(data[{s}][{lower*27}+:27]),.lower_in(data[{s}][{upper*27}+:27]),',
                        "      .upper_payload(1'b0),.lower_payload(1'b0),.context_in(1'b0),",
                        f'      .generation_in(generation[{s}]),.context_enabled(context_enabled),',
                        '      .live_generations(live_generation),.quarantine(stop),',
                        f'      .out_slot_valid(sh_slot[{k}]),.out_frame_start(sh_start[{k}]),.out_eligible(),',
                        f'      .out_error(sh_error[{k}]),.fault_pending(sh_pending[{k}]),',
                        f'      .upper_out(row_data[{lower*27}+:27]),.lower_out(row_data[{upper*27}+:27]),',
                        '      .upper_payload_out(),.lower_payload_out(),.context_out(),',
                        f'      .generation_out(sh_generation[{k}]));']
        else:
            out += [f'    assign row_slot=slot[{s}]; assign row_start=start[{s}];',
                    f'    assign row_generation=generation[{s}]; assign row_data=data[{s}];',
                    "    assign shuffle_fault=1'b0; assign shuffle_pending=1'b0;"]
        for r, root in enumerate(spec['unique_root_streams']):
            filename = f'{name}_stage{s}_root{r}.hex'
            first_root = root_word(plan, s, r, 0, field)
            entry = dict(file=filename if root['stored_words'] else None, stage=s, stream=r,
                         period=root['period'], stored_words=root['stored_words'], first_R_root=first_root,
                         complete_numeric_file=bool(emit_numeric_roms and root['stored_words']))
            rom_ledger.append(entry)
            if emit_numeric_roms and root['stored_words']:
                rom_files[filename] = ''.join(f'{root_word(plan,s,r,i,field):07x}\n'
                                             for i in range(root['period']))
            out += [f'    wire [26:0] root{r};',
                    f'    genefer_stream27_root_rom_prefetch #(.PERIOD({root["period"]}),',
                    f'      .FIRST_ROOT(27\'d{first_root}),.HEX_FILE("{filename if root["stored_words"] else ""}")) root_source{r} (',
                    f'      .clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(root{r}));']
        for k, (lower, upper) in enumerate(spec['pairs']):
            r = spec['root_stream_for_pair'][k]
            out += [f'    wire [31:0] y0_{k},y1_{k};',
                    f'    genefer_ntt_difdit_butterfly27 #(.P(32\'d{prime}),.Q(32\'d{(2-prime)%(1<<32)})) bf{k} (',
                    f"      .clk,.rst_n,.in_valid(accept),.dif(1'b{int(not inverse)}),",
                    f'      .u({{5\'b0,row_data[{lower*27}+:27]}}),.v({{5\'b0,row_data[{upper*27}+:27]}}),',
                    f"      .w({{5'b0,root{r}}}),.out_valid(bf_valid[{k}]),.y0(y0_{k}),.y1(y1_{k}));",
                    f'    assign bf_data[{lower*27}+:27]=y0_{k}[26:0];',
                    f'    assign bf_data[{upper*27}+:27]=y1_{k}[26:0];']
        out += [f'    assign slot[{s+1}]=slot_pipe[5] && (&bf_valid) && !stop;',
                f'    assign start[{s+1}]=start_pipe[5];',
                f'    assign generation[{s+1}]=generation_pipe[5]; assign data[{s+1}]=bf_data;',
                '    always_ff @(posedge clk or negedge rst_n) begin',
                "      if(!rst_n) begin slot_pipe<='0; start_pipe<='0; local_fault<=0; remaining<='0; end",
                '      else begin',
                '        if(!stop && (cadence_bad || shuffle_pending ||',
                '          (bf_valid!={4{slot_pipe[5]}}))) local_fault<=1;',
                "        if(stop) begin slot_pipe<='0; start_pipe<='0; end",
                '        else begin',
                '          slot_pipe<={slot_pipe[4:0],accept}; start_pipe<={start_pipe[4:0],accept && row_start};',
                '          generation_pipe[0]<=row_generation;',
                '          for(int k=1;k<6;k=k+1) generation_pipe[k]<=generation_pipe[k-1];',
                '          if(accept) begin',
                "            if(row_start) begin remaining<=COUNT_W'(FRAME_T-1); owner_generation<=row_generation; end",
                "            else remaining<=remaining-COUNT_W'(1);",
                '          end',
                '        end',
                '      end',
                '    end',
                '  end']
    for lane, source in enumerate(plan['terminal_wire']):
        out.append(f'  assign data_out[{lane*27}+:27]=data[STAGES][{source*27}+:27];')
    out.append('endmodule\n')
    return dict(module=name, source='\n'.join(out), rom_files=rom_files, rom_ledger=rom_ledger,
                topology=plan, source_dependencies=[
                    'rtl/kernel/genefer_stream27_mdc_commutator_slots_v2.sv',
                    'rtl/kernel/genefer_stream27_mdc_commutator_sync.sv',
                    'rtl/kernel/genefer_ntt_banked27_engine.sv',
                    'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv',
                    'rtl/kernel/genefer_stream27_root_rom_prefetch.sv'],
                emitted_numeric_roots=emit_numeric_roms,
                complete_field=False, RTL_qualified=False, HDL_run_performed=False)
