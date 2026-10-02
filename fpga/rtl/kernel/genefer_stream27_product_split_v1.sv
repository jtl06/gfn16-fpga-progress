// Isolated product-register experiment. R=2^32, E0 -> E3, II=1 unchanged.
// Direct 27x27 product FF may map into the DSP. Mapping/area are not assumed.
module genefer_stream27_product_split_core_v1 #(
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697
) (
    input logic clk,rst_n,in_valid,
    input logic [27:0] lhs,
    input logic [26:0] rhs,
    output logic out_valid,
    output logic [31:0] result
);
    localparam int K=P==32'd104857601 ? 22 : P==32'd69206017 ? 21 : 17;
    localparam int D=32-K,CW=P==32'd104857601 ? 5 : P==32'd69206017 ? 6 : 10;
    localparam int LB=D+CW,SHIFT=P==32'd69206017 ? 5 : 9;
    logic [2:0] valid_pipe;
    logic [53:0] product_s1;
    logic [26:0] high_rhs_s1;
    logic [31:0] m_s2;
    logic [22:0] hi_s2,hi_s3;
    logic carry_s2;
    logic [26:0] mp_hi_s3;
    wire [53:0] low_product=lhs[26:0]*rhs;
    // Only five overlapping low bits; carry crosses the 32-bit boundary.
    wire [5:0] overlap_sum={1'b0,product_s1[31:27]}+{1'b0,high_rhs_s1[4:0]};
    wire [31:0] lo={overlap_sum[4:0],product_s1[26:0]};
    wire [22:0] reconstructed_hi={1'b0,product_s1[53:32]}+
        {1'b0,high_rhs_s1[26:5]}+23'(overlap_sum[5]);
    wire [D-1:0] lo_d=lo[D-1:0];
    wire [D-1:0] lo_coeff,m_high;
    wire [26:0] a={{(27-K){1'b0}},m_s2[31:D]};
    wire [LB-1:0] b={{CW{1'b0}},m_s2[D-1:0]};
    wire [26:0] high_term;
    wire [LB-1:0] low_term;
    if(P==32'd104857601)begin: coefficient25
        assign lo_coeff=lo_d+(lo_d<<3)+(lo_d<<4);
        assign high_term=a+(a<<3)+(a<<4);
        assign low_term=b+(b<<3)+(b<<4);
    end else begin: coefficient_two_terms
        assign lo_coeff=lo_d+(lo_d<<SHIFT);
        assign high_term=a+(a<<SHIFT);
        assign low_term=b+(b<<SHIFT);
    end
    assign m_high=lo[31:K]-lo_coeff;
    wire [31:0] t_hi={9'b0,hi_s3},mp_hi={5'b0,mp_hi_s3};
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            valid_pipe<=0;out_valid<=0;result<=0;
            product_s1<=0;high_rhs_s1<=0;m_s2<=0;hi_s2<=0;hi_s3<=0;carry_s2<=0;mp_hi_s3<=0;
        end else begin
            valid_pipe<={valid_pipe[1:0],in_valid};out_valid<=valid_pipe[2];
            if(in_valid)begin
                product_s1<=low_product;
                high_rhs_s1<=lhs[27] ? rhs : 27'b0;
            end
            if(valid_pipe[0])begin
                m_s2<={m_high,lo[K-1:0]};hi_s2<=reconstructed_hi;
                // Same exact overflow compare as the factored parent.
                carry_s2<=lo[31:K]<m_high;
            end
            if(valid_pipe[1])begin
                mp_hi_s3<=high_term+27'(low_term[LB-1:D])+27'(carry_s2);
                hi_s3<=hi_s2;
            end
            if(valid_pipe[2])begin
                if(t_hi>=mp_hi)result<=t_hi-mp_hi;
                else result<=t_hi+P-mp_hi;
            end
        end
    end
    // synthesis translate_off
    initial begin
        if(P!=32'd104857601 && P!=32'd69206017 && P!=32'd67239937)$fatal(1,"L3_UNSUPPORTED_FIELD");
        if(Q!=(32'd2-P))$fatal(1,"L3_INVERSE");
    end
    always @(posedge clk)if(rst_n && in_valid && ({4'b0,lhs}>=(P<<1) || {5'b0,rhs}>=P))
        $fatal(1,"L3_LAZY_RANGE");
    // synthesis translate_on
endmodule

module genefer_stream27_product_split_v1 #(
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697
) (
    input logic clk,rst_n,in_valid,
    input logic [31:0] lhs,rhs,
    output logic out_valid,
    output logic [31:0] result
);
    genefer_stream27_product_split_core_v1 #(.P(P),.Q(Q)) core (
        .clk,.rst_n,.in_valid,.lhs({1'b0,lhs[26:0]}),.rhs(rhs[26:0]),.out_valid,.result);
    // synthesis translate_off
    always @(posedge clk)if(rst_n && in_valid && (lhs>=P || rhs>=P))$fatal(1,"L3_CANONICAL_RANGE");
    // synthesis translate_on
endmodule

module genefer_stream27_product_split_lazy_v1 #(
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697
) (
    input logic clk,rst_n,in_valid,
    input logic [27:0] lhs,
    input logic [26:0] rhs,
    output logic out_valid,
    output logic [31:0] result
);
    genefer_stream27_product_split_core_v1 #(.P(P),.Q(Q)) core (
        .clk,.rst_n,.in_valid,.lhs,.rhs,.out_valid,.result);
endmodule
