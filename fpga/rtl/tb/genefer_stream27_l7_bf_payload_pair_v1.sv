// Native-only paired fixture. Both leaves use the same frozen factored REDC.
module genefer_stream27_l7_bf_payload_pair_v1 #(
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
) (
    input logic clk,rst_n,cancel,in_valid,gs,
    input logic [27:0] u,v,
    input logic [26:0] w,
    input logic [31:0] in_tag,
    output logic [1:0] out_valid,
    output logic [27:0] y0,y1,old_y0,old_y1,
    output logic [31:0] out_tag,old_out_tag
);
    wire local_rst_n=rst_n&&!cancel;
    genefer_stream27_lazy28_payload_free_v1 #(.P(P),.Q(Q)) candidate (
        .clk,.rst_n(local_rst_n),.in_valid,.gs,.u,.v,.w,.in_tag,
        .out_valid(out_valid[0]),.y0,.y1,.out_tag);
    genefer_stream27_lazy28_factored_parent_v1 #(.P(P),.Q(Q)) parent (
        .clk,.rst_n(local_rst_n),.in_valid,.gs,.u,.v,.w,.in_tag,
        .out_valid(out_valid[1]),.y0(old_y0),.y1(old_y1),.out_tag(old_out_tag));
endmodule
