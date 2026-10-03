// Source-only canonical final GS pair, accepted k -> both outputs k+5.
// Existing BF supplies normalized lower output. Parallel upper normalization
// is k+3 then two registers; do not leave y0 unscaled or count this pipe free.
// Upper/lower sum inputs must be canonical<P, NOT the proposed lazy [0,2P).
module genefer_stream27_merged_final_gs_pair_v1 #(
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697,
    parameter logic [31:0] UPPER_SCALE=32'd1
) (
    input logic clk,rst_n,in_valid,
    input logic [31:0] u,v,normalized_lower_root,
    output logic out_valid,out_error,
    output logic [31:0] y0,y1
);
    wire [31:0] sum=u+v;
    wire [31:0] sum_reduced=sum>=P ? sum-P : sum;
    wire lower_valid,upper_valid;
    wire [31:0] unused_upper,lower,upper_normalized;
    logic [31:0] upper_delay[0:1];
    logic [1:0] upper_valid_delay;
    genefer_ntt_difdit_butterfly27 #(.P(P),.Q(Q)) lower_pipeline (
        .clk,.rst_n,.in_valid,.dif(1'b1),.u,.v,.w(normalized_lower_root),
        .out_valid(lower_valid),.y0(unused_upper),.y1(lower));
    genefer_stream27_montgomery_factored_v1 #(.P(P),.Q(Q)) upper_pipeline (
        .clk,.rst_n,.in_valid,.lhs(sum_reduced),.rhs(UPPER_SCALE),
        .out_valid(upper_valid),.result(upper_normalized));
    assign out_valid=lower_valid && upper_valid_delay[1] && !out_error;
    assign y0=upper_delay[1];assign y1=lower;
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            upper_valid_delay<=0;out_error<=0;
        end else begin
            upper_valid_delay<={upper_valid_delay[0],upper_valid};
            if(upper_valid)upper_delay[0]<=upper_normalized;
            if(upper_valid_delay[0])upper_delay[1]<=upper_delay[0];
            if(lower_valid!=upper_valid_delay[1])out_error<=1;
        end
    end
    // synthesis translate_off
    initial if(UPPER_SCALE>=P)$fatal(1,"S_M2_NORMALIZATION_SCALE_RANGE");
    always @(posedge clk)if(rst_n && in_valid && (u>=P || v>=P || normalized_lower_root>=P))
        $fatal(1,"S_M2_FINAL_GS_CANONICAL_INPUT_REQUIRED");
    // synthesis translate_on
endmodule
