// Signed raw REDC, private to fused butterfly; NOT a drop-in normalized leaf.
// L3 isolated subtractive REDC, unchanged R=2^32 and accepted k -> k+3/II1.
// P=1+C*2^K. Only one variable27x27 product; lazy bit27 correction stays outside.
// Resource/timing benefit is unmeasured. No changed roots or new lazy range.
module genefer_stream27_montgomery28x27_raw_pipe_v1 #(
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697
) (
    input logic clk,rst_n,in_valid,
    input logic [27:0] lhs,
    input logic [26:0] rhs,
    output logic out_valid,
    output logic signed [27:0] result_raw
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
    
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            valid_pipe<=0;out_valid<=0;result_raw<=0;
            ab_s1<=0;m_s2<=0;hi_s2<=0;hi_s3<=0;carry_s2<=0;mp_hi_s3<=0;
        end else begin
            valid_pipe<={valid_pipe[1:0],in_valid};out_valid<=valid_pipe[2];
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
                result_raw<=$signed({5'b0,hi_s3})-$signed({1'b0,mp_hi_s3});
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

// P5/L3b: public lazy unsigned28, private signed28 raw Montgomery residue.
// E0->E5, II1. ModP residues preserved; internal representatives may differ byP.
module genefer_stream27_fused_lazy28_butterfly_v1 #(
 parameter logic [31:0] P=32'd104857601,Q=32'd4190109697,parameter int TAG_W=32
)(input logic clk,rst_n,in_valid,gs,input logic [27:0] u,v,input logic [26:0] w,
 input logic [TAG_W-1:0] in_tag,output logic out_valid,output logic [27:0] y0,y1,
 output logic [TAG_W-1:0] out_tag);
 localparam logic [28:0] TWO_P=29'(P)<<1;
 localparam logic signed [28:0] P29=$signed({2'b0,P[26:0]});
 localparam logic signed [29:0] P30=$signed({3'b0,P[26:0]}),TWO_P30=P30<<<1;
 logic pre_valid,product_valid;
 logic [27:0] pre_v,prefix_pipe[0:4];logic [26:0] pre_w;
 logic signed [27:0] product_raw;
 logic [TAG_W-1:0] tag_pipe[0:4];logic [4:0] gs_pipe;
 wire [27:0] ct_u=u>=28'(P) ? u-28'(P) : u;
 wire [28:0] gs_sum={1'b0,u}+{1'b0,v},gs_diff={1'b0,u}+TWO_P-{1'b0,v};
 wire [27:0] gs_sum_fold=28'(gs_sum>=TWO_P ? gs_sum-TWO_P : gs_sum);
 wire [27:0] gs_diff_fold=28'(gs_diff>=TWO_P ? gs_diff-TWO_P : gs_diff);
 wire signed [28:0] raw29=$signed({product_raw[27],product_raw});
 wire signed [29:0] ct_total=$signed({2'b0,prefix_pipe[4]})+$signed({{2{product_raw[27]}},product_raw})+P30;
 wire signed [28:0] ct_diff=$signed({1'b0,prefix_pipe[4]})-raw29;
 wire signed [28:0] gs_biased=raw29+P29;
 genefer_stream27_montgomery28x27_raw_pipe_v1 #(.P(P),.Q(Q)) multiplier(
  .clk,.rst_n,.in_valid(pre_valid),.lhs(pre_v),.rhs(pre_w),.out_valid(product_valid),.result_raw(product_raw));
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   pre_valid<=0;pre_v<=0;pre_w<=0;gs_pipe<=0;out_valid<=0;y0<=0;y1<=0;out_tag<=0;
   for(int k=0;k<5;k=k+1)begin prefix_pipe[k]<=0;tag_pipe[k]<=0;end
  end else begin
   // synthesis translate_off
   if(in_valid && ({1'b0,u}>=TWO_P || {1'b0,v}>=TWO_P || {5'b0,w}>=P))$fatal(1,"P5_BFLY_INPUT_RANGE");
   if(product_valid && (raw29<=-P29 || raw29>=P29))$fatal(1,"P5_RAW_RESULT_RANGE");
   // synthesis translate_on
   pre_valid<=in_valid;
   if(in_valid)begin pre_v<=gs ? gs_diff_fold : v;pre_w<=w;end
   prefix_pipe[0]<=gs ? gs_sum_fold : ct_u;tag_pipe[0]<=in_tag;
   for(int k=1;k<5;k=k+1)begin prefix_pipe[k]<=prefix_pipe[k-1];tag_pipe[k]<=tag_pipe[k-1];end
   gs_pipe<={gs_pipe[3:0],gs};out_valid<=product_valid;
   if(product_valid)begin
    y0<=gs_pipe[4] ? prefix_pipe[4] : 28'(ct_total>=TWO_P30 ? ct_total-P30 : ct_total);
    y1<=gs_pipe[4] ? 28'(gs_biased) : 28'(ct_diff<0 ? ct_diff+P29 : ct_diff);
    out_tag<=tag_pipe[4];
   end
  end
 end
 // synthesis translate_off
 initial if(TAG_W<1)$fatal(1,"P5_TAG_WIDTH");
 // synthesis translate_on
endmodule
