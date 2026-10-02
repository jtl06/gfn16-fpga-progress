// Additive scalar lazy butterfly, not an adopted engine arithmetic profile.
// u,v in [0,2P), w in [0,P); gs=0 CT, gs=1 GS. Both y in [0,2P).
// Accepted edge k -> output edge k+5, II=1, matching the frozen butterfly.
// No lazy28 x lazy28 pointwise operation is admitted by this cell.
module genefer_stream27_factored_lazy28_butterfly_v1 #(
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697,
    parameter int TAG_W=32
) (
    input logic clk,rst_n,in_valid,gs,
    input logic [27:0] u,v,
    input logic [26:0] w,
    input logic [TAG_W-1:0] in_tag,
    output logic out_valid,
    output logic [27:0] y0,y1,
    output logic [TAG_W-1:0] out_tag
);
    localparam logic [28:0] TWO_P=29'(P)<<1;
    logic pre_valid,product_valid;
    logic [27:0] pre_v;
    logic [26:0] pre_w;
    logic [31:0] product;
    logic [27:0] prefix_pipe[0:4];
    logic [TAG_W-1:0] tag_pipe[0:4];
    logic [4:0] gs_pipe;
    wire [27:0] ct_u=u>=28'(P) ? u-28'(P) : u;
    wire [28:0] gs_sum={1'b0,u}+{1'b0,v};
    wire [28:0] gs_diff={1'b0,u}+TWO_P-{1'b0,v};
    wire [27:0] gs_sum_fold=28'(gs_sum>=TWO_P ? gs_sum-TWO_P : gs_sum);
    wire [27:0] gs_diff_fold=28'(gs_diff>=TWO_P ? gs_diff-TWO_P : gs_diff);
    wire [27:0] canonical_product={1'b0,product[26:0]};
    genefer_stream27_montgomery28x27_factored_v1 #(.P(P),.Q(Q)) multiplier (
        .clk,.rst_n,.in_valid(pre_valid),.lhs(pre_v),.rhs(pre_w),
        .out_valid(product_valid),.result(product)
    );
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            pre_valid<=0;pre_v<=0;pre_w<=0;gs_pipe<=0;
            out_valid<=0;y0<=0;y1<=0;out_tag<=0;
            for(int k=0;k<5;k=k+1)begin prefix_pipe[k]<=0;tag_pipe[k]<=0;end
        end else begin
            // Assertions stay inside the non-reset branch; no combinational
            // fault signal fans out into valid or datapath enables.
            // synthesis translate_off
            if(in_valid && ({1'b0,u}>=TWO_P || {1'b0,v}>=TWO_P || {5'b0,w}>=P))
                $fatal(1,"Lazy28 butterfly input range violation");
            if(product_valid && product>=P)
                $fatal(1,"Lazy28 butterfly multiplier range violation");
            // synthesis translate_on
            pre_valid<=in_valid;
            if(in_valid)begin pre_v<=gs ? gs_diff_fold : v;pre_w<=w;end
            prefix_pipe[0]<=gs ? gs_sum_fold : ct_u;
            tag_pipe[0]<=in_tag;
            for(int k=1;k<5;k=k+1)begin
                prefix_pipe[k]<=prefix_pipe[k-1];tag_pipe[k]<=tag_pipe[k-1];
            end
            gs_pipe<={gs_pipe[3:0],gs};out_valid<=product_valid;
            if(product_valid)begin
                y0<=gs_pipe[4] ? prefix_pipe[4] : prefix_pipe[4]+canonical_product;
                y1<=gs_pipe[4] ? canonical_product : prefix_pipe[4]+28'(P)-canonical_product;
                out_tag<=tag_pipe[4];
            end
        end
    end
    // synthesis translate_off
    initial if(TAG_W<1)$fatal(1,"Invalid lazy28 butterfly tag width");
    // synthesis translate_on
endmodule
