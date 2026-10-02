// Additive lazy-data candidate. Frozen canonical 27x27 helper is unchanged.
// lhs in [0,2P), rhs in [0,P); canonical output in [0,P).
// II=1, accepted edge k -> result edge k+3, asynchronous active-low reset.
// One explicit 27x27 product plus a high-bit correction. DSP mapping and the
// added first-stage adder's timing are UNMEASURED; no one-DSP claim is made.
module genefer_montgomery_mul28x27_sparse_pipe #(
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697
) (
    input logic clk,rst_n,in_valid,
    input logic [27:0] lhs,
    input logic [26:0] rhs,
    output logic out_valid,
    output logic [31:0] result
);
    localparam integer S=(P==32'd104857601)?25:
                         (P==32'd69206017)?21:17;
    logic [2:0] valid_pipe;
    logic [54:0] ab_s1;
    logic [31:0] m_s2,hi_s2,hi_s3;
    logic [58:0] mp_s3;
    wire [53:0] low_product=lhs[26:0]*rhs;
    wire [54:0] high_product=lhs[27] ? {1'b0,rhs,27'b0} : 55'b0;
    wire [54:0] full_product={1'b0,low_product}+high_product;
    wire [31:0] lo=ab_s1[31:0];
    wire [58:0] m_ext={27'b0,m_s2};
    wire [31:0] extra_q=(P==32'd104857601)?(lo<<22):32'b0;
    wire [58:0] extra_p=(P==32'd104857601)?(m_ext<<22):59'b0;
    wire [31:0] mp_hi={5'b0,mp_s3[58:32]};
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            valid_pipe<='0;out_valid<=0;result<='0;
            ab_s1<='0;m_s2<='0;hi_s2<='0;hi_s3<='0;mp_s3<='0;
        end else begin
            valid_pipe<={valid_pipe[1:0],in_valid};out_valid<=valid_pipe[2];
            if(in_valid) ab_s1<=full_product;
            if(valid_pipe[0]) begin
                m_s2<=lo-(lo<<26)-(lo<<S)-extra_q;
                hi_s2<={9'b0,ab_s1[54:32]};
            end
            if(valid_pipe[1]) begin
                mp_s3<=m_ext+(m_ext<<26)+(m_ext<<S)+extra_p;hi_s3<=hi_s2;
            end
            if(valid_pipe[2]) begin
                if(hi_s3>=mp_hi) result<=hi_s3-mp_hi;
                else result<=hi_s3+P-mp_hi;
            end
        end
    end
    // synthesis translate_off
    initial begin
        if(P!=32'd104857601 && P!=32'd69206017 && P!=32'd67239937)
            $fatal(1,"unsupported sparse Montgomery28x27 modulus");
        if(Q!=(32'd2-P)) $fatal(1,"invalid sparse Montgomery inverse");
    end
    always @(posedge clk) if(rst_n && in_valid &&
        ({4'b0,lhs}>=(P<<1) || {5'b0,rhs}>=P))
        $fatal(1,"Montgomery28x27 input range violation");
    // synthesis translate_on
endmodule
