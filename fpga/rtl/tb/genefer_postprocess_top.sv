// Test wrapper. Host orchestrates CRT transfers into carry memory.
module genefer_postprocess_top (
    input logic clk, rst_n, crt_valid,
    input logic [31:0] r1,r2,r3,
    output logic crt_ready, coefficient_valid,
    output logic signed [95:0] coefficient,
    input logic load_we, read_en, start,
    input logic [15:0] host_addr,
    input logic signed [95:0] write_data,
    input logic [4:0] size_log2,
    input logic [31:0] base,
    output logic read_valid,
    output logic signed [95:0] read_data,
    output logic busy, done, error,
    output logic [63:0] cycles,
    output logic [6:0] passes
);
    genefer_crt3 crt(.clk,.rst_n,.in_valid(crt_valid),.r1,.r2,.r3,
        .ready(crt_ready),.out_valid(coefficient_valid),.coefficient);
    genefer_carry carry_unit(.clk,.rst_n,.load_we,.read_en,.start,.host_addr,
        .write_data,.size_log2,.base,.read_valid,.read_data,.busy,.done,.error,.cycles,.passes);
endmodule
