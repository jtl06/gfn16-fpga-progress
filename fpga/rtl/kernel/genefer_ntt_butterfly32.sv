// Radix-2 DIT butterfly in Montgomery representation:
// t = v*w*2^-32 mod P; y0 = u+t mod P; y1 = u-t mod P.
// Canonical inputs u,v,w < P, odd S3 prime P < 2^31.
// Five register stages, initiation interval one, no backpressure.
// Input sampled on edge k produces output after edge k+4.
// Reset cancels in-flight work; outputs hold on invalid cycles.
// Twiddle selection, addressing, inverse scaling and RAM are caller-owned.
module genefer_ntt_butterfly32 #(
    parameter logic [31:0] P = 32'd2130706433,
    parameter logic [31:0] Q = 32'd2164260865
) (
    input logic clk, rst_n, in_valid,
    input logic [31:0] u, v, w,
    output logic out_valid,
    output logic [31:0] y0, y1
);
    logic [31:0] u_pipe [0:3];
    logic product_valid;
    logic [31:0] product;
    logic [32:0] sum;
    logic [32:0] sum_reduced;

    genefer_montgomery_mul32_pipe #(.P(P), .Q(Q)) multiplier (
        .clk, .rst_n, .in_valid, .lhs(v), .rhs(w),
        .out_valid(product_valid), .result(product)
    );

    assign sum = {1'b0, u_pipe[3]} + {1'b0, product};
    assign sum_reduced = (sum >= {1'b0, P}) ? sum - {1'b0, P} : sum;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int i = 0; i < 4; i = i + 1) u_pipe[i] <= '0;
            out_valid <= 1'b0;
            y0 <= '0;
            y1 <= '0;
        end else begin
            u_pipe[0] <= u;
            for (int i = 1; i < 4; i = i + 1) u_pipe[i] <= u_pipe[i-1];
            out_valid <= product_valid;
            if (product_valid) begin
                y0 <= sum_reduced[31:0];
                y1 <= (u_pipe[3] >= product) ? u_pipe[3] - product
                                            : u_pipe[3] + P - product;
            end
        end
    end
endmodule
