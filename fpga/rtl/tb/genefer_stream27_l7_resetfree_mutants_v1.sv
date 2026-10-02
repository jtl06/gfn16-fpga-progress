// Deliberate bench-only faults. Good paired cells stay under strict checking.
module genefer_stream27_l7_resetfree_mutants_v1 #(
 parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
)(input logic clk,rst_n,cancel,in_valid,input logic [27:0] lhs,input logic [26:0] rhs,
 output logic [3:0] out_valid,output logic [31:0] lazy_result,canonical_result,old_lazy_result,old_canonical_result,
 output logic [4:0] bad_valid,output logic [159:0] bad_result);
 wire local_rst_n=rst_n && !cancel;
 genefer_stream27_l7_resetfree_pair_v1 #(.P(P),.Q(Q)) good (.*);
 genefer_stream27_l7_bad_pipe_reset_v1 #(.P(P),.Q(Q)) mutant0 (.clk,.rst_n(local_rst_n),.in_valid,.lhs,.rhs,.out_valid(bad_valid[0]),.result(bad_result[0*32+:32]));
 genefer_stream27_l7_bad_output_reset_v1 #(.P(P),.Q(Q)) mutant1 (.clk,.rst_n(local_rst_n),.in_valid,.lhs,.rhs,.out_valid(bad_valid[1]),.result(bad_result[1*32+:32]));
 genefer_stream27_l7_bad_invalid_hold_v1 #(.P(P),.Q(Q)) mutant2 (.clk,.rst_n(local_rst_n),.in_valid,.lhs,.rhs,.out_valid(bad_valid[2]),.result(bad_result[2*32+:32]));
 genefer_stream27_l7_bad_high_word_v1 #(.P(P),.Q(Q)) mutant3 (.clk,.rst_n(local_rst_n),.in_valid,.lhs,.rhs,.out_valid(bad_valid[3]),.result(bad_result[3*32+:32]));
 genefer_stream27_montgomery_factored_resetfree_core_v1 #(.P(P),.Q(Q)) mutant4 (
  .clk,.rst_n,.in_valid,.lhs,.rhs,.out_valid(bad_valid[4]),.result(bad_result[4*32+:32]));
endmodule
module genefer_stream27_l7_bad_pipe_reset_v1 #(
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
    logic [54:0] ab_s1;
    logic [31:0] m_s2;
    logic [22:0] hi_s2,hi_s3;
    logic carry_s2;
    logic [26:0] mp_hi_s3;
    wire [53:0] low_product=lhs[26:0]*rhs;
    wire [54:0] high_product=lhs[27] ? {1'b0,rhs,27'b0} : 55'b0;
    wire [54:0] full_product={1'b0,low_product}+high_product;
    wire [31:0] lo=ab_s1[31:0];
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
        if(!rst_n)begin out_valid<=0;end
        else begin
            valid_pipe<={valid_pipe[1:0],in_valid};out_valid<=valid_pipe[2];
        end
    end
    // Numeric payload deliberately retains arbitrary contents on reset.
    // Existing validity masks are the only publication/capture authority.
    always_ff @(posedge clk)begin
        if(rst_n)begin
            if(in_valid)ab_s1<=full_product;
            if(valid_pipe[0])begin
                m_s2<={m_high,lo[K-1:0]};hi_s2<=ab_s1[54:32];
                // m and lo have identical lowK bits, so the overflow compare is D bits.
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
module genefer_stream27_l7_bad_output_reset_v1 #(
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
    logic [54:0] ab_s1;
    logic [31:0] m_s2;
    logic [22:0] hi_s2,hi_s3;
    logic carry_s2;
    logic [26:0] mp_hi_s3;
    wire [53:0] low_product=lhs[26:0]*rhs;
    wire [54:0] high_product=lhs[27] ? {1'b0,rhs,27'b0} : 55'b0;
    wire [54:0] full_product={1'b0,low_product}+high_product;
    wire [31:0] lo=ab_s1[31:0];
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
        if(!rst_n)begin valid_pipe<=0;end
        else begin
            valid_pipe<={valid_pipe[1:0],in_valid};out_valid<=valid_pipe[2];
        end
    end
    // Numeric payload deliberately retains arbitrary contents on reset.
    // Existing validity masks are the only publication/capture authority.
    always_ff @(posedge clk)begin
        if(rst_n)begin
            if(in_valid)ab_s1<=full_product;
            if(valid_pipe[0])begin
                m_s2<={m_high,lo[K-1:0]};hi_s2<=ab_s1[54:32];
                // m and lo have identical lowK bits, so the overflow compare is D bits.
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
module genefer_stream27_l7_bad_invalid_hold_v1 #(
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
    logic [54:0] ab_s1;
    logic [31:0] m_s2;
    logic [22:0] hi_s2,hi_s3;
    logic carry_s2;
    logic [26:0] mp_hi_s3;
    wire [53:0] low_product=lhs[26:0]*rhs;
    wire [54:0] high_product=lhs[27] ? {1'b0,rhs,27'b0} : 55'b0;
    wire [54:0] full_product={1'b0,low_product}+high_product;
    wire [31:0] lo=ab_s1[31:0];
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
        if(!rst_n)begin valid_pipe<=0;out_valid<=0;end
        else begin
            valid_pipe<={valid_pipe[1:0],in_valid};out_valid<=valid_pipe[2];
        end
    end
    // Numeric payload deliberately retains arbitrary contents on reset.
    // Existing validity masks are the only publication/capture authority.
    always_ff @(posedge clk)begin
        if(rst_n)begin
            if(in_valid)ab_s1<=full_product;
            if(valid_pipe[0])begin
                m_s2<={m_high,lo[K-1:0]};hi_s2<=ab_s1[54:32];
                // m and lo have identical lowK bits, so the overflow compare is D bits.
                carry_s2<=lo[31:K]<m_high;
            end
            if(valid_pipe[1])begin
                mp_hi_s3<=high_term+27'(low_term[LB-1:D])+27'(carry_s2);
                hi_s3<=hi_s2;
            end
            if(1'b1)begin
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
module genefer_stream27_l7_bad_high_word_v1 #(
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
    logic [54:0] ab_s1;
    logic [31:0] m_s2;
    logic [22:0] hi_s2,hi_s3;
    logic carry_s2;
    logic [26:0] mp_hi_s3;
    wire [53:0] low_product=lhs[26:0]*rhs;
    wire [54:0] high_product=lhs[27] ? {1'b0,rhs,27'b0} : 55'b0;
    wire [54:0] full_product={1'b0,low_product}+high_product;
    wire [31:0] lo=ab_s1[31:0];
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
        if(!rst_n)begin valid_pipe<=0;out_valid<=0;end
        else begin
            valid_pipe<={valid_pipe[1:0],in_valid};out_valid<=valid_pipe[2];
        end
    end
    // Numeric payload deliberately retains arbitrary contents on reset.
    // Existing validity masks are the only publication/capture authority.
    always_ff @(posedge clk)begin
        if(rst_n)begin
            if(in_valid)ab_s1<=full_product;
            if(valid_pipe[0])begin
                m_s2<={m_high,lo[K-1:0]};hi_s2<=ab_s1[54:32];
                // m and lo have identical lowK bits, so the overflow compare is D bits.
                carry_s2<=lo[31:K]<m_high;
            end
            if(valid_pipe[1])begin
                mp_hi_s3<=high_term+27'(low_term[LB-1:D])+27'(carry_s2);
                hi_s3<=23'd0;
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
