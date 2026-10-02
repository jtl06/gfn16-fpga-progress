// One shared parent CT/GS BF, plus ONE upper normalization pipe per lane.
// Canonical u,v,w<P only. The final GS lower twiddle already contains R^2/N.
// Accepted edge k -> k+5, II1. Upper sum/rhs launch replaces one output alignment stage.
module genefer_a10_canonical_butterfly_sumlaunch_v2 #(
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
) (
    input logic clk,rst_n,in_valid,gs,normalize_upper,
    input logic [31:0] u,v,w,normalization,
    output logic out_valid,out_error,
    output logic [31:0] y0,y1
);
    logic [32:0] sum;
    logic [31:0] reduced_sum,lower0,lower1,upper_product;
    logic lower_valid,upper_valid;
    logic [5:0] norm_pipe;
    logic upper_launch_valid,upper_valid_delay;
    (* preserve,dont_merge *) logic [31:0] upper_sum_launch,upper_norm_launch;
    logic [31:0] upper_delay;
    assign sum={1'b0,u}+{1'b0,v};
    assign reduced_sum=sum>=33'(P) ? 32'(sum-33'(P)) : sum[31:0];
    genefer_ntt_difdit_butterfly27 #(.P(P),.Q(Q)) shared_lower (
        .clk,.rst_n,.in_valid,.dif(gs),.u,.v,.w,
        .out_valid(lower_valid),.y0(lower0),.y1(lower1)
    );
    genefer_montgomery_mul27_sparse_pipe #(.P(P),.Q(Q)) upper_normalizer (
        .clk,.rst_n,.in_valid(upper_launch_valid),
        .lhs(upper_sum_launch),.rhs(upper_norm_launch),.out_valid(upper_valid),.result(upper_product)
    );
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin norm_pipe<=0;upper_launch_valid<=0;upper_valid_delay<=0;out_error<=0;end
        else begin
            norm_pipe<={norm_pipe[4:0],in_valid && normalize_upper};
            upper_launch_valid<=in_valid && normalize_upper;
            upper_valid_delay<=upper_valid;
            out_error<=(in_valid && normalize_upper && !gs) ||
                (norm_pipe[5] && (lower_valid!=upper_valid_delay));
        end
    end
    // No reset of multiplier payloads; eligibility/tag registers own validity.
    always_ff @(posedge clk)begin
        if(rst_n && in_valid && normalize_upper)begin
            upper_sum_launch<=reduced_sum;upper_norm_launch<=normalization;
        end
        if(rst_n && upper_valid)upper_delay<=upper_product;
    end
    assign out_valid=lower_valid && (!norm_pipe[5] || upper_valid_delay);
    assign y0=norm_pipe[5] ? upper_delay : lower0;
    assign y1=lower1;
    // synthesis translate_off
    always @(posedge clk)if(rst_n && in_valid)begin
        if(u>=P || v>=P || w>=P || (normalize_upper && normalization>=P))
            $fatal(1,"A10_CANONICAL_BF_DOMAIN");
        if(normalize_upper && !gs)$fatal(1,"A10_FINAL_NORMALIZATION_FORM");
    end
    // synthesis translate_on
endmodule
