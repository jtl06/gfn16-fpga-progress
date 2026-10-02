// Matched r75 sizing/normal fixture: TWO independent registered source sets.
// Source lazy28 -> exact current one-subtract canonical boundary -> pair.
// Old E6/new E7 incl source FF; internal pair E5/E6, respectively, II1.
module genefer_stream27_final_pair_inputreg_sizing_v1 #(
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697,
    parameter logic [31:0] UPPER_SCALE=32'd1
) (
    input logic clk,rst_n,
    input logic [1:0] in_valid,
    input logic [55:0] u,v,
    input logic [63:0] normalized_lower_root,
    output logic old_valid,new_valid,old_error,new_error,
    output logic [31:0] old_y0,old_y1,new_y0,new_y1
);
    logic [1:0] valid_q;
    logic [27:0] u_q[0:1],v_q[0:1];
    logic [31:0] root_q[0:1];
    wire [31:0] canonical_u[0:1],canonical_v[0:1];
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)valid_q<=0;
        else valid_q<=in_valid;
    end
    for(genvar k=0;k<2;k=k+1)begin : source_sets
        always_ff @(posedge clk)if(rst_n && in_valid[k])begin
            u_q[k]<=u[k*28+:28];v_q[k]<=v[k*28+:28];root_q[k]<=normalized_lower_root[k*32+:32];
        end
        assign canonical_u[k]={4'b0,u_q[k]>=28'(P) ? u_q[k]-28'(P) : u_q[k]};
        assign canonical_v[k]={4'b0,v_q[k]>=28'(P) ? v_q[k]-28'(P) : v_q[k]};
    end
    genefer_stream27_merged_final_gs_pair_v1 #(.P(P),.Q(Q),.UPPER_SCALE(UPPER_SCALE)) original (
        .clk,.rst_n,.in_valid(valid_q[0]),.u(canonical_u[0]),.v(canonical_v[0]),
        .normalized_lower_root(root_q[0]),.out_valid(old_valid),.out_error(old_error),.y0(old_y0),.y1(old_y1));
    genefer_stream27_merged_final_gs_pair_inputreg_v1 #(.P(P),.Q(Q),.UPPER_SCALE(UPPER_SCALE)) registered_pair (
        .clk,.rst_n,.in_valid(valid_q[1]),.u(canonical_u[1]),.v(canonical_v[1]),
        .normalized_lower_root(root_q[1]),.out_valid(new_valid),.out_error(new_error),.y0(new_y0),.y1(new_y1));
endmodule
