// Sizing-only wrapper: independent operand/valid ports forbid product sharing.
// Input FF adds one wrapper edge, NOT a change to the k->k+3 leaf ABI.
module genefer_stream27_l3_factored_probe_v1 #(
 parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
)(input logic clk,rst_n,input logic [3:0] in_valid,
 input logic [127:0] lhs,rhs,
 output logic [3:0] out_valid,output logic [127:0] result);
 logic [127:0] lhs_q,rhs_q;
 logic [3:0] valid_q;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin lhs_q<=0;rhs_q<=0;valid_q<=0;end
  else begin lhs_q<=lhs;rhs_q<=rhs;valid_q<=in_valid;end
 end
 genefer_stream27_montgomery_factored_v1 #(.P(P),.Q(Q)) new_canonical(
  .clk,.rst_n,.in_valid(valid_q[0]),.lhs(lhs_q[0+:32]),.rhs(rhs_q[0+:32]),.out_valid(out_valid[0]),.result(result[0+:32]));
 genefer_montgomery_mul27_sparse_pipe #(.P(P),.Q(Q)) frozen_canonical(
  .clk,.rst_n,.in_valid(valid_q[1]),.lhs(lhs_q[32+:32]),.rhs(rhs_q[32+:32]),.out_valid(out_valid[1]),.result(result[32+:32]));
 genefer_stream27_montgomery28x27_factored_v1 #(.P(P),.Q(Q)) new_lazy(
  .clk,.rst_n,.in_valid(valid_q[2]),.lhs(lhs_q[64+:28]),.rhs(rhs_q[64+:27]),.out_valid(out_valid[2]),.result(result[64+:32]));
 genefer_montgomery_mul28x27_sparse_pipe_v2 #(.P(P),.Q(Q)) frozen_lazy(
  .clk,.rst_n,.in_valid(valid_q[3]),.lhs(lhs_q[96+:28]),.rhs(rhs_q[96+:27]),.out_valid(out_valid[3]),.result(result[96+:32]));
endmodule
