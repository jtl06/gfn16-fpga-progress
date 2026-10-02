// Isolated old/new canonical butterfly pair; no engine/root/profile changes.
// Both actual cells consume the same request on k and must publish on k+5.
module genefer_a10_upper_sum_pair_v2 #(
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
) (
    input logic clk,rst_n,in_valid,gs,normalize_upper,
    input logic [31:0] u,v,w,normalization,
    output logic out_valid,out_error,
    output logic [31:0] y0,y1,
    output logic old_valid,old_error,
    output logic [31:0] old_y0,old_y1
);
    genefer_a10_canonical_butterfly_v1 #(.P(P),.Q(Q)) original (
        .clk,.rst_n,.in_valid,.gs,.normalize_upper,.u,.v,.w,.normalization,
        .out_valid(old_valid),.out_error(old_error),.y0(old_y0),.y1(old_y1)
    );
    genefer_a10_canonical_butterfly_sumlaunch_v2 #(.P(P),.Q(Q)) successor (
        .clk,.rst_n,.in_valid,.gs,.normalize_upper,.u,.v,.w,.normalization,
        .out_valid,.out_error,.y0,.y1
    );
endmodule
