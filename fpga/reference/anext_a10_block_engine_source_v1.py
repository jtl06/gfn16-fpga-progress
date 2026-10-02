"""Narrow additive A-next A10 independent-block derivative, no RTL execution.

Retains the exactly passed canonical A10 arithmetic/profile/root/data engine.
Adds the frozen A4 blockroute-v2 1R1W interface directly at the same RAM banks.
No host16-vector/block-offset conflation, no profile2 header or F2 recurrence.
The new component needs its own native/interface qualification; parent native
evidence only establishes the unchanged arithmetic path, not this derivative.
"""
import hashlib
from pathlib import Path

from fpga.reference import a10_banked_engine_generate_v1 as gen

ROOT = Path(__file__).resolve().parents[1]
PARENT = 'results/throughput-20260929/a10-batch-v1/aw16-f0/input/source/fpga/rtl/kernel/genefer_a10_banked27_engine_lint_v2.sv'
PARENT_SHA = '3f50001119f0ca672fa19f89f209765d0a4140abcd963b18107d4a407eebec16'
ROUTE = 'rtl/kernel/genefer_track_a4_blockroute_v2.sv'
ROUTE_SHA = '0d292ef6072f250f9255b758319e0754b0265a3d26be694601bb96b25a9e1cfa'
MODULE = 'genefer_anext_a10_block_engine_v1'
TARGET = 'rtl/kernel/' + MODULE + '.sv'
PORTS = '''    // A-next independent16block host access, canonical ordinary residues.
    input logic block_external_conflict,block_read_en,block_write_en,
    input logic [AW-1:0] block_read_offset,block_write_offset,
    input logic [15:0] block_read_mask,block_write_mask,
    input logic [511:0] block_write_words,
    output logic block_read_valid,block_error,
    output logic [AW-1:0] block_read_offset_out,
    output logic [15:0] block_read_mask_out,
    output logic [511:0] block_read_words,
'''
ROUTE_BINDING = '''    // Requests reject as one transaction: no legacy arbitration, no header
    // transfer/loading/busy/start access, no masked noncanonical write. Cold
    // ordinary-residue prefill is allowed before profile_loaded becomes true.
    logic block_request,block_bad_word;
    logic [127:0] block_re,block_we;
    logic [RW-1:0] block_ra[0:127],block_wa[0:127];
    logic [31:0] block_w[0:127];
    always_comb begin
        block_bad_word=0;
        for(int lane=0;lane<16;lane=lane+1)
            if(block_write_en && block_write_mask[lane] && block_write_words[lane*32+:32]>=P)
                block_bad_word=1;
    end
    wire block_enable=state==IDLE && !start && !block_external_conflict &&
        size_log2==5'(AW) && !load_we && !read_en && !vector_request &&
        !profile_request && !profile_loading && !profile_error && !block_bad_word;
    genefer_track_a4_blockroute_v2 #(.AW(AW),.RW(RW)) block_route (
        .clk,.rst_n,.enable(block_enable),.read_en(block_read_en),.write_en(block_write_en),
        .read_offset(block_read_offset),.write_offset(block_write_offset),
        .read_mask(block_read_mask),.write_mask(block_write_mask),.write_words(block_write_words),
        .ram_q(data_q),.request(block_request),.error(block_error),.read_valid(block_read_valid),
        .read_offset_out(block_read_offset_out),.read_mask_out(block_read_mask_out),.read_words(block_read_words),
        .ram_re(block_re),.ram_we(block_we),.ram_ra(block_ra),.ram_wa(block_wa),.ram_w(block_w)
    );
'''


def sha(raw): return hashlib.sha256(raw).hexdigest()


def expected():
    original = (ROOT / PARENT).read_text()
    if sha(original.encode()) != PARENT_SHA or sha((ROOT / ROUTE).read_bytes()) != ROUTE_SHA:
        raise ValueError('ANEXT_A10_PARENT_OR_ROUTE_DRIFT')
    text = gen.once(original, 'module genefer_a10_banked27_engine_v1 #(\n', 'module ' + MODULE + ' #(\n')
    text = gen.once(text, '    parameter int LANES=4,\n', '    parameter int LANES=64,\n')
    text = gen.once(text, '    input logic profile_begin,profile_we,profile_commit,profile_abort,\n',
        PORTS + '    input logic profile_begin,profile_we,profile_commit,profile_abort,\n')
    text = gen.once(text, "    assign seed_setup_cycles=64'd0;\n", "    assign seed_setup_cycles=64'd0;\n" + ROUTE_BINDING)
    text = gen.once(text, 'if(state!=IDLE || start ||\n', 'if(state!=IDLE || start || block_request ||\n')
    text = gen.once(text, '                if(vector_request)begin\n', '''                if(block_request)begin
                    data_re[bank]=block_re[bank];data_we[bank]=block_we[bank];
                    data_ra[bank]=block_ra[bank];data_wa[bank]=block_wa[bank];data_w[bank]=block_w[bank];
                end else if(vector_request)begin
''')
    for before, after in (
        ('            read_valid<=state==IDLE', '            read_valid<=!block_request && state==IDLE'),
        ('vector_read_valid<=state==IDLE', 'vector_read_valid<=!block_request && state==IDLE'),
        ('vector_read_mask<=state==IDLE', 'vector_read_mask<=!block_request && state==IDLE'),
        ('host_error<=state==IDLE', 'host_error<=!block_request && state==IDLE'),
        ('load_we || read_en || vector_request || read_valid || vector_read_valid)',
         'load_we || read_en || vector_request || read_valid || vector_read_valid ||\n                       block_request || block_read_valid || block_error)'),
        ('if(AW<1 || AW>16 || LANES!=64)', 'if(AW<5 || AW>16 || LANES!=64)'),
    ):
        text = gen.once(text, before, after)
    return '// A-next additive independent-block derivative; exact diff guarded, native unqualified.\n' + text


def verify():
    wanted = expected()
    if (ROOT / TARGET).read_text() != wanted:
        raise ValueError('ANEXT_A10_UNGUARDED_DERIVATIVE')
    return dict(module=MODULE, target=TARGET, sha256=sha(wanted.encode()),
        parent_sha256=PARENT_SHA, route_sha256=ROUTE_SHA, source_only=True,
        native_qualified=False, promotion_allowed=False)


def block_legal(*,aw,p,size_log2,state='IDLE',rst=True,start=False,external_conflict=False,
                scalar_request=False,vector_request=False,profile_request=False,
                profile_loading=False,profile_error=False,read_en=False,write_en=False,
                read_offset=0,write_offset=0,read_mask=65535,write_mask=65535,words=(0,)*16):
    """Small event oracle for new acceptance guards; not a numerical NTT."""
    if not (type(aw) is int and 5<=aw<=16 and 0<p<(1<<27) and len(words)==16):
        raise ValueError('ANEXT_A10_MODEL_GEOMETRY')
    t=1<<(aw-4)
    legal=bool(state=='IDLE' and not start and not external_conflict and size_log2==aw and
        not scalar_request and not vector_request and not profile_request and not profile_loading and
        not profile_error and (not write_en or all(not(write_mask>>j&1) or 0<=words[j]<p for j in range(16))) and
        (not read_en or 0<=read_offset<t) and (not write_en or 0<=write_offset<t) and
        not(read_en and write_en and read_offset==write_offset and read_mask&write_mask))
    return dict(error=int(bool(rst and (read_en or write_en) and not legal)),
        read_accept=bool(rst and read_en and legal),write_accept=bool(rst and write_en and legal))


if __name__=='__main__':
    import json
    print(json.dumps(verify(),indent=2))
