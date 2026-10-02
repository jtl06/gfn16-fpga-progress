// Source-only minimal route/RAM native probe. Full engine comparison separate.
module track_a4_blockroute_probe_v2 #(parameter int AW=5) (
    input logic clk,rst_n,enable,read_en,write_en,
    input logic [AW-1:0] read_offset,write_offset,
    input logic [15:0] read_mask,write_mask,
    input logic [511:0] write_words,
    output logic request,error,read_valid,
    output logic [AW-1:0] read_offset_out,
    output logic [15:0] read_mask_out,
    output logic [511:0] read_words
);
    localparam int RW=AW>7 ? AW-7 : 1;
    localparam int DEPTH=1<<(AW>7 ? AW-7 : 0);
    logic [31:0] ram_q[0:127],ram_w[0:127];
    logic [127:0] ram_re,ram_we;
    logic [RW-1:0] ram_ra[0:127],ram_wa[0:127];
    genefer_track_a4_blockroute_v2 #(.AW(AW),.RW(RW)) route (.*);
    for(genvar bank=0;bank<128;bank=bank+1)begin: banks
        genefer_sdp_ram32 #(.AW(RW),.DEPTH(DEPTH)) ram (
            .clk,.rst_n,.read_en(ram_re[bank]),.write_en(ram_we[bank]),
            .read_addr(ram_ra[bank]),.write_addr(ram_wa[bank]),
            .write_data(ram_w[bank]),.read_data(ram_q[bank])
        );
    end
endmodule
