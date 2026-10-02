// Arithmetic baseline only. No board-specific I/O, clock-generation, or
// programming logic.
// Implements the Montgomery convention in genefer22 ocl/kernel.cl::mulmod.
module genefer_montgomery_mul32 #(
    parameter logic [31:0] P = 32'd2130706433,
    parameter logic [31:0] Q = 32'd2164260865
) (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        in_valid,
    input  logic [31:0] lhs,
    input  logic [31:0] rhs,
    output logic        out_valid,
    output logic [31:0] result
);
    logic [63:0] ab_product;
    logic [63:0] lo_q_product;
    logic [63:0] m_p_product;
    logic [31:0] reduced;

    always_comb begin
        // Explicit extensions avoid context-dependent Verilog multiply widths.
        ab_product   = {32'b0, lhs} * {32'b0, rhs};
        lo_q_product = {32'b0, ab_product[31:0]} * {32'b0, Q};
        m_p_product  = {32'b0, lo_q_product[31:0]} * {32'b0, P};

        if (ab_product[63:32] >= m_p_product[63:32]) begin
            reduced = ab_product[63:32] - m_p_product[63:32];
        end else begin
            reduced = ab_product[63:32] + P - m_p_product[63:32];
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_valid <= 1'b0;
            result    <= 32'b0;
        end else begin
            out_valid <= in_valid;
            if (in_valid) begin
                result <= reduced;
            end
        end
    end

endmodule
