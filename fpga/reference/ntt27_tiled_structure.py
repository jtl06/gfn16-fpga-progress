"""Structural gate for a control-only clone; no synthesis or timing claim."""
import hashlib
from pathlib import Path

ANCESTOR_SHA='475a7500e58485c943961729334f8c03e35eb52095657813f8c770d29cb5167c'
HEADER='// Tile-local replicas of four folded-router control registers; no added stage.\n// See NTT27-TILED-CONTROLS.md for official Quartus preservation semantics.\n'
TILE_BLOCK='''
    // Each replica is a real destination-local driver, not an unused copy.
    // preserve blocks removal/retiming; dont_merge blocks duplicate merging.
    // Capture original predecessor/RHS on the original edge, never another copy.
    for(genvar t=0;t<TILES;t=t+1) begin : control_tiles
        (* preserve, dont_merge *) logic [PW-1:0] pairing_e;
        (* preserve, dont_merge *) logic orientation_e;
        (* preserve, dont_merge *) logic [KW-1:0] folded_root_bank_d;
        (* preserve, dont_merge *) logic [PW-1:0] rotation_d;
        always_ff @(posedge clk or negedge rst_n) begin
            if(!rst_n) begin
                pairing_e<=0;orientation_e<=0;
                folded_root_bank_d<=0;rotation_d<=0;
            end else begin
                pairing_e<=pairing_d;orientation_e<=orientation_d;
                folded_root_bank_d<=root_base_bank ^ rol(base_bank & folding_mask,rotation);
                rotation_d<=rotation;
            end
        end
    end

'''


def expected(ancestor):
    if hashlib.sha256(ancestor.encode()).hexdigest()!=ANCESTOR_SHA:
        raise ValueError('frozen folded ancestor mismatch')
    text=HEADER+ancestor.replace('genefer_ntt_banked27_folded_engine','genefer_ntt_banked27_tiled_engine')
    substitutions=[
        ('    localparam int PW=KW>1 ? $clog2(KW) : 1;',
         '    localparam int PW=KW>1 ? $clog2(KW) : 1;\n    localparam int TILE_LANES=LANES<8 ? LANES : 8;\n    localparam int TILE_BANKS=2*TILE_LANES,TILES=LANES/TILE_LANES;'),
        ('pairing,rotation,pairing_d,rotation_d;','pairing,rotation,pairing_d;'),
        ('base_bank,root_base_bank,root_mask,folded_root_bank_d;','base_bank,root_base_bank,root_mask;'),
        ('    logic [PW-1:0] pairing_e;\n',''),
        ('logic orientation_e,point_half_e,low_stage_e;','logic point_half_e,low_stage_e;'),
        ('pairing_e<=0;stage_bit_e<=0;','stage_bit_e<=0;'),
        ('orientation_e<=0;point_half_e<=0;low_stage_e<=0;','point_half_e<=0;low_stage_e<=0;'),
        ('pairing_e<=pairing_d;stage_bit_e<=stage_bit_d;','stage_bit_e<=stage_bit_d;'),
        ('orientation_e<=orientation_d;point_half_e<=point_half_d;','point_half_e<=point_half_d;'),
        ('pairing_d<=0;rotation_d<=0;folded_root_bank_d<=0;','pairing_d<=0;'),
        ('pairing_d<=pairing;rotation_d<=rotation;stage_bit_d<=stage_bit;','pairing_d<=pairing;stage_bit_d<=stage_bit;'),
        ('            folded_root_bank_d<=root_base_bank ^ rol(base_bank & folding_mask,rotation);\n',''),
        ('folded_root_bank_d[d-1] ?','control_tiles[b/TILE_BANKS].folded_root_bank_d[d-1] ?'),
        ('root_rotate_option[b][rotation_d]','root_rotate_option[b][control_tiles[b/TILE_BANKS].rotation_d]'),
    ]
    for old,new in substitutions:
        if text.count(old)!=1:raise ValueError('structural anchor mismatch: '+old)
        text=text.replace(old,new)
    for signal in ('orientation_e','pairing_e'):
        text=text.replace(signal,'control_tiles[lane/TILE_LANES].'+signal)
    text=text.replace('    // Fold the data-bank XOR into the first root-bank XOR:\n',
                      TILE_BLOCK+'    // Fold the data-bank XOR into the first root-bank XOR:\n')
    return text


def validate(ancestor,candidate):
    if candidate.rstrip()!=expected(ancestor).rstrip():
        raise ValueError('tile-control-only structure mismatch')


def geometry(lanes):
    if type(lanes) is not int or lanes<1 or lanes>64 or lanes&(lanes-1):
        raise ValueError('unsupported lanes')
    kw=lanes.bit_length();pw=max(1,(kw-1).bit_length())
    width=min(lanes,8);tiles=lanes//width;bits=2*pw+kw+1
    return dict(lanes=lanes,tile_lanes=width,tile_banks=2*width,tiles=tiles,
                bits_per_tile=bits,declared_register_bits=tiles*bits,
                added_register_bits=(tiles-1)*bits,latency_delta=0)


def validate_files(root):
    kernel=Path(root)/'rtl/kernel'
    ancestor=kernel/'genefer_ntt_banked27_folded_engine.sv'
    candidate=kernel/'genefer_ntt_banked27_tiled_engine.sv'
    validate(ancestor.read_text(),candidate.read_text())
    return dict(status='passed',ancestor_sha256=ANCESTOR_SHA,
                candidate_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
                profiles=[geometry(n) for n in (1,2,4,8,16,32,64)])
