// SOURCE-ONLY wide final GS counterpart, not an adopted field profile.
// Lazy u/v<2P, normalized lower w<P, normalization=R^2/N<P, radix2^32.
// One lazy GS lower BF plus ONE parallel upper28x27 pipe; accepted k -> k+5.
// Both results canonical<P. No 28x28 square operation is provided.
module genefer_stream27_merged_final_gs_pair28_v1 #(
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697,
    parameter int TAG_W=32
) (
    input logic clk,rst_n,in_valid,
    input logic [27:0] u,v,
    input logic [26:0] normalized_w,normalization,
    input logic [TAG_W-1:0] in_tag,
    output logic out_valid,out_error,
    output logic [27:0] y0,y1,
    output logic [TAG_W-1:0] out_tag
);
    localparam logic [28:0] TWO_P=29'(P)<<1;
    wire [28:0] upper_sum={1'b0,u}+{1'b0,v};
    // u+v<4P. One29-bit fold2P gives a legal28x27 lhs in [0,2P).
    wire [27:0] upper_fold=28'(upper_sum>=TWO_P ? upper_sum-TWO_P : upper_sum);
    logic lower_valid,upper_valid;
    logic [27:0] unused_upper,lower_result;
    logic [31:0] upper_product,upper_delay[0:1];
    logic [1:0] upper_valid_delay;
    logic [TAG_W-1:0] lower_tag;
    genefer_ntt_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(TAG_W)) lower (
        .clk,.rst_n,.in_valid,.gs(1'b1),.u,.v,.w(normalized_w),.in_tag,
        .out_valid(lower_valid),.y0(unused_upper),.y1(lower_result),.out_tag(lower_tag)
    );
    genefer_montgomery_mul28x27_sparse_pipe_v2 #(.P(P),.Q(Q)) upper_normalizer (
        .clk,.rst_n,.in_valid,.lhs(upper_fold),.rhs(normalization),
        .out_valid(upper_valid),.result(upper_product)
    );
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin upper_valid_delay<=0;out_error<=0;end
        else begin
            upper_valid_delay<={upper_valid_delay[0],upper_valid};
            out_error<=lower_valid!=upper_valid_delay[1];
        end
    end
    always_ff @(posedge clk)begin
        if(rst_n && upper_valid)upper_delay[0]<=upper_product;
        if(rst_n && upper_valid_delay[0])upper_delay[1]<=upper_delay[0];
    end
    assign out_valid=lower_valid && upper_valid_delay[1];
    assign y0={1'b0,upper_delay[1][26:0]};
    assign y1=lower_result;
    assign out_tag=lower_tag;
    // synthesis translate_off
    always @(posedge clk)if(rst_n)begin
        if(in_valid && ({1'b0,u}>=TWO_P || {1'b0,v}>=TWO_P ||
                       {5'b0,normalized_w}>=P || {5'b0,normalization}>=P))
            $fatal(1,"MERGED_FINAL_GS28_DOMAIN");
        if(out_valid && ({4'b0,y0}>=P || {4'b0,y1}>=P))
            $fatal(1,"MERGED_FINAL_GS28_CANONICAL_OUTPUT");
    end
    // synthesis translate_on
endmodule
