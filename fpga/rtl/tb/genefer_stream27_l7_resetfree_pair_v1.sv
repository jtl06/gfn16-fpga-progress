// Native fixture only. Full-clock cancel asserts both leaf resets immediately.
module genefer_stream27_l7_resetfree_pair_v1 #(
 parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
)(input logic clk,rst_n,cancel,in_valid,
 input logic [27:0] lhs,input logic [26:0] rhs,
 output logic [3:0] out_valid,
 output logic [31:0] lazy_result,canonical_result,old_lazy_result,old_canonical_result);
 wire local_rst_n=rst_n && !cancel;
 wire [31:0] x={4'b0,lhs},y={5'b0,rhs};
 wire [31:0] canonical_lhs=x>=P ? x-P : x;
 genefer_stream27_montgomery28x27_factored_resetfree_v1 #(.P(P),.Q(Q)) lazy_new(
  .clk,.rst_n(local_rst_n),.in_valid,.lhs,.rhs,.out_valid(out_valid[0]),.result(lazy_result));
 genefer_stream27_montgomery_factored_resetfree_v1 #(.P(P),.Q(Q)) canonical_new(
  .clk,.rst_n(local_rst_n),.in_valid,.lhs(canonical_lhs),.rhs(y),.out_valid(out_valid[1]),.result(canonical_result));
 genefer_stream27_montgomery28x27_factored_v1 #(.P(P),.Q(Q)) lazy_old(
  .clk,.rst_n(local_rst_n),.in_valid,.lhs,.rhs,.out_valid(out_valid[2]),.result(old_lazy_result));
 genefer_stream27_montgomery_factored_v1 #(.P(P),.Q(Q)) canonical_old(
  .clk,.rst_n(local_rst_n),.in_valid,.lhs(canonical_lhs),.rhs(y),.out_valid(out_valid[3]),.result(old_canonical_result));
endmodule
