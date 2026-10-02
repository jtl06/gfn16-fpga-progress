// Simulation-only wrapper: all three S3 fields tested independently.
module genefer_arithmetic_top (
    input logic clk, rst_n,
    input logic [2:0] in_valid,
    input logic [31:0] a, b, w,
    output logic [2:0] baseline_valid, pipe_valid, butterfly_valid,
    output logic [31:0] baseline_result [0:2], pipe_result [0:2],
    output logic [31:0] y0 [0:2], y1 [0:2]
);
    localparam logic [31:0] PRIMES [0:2] = '{2130706433, 2113929217, 2013265921};
    localparam logic [31:0] INVERSES [0:2] = '{2164260865, 2181038081, 2281701377};
    for (genvar i = 0; i < 3; i = i + 1) begin : fields
        genefer_montgomery_mul32 #(.P(PRIMES[i]), .Q(INVERSES[i])) baseline (
            .clk, .rst_n, .in_valid(in_valid[i]), .lhs(a), .rhs(b),
            .out_valid(baseline_valid[i]), .result(baseline_result[i])
        );
        genefer_montgomery_mul32_pipe #(.P(PRIMES[i]), .Q(INVERSES[i])) pipelined (
            .clk, .rst_n, .in_valid(in_valid[i]), .lhs(a), .rhs(b),
            .out_valid(pipe_valid[i]), .result(pipe_result[i])
        );
        genefer_ntt_butterfly32 #(.P(PRIMES[i]), .Q(INVERSES[i])) butterfly (
            .clk, .rst_n, .in_valid(in_valid[i]), .u(a), .v(b), .w,
            .out_valid(butterfly_valid[i]), .y0(y0[i]), .y1(y1[i])
        );
    end
endmodule
