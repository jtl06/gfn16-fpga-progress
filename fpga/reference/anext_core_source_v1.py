"""Exact additive A4b+A10 composition source, promoted-T5b lineage explicit.

No frozen RTL is edited. F2 recurrence is absent, not instantiated unused.
Native block-interface/three-phase and complete-core gates remain required.
"""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PINS={
 'rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1.sv':'704f7fed433d724dbc8e56c7b725824ec36cce78d6ce8f021307837d2a96b8e7',
 'rtl/kernel/genefer_track_a4_ntt_sequencer_v1.sv':'f5ba08a60c0ebae30aa00c3485fefc0c6376d7901d6cf5e47d1baf8b8627cbe0',
 'rtl/kernel/genefer_track_a4_square_backend_v4.sv':'af1e4bb2877f652f7c63d2f4d005eee67b7feb1bfda028bbb5f0e4e61fa8b37b',
 'rtl/kernel/genefer_track_a4_core_v4.sv':'877e6bea81585f6e2b9b07a0a1d65ef22a21afcdd584db7dff2f4f501e1841b6',
 'rtl/kernel/genefer_a10_profile3_v1.sv':'526ede3d3bbb7bd43baf9f6830a087c5ba3f89ee0c6f5d32a8de24e57f27fd4b',
 'rtl/tb/track_a4_core_v4.cpp':'85a4598a4437cd7afd7d7cb2090ad00859cd6e99ca5586c95326f3cb577d2384',
}


def once(text,before,after):
    if text.count(before)!=1:raise ValueError('ANEXT_EXACT_SOURCE_ANCHOR '+before[:80])
    return text.replace(before,after)


def expected():
    texts={}
    for name,pin in PINS.items():
        raw=(ROOT/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('ANEXT_PARENT_DRIFT '+name)
        texts[name]=raw.decode()
    seq=texts['rtl/kernel/genefer_track_a4_ntt_sequencer_v1.sv']
    replacements=[
      ('module genefer_track_a4_ntt_sequencer_v1','module genefer_anext_ntt_sequencer_v1'),
      ("    localparam logic [31:0] G[0:2]='{32'd3,32'd5,32'd10};\n",''),
      ('localparam int PROFILE_WORDS=(2*AW+2)*(4*NTT_LANES+1);','localparam int PROFILE_WORDS=4;'),
      ('logic [31:0] rom_data[0:2];','logic [31:0] rom_data[0:2],expected_header[0:2];'),
      ("assign root_phase=step==0 ? 2'd0 : step==1 ? 2'd1 : step==3 ? 2'd2 : 2'd3;","assign root_phase=step==0 ? 2'd1 : step==2 ? 2'd2 : 2'd0;"),
      ("assign ntt_op=step==0 || step==4 ? 2'd2 : step==2 ? 2'd1 : 2'd0;","assign ntt_op=step==1 ? 2'd1 : 2'd0;"),
      ('genefer_root_profile27_r2_rom #(.AW(AW),.LANES(NTT_LANES),.P(P[f]),.GENERATOR(G[f])) roots (',
       '''genefer_a10_profile3_constants_v1 #(.AW(AW),.P(P[f])) header_contract (
            .address(profile_words_loaded),.word(expected_header[f]),.normalization(),.psi()
        );
        genefer_a10_profile3_rom_v1 #(.AW(AW),.P(P[f])) roots ('''),
      ('genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_blockroute_v2_engine #(', 'genefer_anext_a10_block_engine_v1 #('),
      ('.AW(AW),.LANES(NTT_LANES),.HOST_LANES(16),.P(P[f]),.Q(Q[f])) engine (','.AW(AW),.LANES(NTT_LANES),.P(P[f]),.Q(Q[f])) engine ('),
      (".vector_lane_mask(16'd0),.vector_write_data(512'd0),.vector_read_valid(),", ".vector_lane_mask(64'd0),.vector_write_data(2048'd0),.vector_read_valid(),"),
      ('.block_read_en(block_read_en && !start_ntt),', ".block_external_conflict(1'b0),.block_read_en(block_read_en && !start_ntt),"),
      ('.profile_commit(state==PROFILE_COMMIT),.profile_size_log2', ".profile_commit(state==PROFILE_COMMIT),.profile_abort(1'b0),.profile_size_log2"),
      (".profile_modulus(P[f]),.profile_format(8'd2)",".profile_modulus(P[f]),.profile_format(8'd3)"),
      ('.profile_next_addr(profile_next[f]),.seed_setup_cycles(child_seed_cycles[f]),',
       '.profile_next_addr(profile_next[f]),.seed_setup_cycles(child_seed_cycles[f]),\n            .root_rom_reads(),.normalization_products(),.profile_epoch(),'),
      (".start(state==NTT_START),.inverse(1'b0),.dif(step==1)",'.start(state==NTT_START),.inverse(step==2),.dif(step==2)'),
      ('rom_data[0]>=P[0] || rom_data[1]>=P[1] || rom_data[2]>=P[2] ||',
       'rom_data[0]!=expected_header[0] || rom_data[1]!=expected_header[1] || rom_data[2]!=expected_header[2] ||'),
      ('else if(step==4) begin','else if(step==2) begin'),
      ('A4_NTT_SEQUENCER_GEOMETRY','ANEXT_NTT_SEQUENCER_GEOMETRY'),
    ]
    for before,after in replacements:seq=once(seq,before,after)
    # Comments distinguish the new arithmetic/profile from frozen format2 ancestry.
    seq=once(seq,'// Frozen T5 profile/five-phase cases are source-delta guarded. Route-v2 engines\n// retain all arithmetic. Caller owns complete ordinary-residue field prefill.',
      '// A10 format3 three-phase cases are exact-delta guarded. New block-port A10\n// engine retains canonical arithmetic. Caller owns ordinary-residue prefill.')
    backend=texts['rtl/kernel/genefer_track_a4_square_backend_v4.sv']
    backend=once(backend,'module genefer_track_a4_square_backend_v4','module genefer_anext_square_backend_v1')
    backend=once(backend,'genefer_track_a4_ntt_sequencer_v1 #','genefer_anext_ntt_sequencer_v1 #')
    core=texts['rtl/kernel/genefer_track_a4_core_v4.sv']
    core=once(core,'module genefer_track_a4_core_v4','module genefer_anext_core_v1')
    core=once(core,'genefer_track_a4_square_backend_v4 #','genefer_anext_square_backend_v1 #')
    bench=texts['rtl/tb/track_a4_core_v4.cpp'].replace('genefer_track_a4_core_v4','genefer_anext_core_v1')
    return {'rtl/kernel/genefer_anext_ntt_sequencer_v1.sv':seq,
            'rtl/kernel/genefer_anext_square_backend_v1.sv':backend,
            'rtl/kernel/genefer_anext_core_v1.sv':core,
            'rtl/tb/track_anext_core_v1.cpp':bench}


def verify():
    files=expected()
    for path,text in files.items():
        if (ROOT/path).read_text()!=text:raise ValueError('ANEXT_UNGUARDED_COMPOSITION '+path)
    return {path:hashlib.sha256(text.encode()).hexdigest() for path,text in files.items()}


if __name__=='__main__':
    import json
    print(json.dumps(verify(),indent=2))
