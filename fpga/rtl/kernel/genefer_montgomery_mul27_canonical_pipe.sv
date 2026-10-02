// Isolated RTL-only candidate: explicitly zero-extended27-bit result, II=1.
// P1=1+2^26+2^25+2^22; P2=1+2^26+2^21; P3=1+2^26+2^17.
// Only those three moduli; canonical lhs,rhs<P.
// Since (P-1)^2 is divisible by 2^32, Q=P^-1=2-P (mod 2^32).
// Reduction uses explicit shifts/adds; the only variable product is 27x27.
// Same edge k -> edge k+3 output contract as the frozen generic helper.
module genefer_montgomery_mul27_canonical_pipe #(
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697
) (
    input logic clk,rst_n,in_valid,
    input logic [31:0] lhs,rhs,
    output logic out_valid,
    output logic [31:0] result
);
    localparam integer S=(P==32'd104857601)?25:
                         (P==32'd69206017)?21:17;
    wire [26:0] lhs27=lhs[26:0],rhs27=rhs[26:0];
    logic [2:0] valid_pipe;
    logic [53:0] ab_s1;
    logic [31:0] m_s2,hi_s2,hi_s3;
    logic [58:0] mp_s3;
    wire [31:0] lo=ab_s1[31:0];
    wire [58:0] m_ext={27'b0,m_s2};
    wire [31:0] extra_q=(P==32'd104857601)?(lo<<22):32'b0;
    wire [58:0] extra_p=(P==32'd104857601)?(m_ext<<22):59'b0;
    wire [31:0] mp_hi={5'b0,mp_s3[58:32]};
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            valid_pipe<='0;out_valid<=0;result<='0;
            ab_s1<='0;m_s2<='0;hi_s2<='0;hi_s3<='0;mp_s3<='0;
        end else begin
            valid_pipe<={valid_pipe[1:0],in_valid};out_valid<=valid_pipe[2];
            if(in_valid)ab_s1<=lhs27*rhs27;
            if(valid_pipe[0])begin
                m_s2<=lo-(lo<<26)-(lo<<S)-extra_q;
                hi_s2<={10'b0,ab_s1[53:32]};
            end
            if(valid_pipe[1])begin
                mp_s3<=m_ext+(m_ext<<26)+(m_ext<<S)+extra_p;hi_s3<=hi_s2;
            end
            if(valid_pipe[2])begin
                if(hi_s3>=mp_hi)result<={5'b0,27'(hi_s3-mp_hi)};
                else result<={5'b0,27'(hi_s3+P-mp_hi)};
            end
        end
    end
    // synthesis translate_off
    initial begin
        if(P!=32'd104857601 && P!=32'd69206017 && P!=32'd67239937)
            $fatal(1,"unsupported sparse Montgomery27 modulus");
        if(Q!=(32'd2-P))$fatal(1,"invalid sparse Montgomery inverse");
    end
    always @(posedge clk)if(rst_n && in_valid && (lhs>=P || rhs>=P))
        $fatal(1,"noncanonical Montgomery27 input");
    // synthesis translate_on
endmodule
