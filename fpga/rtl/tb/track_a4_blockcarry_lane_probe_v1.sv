// Provisional native harness, explicit AW5/AW8 independent builds required.
module track_a4_blockcarry_lane_probe_v1 #(parameter int AW=5) (
    input logic clk,rst_n,begin_block,in_valid,block_start,block_end,
    input logic [31:0] base,
    input logic [95:0] reciprocal,
    input logic [76:0] coefficient_limit,
    input logic signed [95:0] coefficient,
    input logic [AW-1:0] offset,
    output logic busy,done,error,
    output logic [3:0] error_code,
    output logic digit_valid,
    output logic [31:0] digit,
    output logic [AW-1:0] digit_offset,
    output logic boundary_valid,
    output logic [31:0] boundary_low,
    output logic signed [31:0] boundary_high
);
    genefer_track_a4_blockcarry_lane_v1 #(.AW(AW)) lane (.*);
endmodule
