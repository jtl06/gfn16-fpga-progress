"""Exact one-stage root-network cut from frozen tiled RTL; not a timing proof."""
from pathlib import Path
import hashlib

ANCESTOR_SHA = 'd3dbaa6fe626e7e926b589f92b84959381b6c7aff74cb21a2d9f1d8d25353af0'


def expected(ancestor):
    if hashlib.sha256(ancestor.encode()).hexdigest() != ANCESTOR_SHA:
        raise ValueError('frozen tiled source changed')
    text = ancestor
    def change(old, new, count=1):
        nonlocal text
        if text.count(old) != count:
            raise ValueError('structural anchor count: ' + old)
        text = text.replace(old, new)

    change('genefer_ntt_banked27_tiled_engine', 'genefer_ntt_banked27_rootpipe_engine')
    change('// Tile-local replicas of four folded-router control registers; no added stage.',
           '// One extra root-XOR cut, with aligned operands, valid and writeback tags.')
    change('// Routing-retimed variant: RAM read-to-write distance is eight clocks.',
           '// Root-pipelined variant: RAM read-to-write distance is nine clocks.')
    change('    localparam int TILE_LANES=', '    localparam int ROOT_CUT=KW>1 ? KW/2 : 1;\n    localparam int TILE_LANES=')
    change('logic [7:0] orientation_pipe,point_half_pipe;', 'logic [8:0] orientation_pipe,point_half_pipe;')
    change('row_tag [0:7][0:BANKS-1]', 'row_tag [0:8][0:BANKS-1]')
    change('    logic [4:0] stage_bit_e;', '''    logic [31:0] data_mid_q [0:BANKS-1],root_point_mid_q [0:BANKS-1];
    logic [31:0] root_cut_q [0:BANKS-1];
    logic [4:0] stage_bit_mid,stage_bit_e;
    logic point_half_mid,low_stage_mid;
    logic [LANES-1:0] bf_mid_valid,mul_mid_valid;''')
    change('            stage_bit_e<=0;', '            stage_bit_mid<=0;stage_bit_e<=0;')
    change('            point_half_e<=0;low_stage_e<=0;',
           '            point_half_mid<=0;low_stage_mid<=0;point_half_e<=0;low_stage_e<=0;')
    change('            bf_route_valid<=0;mul_route_valid<=0;',
           '            bf_mid_valid<=0;mul_mid_valid<=0;bf_route_valid<=0;mul_route_valid<=0;')
    change('            stage_bit_e<=stage_bit_d;',
           '            stage_bit_mid<=stage_bit_d;stage_bit_e<=stage_bit_mid;')
    change('            point_half_e<=point_half_d;low_stage_e<=low_stage_d;',
           '            point_half_mid<=point_half_d;low_stage_mid<=low_stage_d;\n            point_half_e<=point_half_mid;low_stage_e<=low_stage_mid;')
    change('            bf_route_valid<=bf_in_valid;mul_route_valid<=mul_in_valid;',
           '            bf_mid_valid<=bf_in_valid;mul_mid_valid<=mul_in_valid;\n            bf_route_valid<=bf_mid_valid;mul_route_valid<=mul_mid_valid;')
    change('            data_route_q[b]<=data_q[b];',
           '            data_mid_q[b]<=data_q[b];data_route_q[b]<=data_mid_q[b];')
    change('            root_point_q[b]<=root_q[b];',
           '            root_point_mid_q[b]<=root_q[b];root_point_q[b]<=root_point_mid_q[b];')
    change('        (* preserve, dont_merge *) logic [PW-1:0] pairing_e;',
           '        (* preserve, dont_merge *) logic [PW-1:0] pairing_mid,pairing_e;')
    change('        (* preserve, dont_merge *) logic orientation_e;',
           '        (* preserve, dont_merge *) logic orientation_mid,orientation_e;')
    change('        (* preserve, dont_merge *) logic [KW-1:0] folded_root_bank_d;',
           '        (* preserve, dont_merge *) logic [KW-1:0] folded_root_bank_d,folded_root_bank_mid;')
    change('        (* preserve, dont_merge *) logic [PW-1:0] rotation_d;',
           '        (* preserve, dont_merge *) logic [PW-1:0] rotation_d,rotation_mid;')
    change('                pairing_e<=0;orientation_e<=0;',
           '                pairing_mid<=0;orientation_mid<=0;pairing_e<=0;orientation_e<=0;')
    change('                folded_root_bank_d<=0;rotation_d<=0;',
           '                folded_root_bank_d<=0;rotation_d<=0;folded_root_bank_mid<=0;rotation_mid<=0;')
    change('                pairing_e<=pairing_d;orientation_e<=orientation_d;',
           '                pairing_mid<=pairing_d;orientation_mid<=orientation_d;\n                pairing_e<=pairing_mid;orientation_e<=orientation_mid;')
    change('                rotation_d<=rotation;',
           '                rotation_d<=rotation;\n                folded_root_bank_mid<=folded_root_bank_d;rotation_mid<=rotation_d;')
    change('    // This removes the final BANKS-wide XOR network without changing latency.',
           '    // Preserve the folded mapping; add one cut after ROOT_CUT XOR dimensions.')
    change('''            else assign words[b]=control_tiles[b/TILE_BANKS].folded_root_bank_d[d-1] ? root_xor_stages[d-1].words[b^(1<<(d-1))] : root_xor_stages[d-1].words[b];''',
           '''            else if(d<=ROOT_CUT)
                assign words[b]=control_tiles[b/TILE_BANKS].folded_root_bank_d[d-1] ? root_xor_stages[d-1].words[b^(1<<(d-1))] : root_xor_stages[d-1].words[b];
            else if(d==ROOT_CUT+1)
                assign words[b]=control_tiles[b/TILE_BANKS].folded_root_bank_mid[d-1] ? root_cut_q[b^(1<<(d-1))] : root_cut_q[b];
            else
                assign words[b]=control_tiles[b/TILE_BANKS].folded_root_bank_mid[d-1] ? root_xor_stages[d-1].words[b^(1<<(d-1))] : root_xor_stages[d-1].words[b];''')
    change('    for(genvar b=0;b<BANKS;b=b+1) begin : root_route', '''    for(genvar b=0;b<BANKS;b=b+1) begin : root_cut_registers
        always_ff @(posedge clk) root_cut_q[b]<=root_xor_stages[ROOT_CUT].words[b];
    end
    for(genvar b=0;b<BANKS;b=b+1) begin : root_route''')
    change('            assign root_rotate_option[b][d]=root_xor_stages[KW].words[ROT];',
           '            if(ROOT_CUT==KW) assign root_rotate_option[b][d]=root_cut_q[ROT];\n            else assign root_rotate_option[b][d]=root_xor_stages[KW].words[ROT];')
    change('root_rotate_option[b][control_tiles[b/TILE_BANKS].rotation_d]',
           'root_rotate_option[b][control_tiles[b/TILE_BANKS].rotation_mid]')
    change('orientation_pipe[7]', 'orientation_pipe[8]')
    change('point_half_pipe[7]', 'point_half_pipe[8]')
    change('row_tag[7][bank]', 'row_tag[8][bank]', 2)
    change('orientation_pipe[6:0]', 'orientation_pipe[7:0]')
    change('point_half_pipe[6:0]', 'point_half_pipe[7:0]')
    change('for(int t=0;t<8;t=t+1)', 'for(int t=0;t<9;t=t+1)')
    change('for(int t=1;t<8;t=t+1)', 'for(int t=1;t<9;t=t+1)')
    return text


def validate_files(root):
    root = Path(root)/'rtl/kernel'
    source = (root/'genefer_ntt_banked27_tiled_engine.sv').read_text()
    candidate = (root/'genefer_ntt_banked27_rootpipe_engine.sv').read_text()
    if candidate != expected(source):
        raise ValueError('one-stage root-pipeline structural delta mismatch')
    return {'status': 'passed_structure_not_simulation', 'ancestor_sha256': ANCESTOR_SHA,
            'candidate_sha256': hashlib.sha256(candidate.encode()).hexdigest()}
