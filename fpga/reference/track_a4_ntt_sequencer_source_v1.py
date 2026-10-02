"""Isolated three-field sequencer source-delta guard, no HDL execution.

Frozen T5's complete profile and five-phase state cases are byte-identical
except final exit ownership. Arithmetic/root adapters are separately guarded.
"""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT='rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill.sv'
PARENT_SHA='fc8f381d0db17d3c1bff9ee4b89a99878102099b2c6a404d60157ce2c6b5d6af'
NEW='rtl/kernel/genefer_track_a4_ntt_sequencer_v1.sv'
NEW_SHA='f5ba08a60c0ebae30aa00c3485fefc0c6376d7901d6cf5e47d1baf8b8627cbe0'
PINS={
    PARENT:PARENT_SHA,
    'rtl/kernel/genefer_root_profile27_r2_rom.sv':'cb851bec51f518a71d216d4a993ffa3aa937b8230474c38898b061e7ad42dea6',
    'rtl/kernel/genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_blockroute_v2_engine.sv':'9b49d38319777baaed70560cb56bc71e5c16cbd2d30bc576fd1d7abb995b1df7',
    'rtl/kernel/genefer_ntt_banked27_prefetch_r2_orient8_rootfused_blockroute_v2_engine.sv':'c4d66bf94e91a160438bc1eaf8afc260663b3241ebefb07f021b56e91723434e',
    'rtl/kernel/genefer_track_a4_blockroute_v2.sv':'0d292ef6072f250f9255b758319e0754b0265a3d26be694601bb96b25a9e1cfa',
}


def require(ok,why):
    if not ok:raise ValueError(why)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def between(text,start,end):
    require(text.count(start)==1 and text.count(end)==1,'unique source-delta anchors')
    return text[text.index(start):text.index(end)]


def validate_text(parent,text):
    profile=between(parent,'                PROFILE_BEGIN:','                NTT_START:')
    require(between(text,'                PROFILE_BEGIN:','                NTT_START:')==profile,
            'T5 complete profile FSM changed')
    phases=between(parent,'                NTT_START:','                RESIDUES:')
    old='else if(step==4) begin issue_count<=0; write_count<=0; state<=RESIDUES; end'
    new='else if(step==4) begin state<=IDLE;busy<=0;done<=1;end'
    require(phases.count(old)==1,'single final-phase handoff anchor')
    require(between(text,'                NTT_START:','                FAILED:')==phases.replace(old,new,1),
            'T5 NTT five-phase timing/seed counters changed')
    for start,end in (
        ('    assign profile_coherent=','    assign read_valid='),
    ):
        wanted=between(parent,start,end)
        require(between(text,start,'    assign root_phase=')==wanted,
                'T5 profile completeness/domain binding changed')
    for prefix in ('    localparam logic [31:0] P[0:2]=','    localparam logic [31:0] Q[0:2]=',
                   '    localparam logic [31:0] G[0:2]=','    localparam int PROFILE_WORDS=',
                   '    assign root_phase=','    assign ntt_op='):
        parent_line=next(row for row in parent.splitlines() if row.startswith(prefix))
        require(parent_line in text.splitlines(),'T5 field/domain/phase expression changed: '+prefix)
    for token in ('.profile_format(8\'d2)',".inverse(1'b0),.dif(step==1)",'.root_phase,.op(ntt_op)',
                  ".size_log2(5'(AW)),.scale(32'd0)",
                  'wire children_rst_n=rst_n && !cancel && state!=FAILED;',
                  '.block_read_en(block_read_en && !start_ntt),.block_write_en(block_write_en && !start_ntt)',
                  '!(|profile_loading) && !(|block_read_valid) && !core_fault && !block_request &&'):
        require(token in text,'sequencer interface/quarantine contract changed: '+token)
    for forbidden in ('genefer_crt3','genefer_carry_','genefer_digit_reduce','genefer_track_a4_post_ntt',
                      'genefer_track_a4_host_shell','genefer_track_a4_digit_image','public_flat'):
        require(forbidden not in text,'sequencer arithmetic/host ownership expansion')
    return dict(profile_cases='byte-identical T5',ntt_cases='byte-identical except final idle/done handoff',
                phases=[dict(step=0,op=2,root_phase=0,dif=0),dict(step=1,op=0,root_phase=1,dif=1),
                        dict(step=2,op=1,root_phase=3,dif=0),dict(step=3,op=0,root_phase=2,dif=0),
                        dict(step=4,op=2,root_phase=3,dif=0)],
                domain='ordinary field prefill -> R2 twist/Montgomery spectrum -> ordinary untwist output',
                claims='Source bound only; no elaboration/native/whole-core qualification.')


def verify(root=ROOT):
    root=Path(root)
    for name,digest in {**PINS,NEW:NEW_SHA}.items():
        require(sha(root/name)==digest,'frozen sequencer/dependency source pin: '+name)
    result=validate_text((root/PARENT).read_text(),(root/NEW).read_text())
    from fpga.reference import track_a4_blockroute_source_v2
    track_a4_blockroute_source_v2.verify()
    result['source_sha256']={**PINS,NEW:NEW_SHA}
    return result
