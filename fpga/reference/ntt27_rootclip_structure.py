"""Exact post-clip bank-register experiment; source/model checks, NOT RTL simulation."""
import hashlib
from pathlib import Path

ANCESTOR_SHA = 'cab41579a4b96793f52c31a2864f74aeab3d023f23b50f5c8acce368f07d1967'
BENCH_SHA = 'a71dbb8a374f0fc0e40c0dd9cd505a5201ba64cf4ec08cb1249db039665ee999'
OLD_TOP = 'genefer_ntt_banked27_rootpipe_engine'
TOP = 'genefer_ntt_banked27_rootclip_engine'


def pinned(text, sha):
    if hashlib.sha256(text.encode()).hexdigest() != sha:
        raise ValueError('qualified ancestor identity changed')


def once(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError('ambiguous structural anchor: '+old)
    return text.replace(old,new)


def expected(ancestor):
    pinned(ancestor,ANCESTOR_SHA)
    text=once(ancestor,OLD_TOP,TOP)
    text=once(text,'// One extra root-XOR cut, with aligned operands, valid and writeback tags.',
        '// LOCAL RTL-ONLY experiment: one post-root_clip bank-register stage.\n'
        '// Qualified rootpipe ancestor is unchanged; this clone is not simulated or fitted.')
    text=once(text,'// Root-pipelined variant: RAM read-to-write distance is nine clocks.',
        '// Root-clip variant: RAM read-to-write distance is ten clocks.')
    text=once(text,'logic [8:0] orientation_pipe,point_half_pipe;',
                       'logic [9:0] orientation_pipe,point_half_pipe;')
    text=once(text,'row_tag [0:8][0:BANKS-1]','row_tag [0:9][0:BANKS-1]')
    text=once(text,'    logic [31:0] root_clip [0:BANKS-1];',
        '    logic [31:0] root_clip [0:BANKS-1];\n'
        '    (* preserve, dont_merge *) logic [31:0] root_clip_q [0:BANKS-1];\n'
        '    logic [31:0] data_clip_q [0:BANKS-1],root_point_clip_q [0:BANKS-1];')
    text=once(text,'    logic [LANES-1:0] bf_route_valid,mul_route_valid;',
        '    logic [LANES-1:0] bf_route_valid,mul_route_valid;\n'
        '    logic [LANES-1:0] bf_clip_valid,mul_clip_valid;\n'
        '    logic point_half_f;')
    text=once(text,'            bf_mid_valid<=0;mul_mid_valid<=0;bf_route_valid<=0;mul_route_valid<=0;',
        '            bf_mid_valid<=0;mul_mid_valid<=0;bf_route_valid<=0;mul_route_valid<=0;\n'
        '            bf_clip_valid<=0;mul_clip_valid<=0;point_half_f<=0;')
    text=once(text,'            bf_route_valid<=bf_mid_valid;mul_route_valid<=mul_mid_valid;',
        '            bf_route_valid<=bf_mid_valid;mul_route_valid<=mul_mid_valid;\n'
        '            bf_clip_valid<=bf_route_valid;mul_clip_valid<=mul_route_valid;\n'
        '            point_half_f<=point_half_e;')
    text=once(text,'            root_point_mid_q[b]<=root_q[b];root_point_q[b]<=root_point_mid_q[b];',
        '            root_point_mid_q[b]<=root_q[b];root_point_q[b]<=root_point_mid_q[b];\n'
        '            data_clip_q[b]<=data_route_q[b];root_point_clip_q[b]<=root_point_q[b];')
    text=once(text,'(* preserve, dont_merge *) logic [PW-1:0] pairing_mid,pairing_e;',
                       '(* preserve, dont_merge *) logic [PW-1:0] pairing_mid,pairing_e,pairing_f;')
    text=once(text,'(* preserve, dont_merge *) logic orientation_mid,orientation_e;',
                       '(* preserve, dont_merge *) logic orientation_mid,orientation_e,orientation_f;')
    text=once(text,'                pairing_mid<=0;orientation_mid<=0;pairing_e<=0;orientation_e<=0;',
        '                pairing_mid<=0;orientation_mid<=0;pairing_e<=0;orientation_e<=0;\n'
        '                pairing_f<=0;orientation_f<=0;')
    text=once(text,'                pairing_e<=pairing_mid;orientation_e<=orientation_mid;',
        '                pairing_e<=pairing_mid;orientation_e<=orientation_mid;\n'
        '                pairing_f<=pairing_e;orientation_f<=orientation_e;')
    text=once(text,'        assign root_clip[b]=low_stage_e ? root_clip_option[b][PW\'(stage_bit_e)] : root_rotated[b];',
        '        assign root_clip[b]=low_stage_e ? root_clip_option[b][PW\'(stage_bit_e)] : root_rotated[b];\n'
        '        always_ff @(posedge clk) root_clip_q[b]<=root_clip[b];')
    # Scope consumer substitution to arithmetic only: host RAM/API and existing
    # routing/clock edges are deliberately unchanged.
    begin='    for(genvar lane=0;lane<LANES;lane=lane+1) begin : arithmetic\n'
    end='    for(genvar bank=0;bank<BANKS;bank=bank+1) begin : memories\n'
    if text.count(begin)!=1 or text.count(end)!=1:raise ValueError('arithmetic region changed')
    start=text.index(begin);stop=text.index(end)
    region=text[start:stop]
    for old,new,count in [('data_route_q[','data_clip_q[',4),('root_point_q[','root_point_clip_q[',2),
                          ('root_clip[','root_clip_q[',2),('.pairing_e]','.pairing_f]',6),
                          ('.orientation_e ','.orientation_f ',3),('point_half_e','point_half_f',2),
                          ('bf_route_valid','bf_clip_valid',6),('mul_route_valid','mul_clip_valid',3)]:
        region=once(region,old,new,count)
    text=text[:start]+region+text[stop:]
    for old,new,count in [('orientation_pipe[8]','orientation_pipe[9]',1),
                          ('point_half_pipe[8]','point_half_pipe[9]',1),
                          ('row_tag[8][bank]','row_tag[9][bank]',2),
                          ('orientation_pipe[7:0]','orientation_pipe[8:0]',1),
                          ('point_half_pipe[7:0]','point_half_pipe[8:0]',1),
                          ('for(int t=0;t<9;t=t+1)','for(int t=0;t<10;t=t+1)',1),
                          ('for(int t=1;t<9;t=t+1)','for(int t=1;t<10;t=t+1)',1)]:
        text=once(text,old,new,count)
    return text


def bench_expected(ancestor):
    pinned(ancestor,BENCH_SHA)
    text=once(ancestor,OLD_TOP,TOP,2)
    return once(text,'(op==0?9*lg:0)+(mul?9:0)','(op==0?10*lg:0)+(mul?10:0)')


def validate_files(root):
    root=Path(root);kernel=root/'rtl/kernel';bench=root/'rtl/tb'
    rtl=(kernel/(TOP+'.sv')).read_text()
    cpp=(bench/'ntt_banked27_rootclip_engine.cpp').read_text()
    if rtl!=expected((kernel/(OLD_TOP+'.sv')).read_text()):raise ValueError('unreviewed rootclip RTL delta')
    if cpp!=bench_expected((bench/'ntt_banked27_rootpipe_engine.cpp').read_text()):raise ValueError('unreviewed rootclip bench delta')
    return dict(status='local_source_model_checks_only_not_simulated',ancestor_sha256=ANCESTOR_SHA,
                rtl_sha256=hashlib.sha256(rtl.encode()).hexdigest(),bench_sha256=hashlib.sha256(cpp.encode()).hexdigest())


def costs(aw=16,lanes=64):
    if type(aw)!=int or not 1<=aw<=16 or type(lanes)!=int or lanes<1 or lanes>64 or lanes&(lanes-1):
        raise ValueError('unsupported geometry')
    kw=lanes.bit_length();pw=max(1,(kw-1).bit_length());banks=2*lanes
    rw=max(1,aw-kw);tiles=lanes//min(lanes,8);n=1<<aw
    payload=3*banks*32;row=banks*rw;control=2*lanes+tiles*(pw+1)+1+2
    phase=lambda drain:2*aw*((n+banks-1)//banks+1+drain)+3*((n+lanes-1)//lanes+drain)
    return dict(payload_bits=payload,row_tag_bits=row,control_bits=control,
                logical_register_bits=payload+row+control,old_cycles=phase(9),new_cycles=phase(10),
                extra_cycles=2*aw+3,extra_ram_bits=0,extra_multiplier_pipelines=0)


# Planned source mutants, not executed RTL regressions. Expected rejection must
# be demonstrated by a future independent oracle, never inferred from these edits.
MUTATIONS = (
    ('clip-bypass','assign root_lo[p]=root_clip_q[LO];assign root_hi[p]=root_clip_q[HI];',
                   'assign root_lo[p]=root_clip[LO];assign root_hi[p]=root_clip[HI];'),
    ('data-bypass','assign data_lo[p]=data_clip_q[LO];assign data_hi[p]=data_clip_q[HI];',
                   'assign data_lo[p]=data_route_q[LO];assign data_hi[p]=data_route_q[HI];'),
    ('point-root-bypass','(point_half_f ? root_point_clip_q[lane+LANES] : root_point_clip_q[lane])',
                         '(point_half_f ? root_point_q[lane+LANES] : root_point_q[lane])'),
    ('pairing-delay','pairing_f<=pairing_e;','pairing_f<=pairing_mid;'),
    ('orientation-delay','orientation_f<=orientation_e;','orientation_f<=orientation_mid;'),
    ('point-half-delay','point_half_f<=point_half_e;','point_half_f<=point_half_mid;'),
    ('bf-valid-delay','bf_clip_valid<=bf_route_valid;','bf_clip_valid<=bf_mid_valid;'),
    ('mul-valid-delay','mul_clip_valid<=mul_route_valid;','mul_clip_valid<=mul_mid_valid;'),
    ('kind-delay','point_type_pipe<={point_type_pipe[4:0],mul_clip_valid[lane]};',
                  'point_type_pipe<={point_type_pipe[4:0],mul_route_valid[lane]};'),
    ('bf-row-tag','data_wa[bank]=row_tag[9][bank];data_w[bank]=bf_write_option[pairing];',
                  'data_wa[bank]=row_tag[8][bank];data_w[bank]=bf_write_option[pairing];'),
    ('point-row-tag','data_wa[bank]=row_tag[9][bank];data_w[bank]=product[bank%LANES];',
                     'data_wa[bank]=row_tag[8][bank];data_w[bank]=product[bank%LANES];'),
    ('orientation-tag','orientation_pipe[9]==','orientation_pipe[8]=='),
    ('point-half-tag','point_half_pipe[9])','point_half_pipe[8])'),
    ('reset-bf-valid','bf_clip_valid<=0;',''),
    ('reset-mul-valid','mul_clip_valid<=0;',''),
)


def targeted_mutants(candidate):
    return {name:once(candidate,old,new) for name,old,new in MUTATIONS}
