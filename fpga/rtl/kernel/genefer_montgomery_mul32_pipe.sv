// Four register stages, initiation interval one; no backpressure.
// Accept canonical residues lhs,rhs < P. P is an odd S3 prime < 2^31,
// Q = P^-1 modulo 2^32 (positive inverse, matching Genefer).
// Input sampled on edge k produces output after edge k+3.
// Reset cancels all pending transactions; result holds during invalid cycles.
module genefer_montgomery_mul32_pipe #(
    parameter logic [31:0] P = 32'd2130706433,
    parameter logic [31:0] Q = 32'd2164260865
) (
    input logic clk, rst_n, in_valid,
    input logic [31:0] lhs, rhs,
    output logic out_valid,
    output logic [31:0] result
);
    logic [2:0] valid_pipe;
    logic [63:0] ab_s1;
    logic [31:0] m_s2, hi_s2, hi_s3;
    logic [63:0] mp_s3;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_pipe <= '0;
            out_valid <= 1'b0;
            ab_s1 <= '0;
            m_s2 <= '0;
            hi_s2 <= '0;
            hi_s3 <= '0;
            mp_s3 <= '0;
            result <= '0;
        end else begin
            valid_pipe <= {valid_pipe[1:0], in_valid};
            out_valid <= valid_pipe[2];
            if (in_valid) ab_s1 <= {32'b0, lhs} * {32'b0, rhs};
            if (valid_pipe[0]) begin
                // Only the low 32 bits are needed here (arithmetic mod 2^32).
                m_s2 <= ab_s1[31:0] * Q;
                hi_s2 <= ab_s1[63:32];
            end
            if (valid_pipe[1]) begin
                mp_s3 <= {32'b0, m_s2} * {32'b0, P};
                hi_s3 <= hi_s2;
            end
            if (valid_pipe[2]) begin
                if (hi_s3 >= mp_s3[63:32])
                    result <= hi_s3 - mp_s3[63:32];
                else
                    result <= hi_s3 + P - mp_s3[63:32];
            end
        end
    end
endmodule
