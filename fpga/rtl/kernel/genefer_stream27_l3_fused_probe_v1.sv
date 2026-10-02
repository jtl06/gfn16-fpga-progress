// Independent input FF sets prevent sharing variable products between cells.
// Sizing-only E0 input register adds one edge; each butterfly still has E0->E5.
module genefer_stream27_l3_fused_probe_v1 #(
 parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
)(input logic clk,rst_n,input logic [2:0] in_valid,gs,
 input logic [83:0] u,v,input logic [80:0] w,input logic [95:0] in_tag,
 output logic [2:0] out_valid,output logic [83:0] y0,y1,output logic [95:0] out_tag);
 logic [2:0] valid_q,gs_q;logic [83:0] u_q,v_q;logic [80:0] w_q;logic [95:0] tag_q;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin valid_q<=0;gs_q<=0;u_q<=0;v_q<=0;w_q<=0;tag_q<=0;end
  else begin valid_q<=in_valid;gs_q<=gs;u_q<=u;v_q<=v;w_q<=w;tag_q<=in_tag;end
 end
 genefer_ntt_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(32)) frozen_butterfly(
  .clk,.rst_n,.in_valid(valid_q[0]),.gs(gs_q[0]),.u(u_q[0+:28]),.v(v_q[0+:28]),.w(w_q[0+:27]),
  .in_tag(tag_q[0+:32]),.out_valid(out_valid[0]),.y0(y0[0+:28]),.y1(y1[0+:28]),.out_tag(out_tag[0+:32]));
 genefer_stream27_factored_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(32)) factored_butterfly(
  .clk,.rst_n,.in_valid(valid_q[1]),.gs(gs_q[1]),.u(u_q[28+:28]),.v(v_q[28+:28]),.w(w_q[27+:27]),
  .in_tag(tag_q[32+:32]),.out_valid(out_valid[1]),.y0(y0[28+:28]),.y1(y1[28+:28]),.out_tag(out_tag[32+:32]));
 genefer_stream27_fused_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(32)) fused_butterfly(
  .clk,.rst_n,.in_valid(valid_q[2]),.gs(gs_q[2]),.u(u_q[56+:28]),.v(v_q[56+:28]),.w(w_q[54+:27]),
  .in_tag(tag_q[64+:32]),.out_valid(out_valid[2]),.y0(y0[56+:28]),.y1(y1[56+:28]),.out_tag(out_tag[64+:32]));
endmodule
