"""Exact additive parent-to-derivative guard; no broad textual copying drift."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = "genefer_ntt_banked27_prefetch_r2_orient8_rootfused_engine"
ADAPTER = "genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_engine"
ENGINE_NEW = "genefer_ntt_banked27_prefetch_r2_orient8_rootfused_blockroute_v1_engine"
ADAPTER_NEW = "genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_blockroute_v1_engine"
PINS = {ENGINE: "d52351bdf53c6809208f7a466848b4376cbd8ff87c52f633dc8c2814026b47ee",
        ADAPTER: "b3d06d1e5f90e4944fdf88ff264cb7edbd73d0daf9f46ccf93389ab4889d9e3f"}
PORTS = """    // A4 additive independent block ports; inactive ports preserve parent behavior.
    input logic block_read_en,block_write_en,
    input logic [AW-1:0] block_read_offset,block_write_offset,
    input logic [15:0] block_read_mask,block_write_mask,
    input logic [511:0] block_write_words,
    output logic block_read_valid,block_error,
    output logic [AW-1:0] block_read_offset_out,
    output logic [15:0] block_read_mask_out,
    output logic [511:0] block_read_words,
"""
ROUTE = """    // A4 route accepts only fixed-N idle access, and rejects all host/profile
    // arbitration conflicts atomically. Legacy ports are untouched when inactive.
    logic block_request;
    logic [127:0] block_re,block_we;
    logic [RW-1:0] block_ra[0:127],block_wa[0:127];
    logic [31:0] block_w[0:127];
    wire block_enable=state==IDLE && !start && !block_external_conflict && size_log2==5'(AW) &&
        !load_we && !read_en && !vector_request && !profile_begin && !profile_we && !profile_commit;
    genefer_track_a4_blockroute_v1 #(.AW(AW),.RW(RW)) block_route (
        .clk,.rst_n,.enable(block_enable),.read_en(block_read_en),.write_en(block_write_en),
        .read_offset(block_read_offset),.write_offset(block_write_offset),
        .read_mask(block_read_mask),.write_mask(block_write_mask),.write_words(block_write_words),
        .ram_q(data_q),.request(block_request),.error(block_error),.read_valid(block_read_valid),
        .read_offset_out(block_read_offset_out),.read_mask_out(block_read_mask_out),.read_words(block_read_words),
        .ram_re(block_re),.ram_we(block_we),.ram_ra(block_ra),.ram_wa(block_wa),.ram_w(block_w)
    );
"""


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError("additive source guard: expected exactly one anchor: " + before[:80])
    return text.replace(before, after, 1)


def expected(parent):
    original = (ROOT/"rtl/kernel"/(parent+".sv")).read_text()
    if hashlib.sha256(original.encode()).hexdigest() != PINS[parent]:
        raise ValueError("frozen parent source drift")
    new = ENGINE_NEW if parent == ENGINE else ADAPTER_NEW
    text = replace_once(original, "module "+parent+" #(", "module "+new+" #(")
    text = replace_once(text, "    input logic profile_begin,profile_we,profile_commit,\n", PORTS+"    input logic profile_begin,profile_we,profile_commit,\n")
    if parent == ENGINE:
        text = replace_once(text, "    parameter int LANES=4,\n", "    parameter int LANES=64,\n")
        text = replace_once(text, "    input logic block_read_en,block_write_en,\n", "    input logic block_external_conflict,\n    input logic block_read_en,block_write_en,\n")
        text = replace_once(text, "    logic [RW-1:0] row_tag [0:6][0:BANKS-1];\n", ROUTE+"    logic [RW-1:0] row_tag [0:6][0:BANKS-1];\n")
        text = replace_once(text, "                if(vector_request) begin\n", """                if(block_request) begin
                    data_re[bank]=block_re[bank];data_we[bank]=block_we[bank];
                    data_ra[bank]=block_ra[bank];data_wa[bank]=block_wa[bank];data_w[bank]=block_w[bank];
                end else if(vector_request) begin
""")
        for before, after in (
            ("done<=0;read_valid<=state==IDLE", "done<=0;read_valid<=!block_request && state==IDLE"),
            ("vector_read_valid<=state==IDLE", "vector_read_valid<=!block_request && state==IDLE"),
            ("vector_read_mask<=state==IDLE", "vector_read_mask<=!block_request && state==IDLE"),
            ("host_error<=state==IDLE", "host_error<=!block_request && state==IDLE"),
            ('if(LANES<1 || LANES>64 || (LANES&(LANES-1))!=0)', 'if(LANES!=64)'),
            ('if(AW<1 || AW>16)', 'if(AW<5 || AW>16)'),
        ):
            text = replace_once(text, before, after)
    else:
        text = replace_once(text, "initial if(AW<1 || AW>16", "initial if(AW<5 || AW>16")
        text = replace_once(text, ENGINE+" #(", ENGINE_NEW+" #(")
        text = replace_once(text, "        .profile_begin,.profile_we,.profile_commit,.profile_size_log2,.profile_modulus,\n", """        .block_read_en,.block_write_en,.block_read_offset,.block_write_offset,
        .block_external_conflict(load_we || read_en || request || profile_request),
        .block_read_mask,.block_write_mask,.block_write_words,
        .block_read_valid,.block_error,.block_read_offset_out,.block_read_mask_out,.block_read_words,
        .profile_begin,.profile_we,.profile_commit,.profile_size_log2,.profile_modulus,
""")
        # Preserve raw arbitration intent even when parent adapter gating masks
        # a malformed vector, scalar or profile request before child forwarding.
    return "// PROVISIONAL A4 additive block-route derivative; exact parent diff guarded.\n"+text


def verify():
    result = {}
    for parent, new in ((ENGINE, ENGINE_NEW), (ADAPTER, ADAPTER_NEW)):
        path = ROOT/"rtl/kernel"/(new+".sv")
        wanted = expected(parent)
        if path.read_text() != wanted:
            raise ValueError("unguarded derivative edit: " + str(path))
        result[str(path.relative_to(ROOT))] = hashlib.sha256(wanted.encode()).hexdigest()
    return result
