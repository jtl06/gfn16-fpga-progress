// Four register stages, II=1, matching the frozen32-bit helper's ports/timing.
// Contract: canonical lhs,rhs<P; odd3<=P<2^27; Q=P^-1 modulo2^32.
// This is NOT a radix-digit converter. Full32-bit digits must first be reduced.
// Edge k input produces edge k+3 output; reset cancels pending transactions.
module genefer_montgomery_mul27_pipe #(
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697
) (
    input logic clk,rst_n,in_valid,
    input logic [31:0] lhs,rhs,
    output logic out_valid,
    output logic [31:0] result
);
    wire [26:0] lhs27=lhs[26:0],rhs27=rhs[26:0];
    logic [2:0] valid_pipe;
    logic [53:0] ab_s1;
    logic [31:0] m_s2,hi_s2,hi_s3;
    logic [58:0] mp_s3;
    wire [31:0] mp_hi={5'b0,mp_s3[58:32]};
    localparam logic [63:0] PQ=64'(P)*64'(Q);
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            valid_pipe<='0;out_valid<=0;result<='0;
            ab_s1<='0;m_s2<='0;hi_s2<='0;hi_s3<='0;mp_s3<='0;
        end else begin
            valid_pipe<={valid_pipe[1:0],in_valid};out_valid<=valid_pipe[2];
            if(in_valid)ab_s1<=lhs27*rhs27;
            if(valid_pipe[0])begin
                m_s2<=ab_s1[31:0]*Q;
                hi_s2<={10'b0,ab_s1[53:32]};
            end
            if(valid_pipe[1])begin
                mp_s3<=m_s2*P[26:0];hi_s3<=hi_s2;
            end
            if(valid_pipe[2])begin
                if(hi_s3>=mp_hi)result<=hi_s3-mp_hi;
                else result<=hi_s3+P-mp_hi;
            end
        end
    end
    // Assertions check the input contract; they are not a hardware converter.
    // synthesis translate_off
    initial begin
        if(P<3 || P>=32'd134217728 || !P[0])$fatal(1,"invalid27-bit Montgomery modulus");
        if(PQ[31:0]!=32'd1)$fatal(1,"invalid positive Montgomery inverse");
    end
    always @(posedge clk)if(rst_n && in_valid && (lhs>=P || rhs>=P))
        $fatal(1,"noncanonical Montgomery27 input");
    // synthesis translate_on
endmodule
