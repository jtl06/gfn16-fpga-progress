module sdp_ram27_residue_equivalence #(parameter int AW=9, DEPTH=1<<AW) (
    input logic clk,rst_n,read_en,write_en,
    input logic [AW-1:0] read_addr,write_addr,
    input logic [31:0] write_data,
    output logic [31:0] wide_q,narrow_q
);
    genefer_sdp_ram32 #(.AW(AW),.DEPTH(DEPTH)) baseline (
        .clk,.rst_n,.read_en,.write_en,.read_addr,.write_addr,.write_data,.read_data(wide_q));
    genefer_sdp_ram27_residue #(.AW(AW),.DEPTH(DEPTH)) candidate (
        .clk,.rst_n,.read_en,.write_en,.read_addr,.write_addr,.write_data,.read_data(narrow_q));
endmodule
