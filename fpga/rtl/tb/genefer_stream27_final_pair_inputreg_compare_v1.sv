// Native-only paired old/new fixture. New E6, old E5; arithmetic identical.
module genefer_stream27_final_pair_inputreg_compare_v1 #(
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697,
    parameter logic [31:0] UPPER_SCALE=32'd1
) (
    input logic clk,rst_n,in_valid,
    input logic [31:0] u,v,normalized_lower_root,
    output logic old_valid,new_valid,old_error,new_error,
    output logic [31:0] old_y0,old_y1,new_y0,new_y1
);
    genefer_stream27_merged_final_gs_pair_v1 #(.P(P),.Q(Q),.UPPER_SCALE(UPPER_SCALE)) original (
        .clk,.rst_n,.in_valid,.u,.v,.normalized_lower_root,
        .out_valid(old_valid),.out_error(old_error),.y0(old_y0),.y1(old_y1));
    genefer_stream27_merged_final_gs_pair_inputreg_v1 #(.P(P),.Q(Q),.UPPER_SCALE(UPPER_SCALE)) registered_pair (
        .clk,.rst_n,.in_valid,.u,.v,.normalized_lower_root,
        .out_valid(new_valid),.out_error(new_error),.y0(new_y0),.y1(new_y1));
endmodule
