// One coherent ingress register before the frozen signed reducer.
// Accepted edge k responds at k+5; II=1. Quarantine blocks NEW captures,
// not an already admitted tail. The owning field gates eligibility/commit.
module genefer_stream27_signed_boundary_inputreg_v1 #(
    parameter logic [31:0] P=32'd104857601,
    parameter int AW=16, BLOCKS=8, PAYLOAD_W=1
) (
    input logic clk,rst_n,quarantine,in_valid,boundary_high,
    input logic signed [31:0] correction,
    input logic [31:0] base,
    input logic [PAYLOAD_W-1:0] payload_in,
    output logic out_valid,out_error,
    output logic [31:0] residue,
    output logic [PAYLOAD_W-1:0] payload_out
);
    logic slot_q,high_q;
    logic signed [31:0] correction_q;
    logic [31:0] base_q;
    logic [PAYLOAD_W-1:0] owner_q;
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)slot_q<=1'b0;
        else slot_q<=in_valid && !quarantine;
    end
    always_ff @(posedge clk)begin
        if(rst_n && in_valid && !quarantine)begin
            correction_q<=correction; base_q<=base;
            high_q<=boundary_high; owner_q<=payload_in;
        end
    end
    genefer_stream27_signed_boundary_reduce27_pipe #(
        .P(P),.AW(AW),.BLOCKS(BLOCKS),.PAYLOAD_W(PAYLOAD_W)
    ) core (
        .clk,.rst_n,.in_valid(slot_q),.boundary_high(high_q),
        .correction(correction_q),.base(base_q),.payload_in(owner_q),
        .out_valid,.out_error,.residue,.payload_out
    );
endmodule
