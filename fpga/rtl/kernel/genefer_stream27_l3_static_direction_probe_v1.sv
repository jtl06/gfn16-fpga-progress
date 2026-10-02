// Static CT/GS sizing: four independent input FF sets; no shared products.
// TAG_W=1 matches current streaming cells. E0 input -> E6 output, II1.
// Only gs constant binding changes; arithmetic definitions stay byte-identical.
module genefer_stream27_l3_static_direction_probe_v1 #(
 parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
)(input logic clk,rst_n,input logic [3:0] in_valid,in_tag,
 input logic [111:0] u,v,input logic [107:0] w,
 output logic [3:0] out_valid,out_tag,output logic [111:0] y0,y1);
 logic [3:0] valid_q,tag_q;logic [111:0] u_q,v_q;logic [107:0] w_q;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin valid_q<=0;tag_q<=0;u_q<=0;v_q<=0;w_q<=0;end
  else begin valid_q<=in_valid;tag_q<=in_tag;u_q<=u;v_q<=v;w_q<=w;end
 end
 genefer_stream27_factored_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(1)) normalized_ct(
  .clk,.rst_n,.in_valid(valid_q[0]),.gs(1'b0),.u(u_q[0+:28]),.v(v_q[0+:28]),.w(w_q[0+:27]),
  .in_tag(tag_q[0]),.out_valid(out_valid[0]),.y0(y0[0+:28]),.y1(y1[0+:28]),.out_tag(out_tag[0]));
 genefer_stream27_fused_sign_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(1)) fused_ct(
  .clk,.rst_n,.in_valid(valid_q[1]),.gs(1'b0),.u(u_q[28+:28]),.v(v_q[28+:28]),.w(w_q[27+:27]),
  .in_tag(tag_q[1]),.out_valid(out_valid[1]),.y0(y0[28+:28]),.y1(y1[28+:28]),.out_tag(out_tag[1]));
 genefer_stream27_factored_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(1)) normalized_gs(
  .clk,.rst_n,.in_valid(valid_q[2]),.gs(1'b1),.u(u_q[56+:28]),.v(v_q[56+:28]),.w(w_q[54+:27]),
  .in_tag(tag_q[2]),.out_valid(out_valid[2]),.y0(y0[56+:28]),.y1(y1[56+:28]),.out_tag(out_tag[2]));
 genefer_stream27_fused_sign_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(1)) fused_gs(
  .clk,.rst_n,.in_valid(valid_q[3]),.gs(1'b1),.u(u_q[84+:28]),.v(v_q[84+:28]),.w(w_q[81+:27]),
  .in_tag(tag_q[3]),.out_valid(out_valid[3]),.y0(y0[84+:28]),.y1(y1[84+:28]),.out_tag(out_tag[3]));
endmodule
