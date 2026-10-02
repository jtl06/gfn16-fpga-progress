// r75 isolated final inverse GS pair. Canonical operands/root; radix remains 2^32.
// Complete input bundle accepted E0, unchanged pair accepts E1, both outputs E6.
// II=1. All final-stage slot/start/generation metadata must gain the same edge.
// rst_n immediately flushes input valid AND the unchanged arithmetic pipelines.
module genefer_stream27_merged_final_gs_pair_inputreg_v1_p16_diet_v1 #(
    parameter logic [31:0] P=32'd104857601,
    parameter logic [31:0] Q=32'd4190109697,
    parameter logic [31:0] UPPER_SCALE=32'd1
) (
    input logic clk,rst_n,in_valid,
    input logic [31:0] u,v,normalized_lower_root,
    output logic out_valid,out_error,
    output logic [31:0] y0,y1
);
    logic input_valid_q;
    logic [31:0] u_q,v_q,lower_root_q;
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)input_valid_q<=0;
        else input_valid_q<=in_valid;
    end
    // Payload is token-qualified, not asynchronously reset. No stale payload
    // can publish after reset: input valid and every parent valid are flushed.
    always_ff @(posedge clk)begin
        if(rst_n && in_valid)begin
            u_q<=u;v_q<=v;lower_root_q<=normalized_lower_root;
        end
    end
    genefer_stream27_merged_final_gs_pair_v1_p16_diet_v1 #(.P(P),.Q(Q),.UPPER_SCALE(UPPER_SCALE)) pair (
        .clk,.rst_n,.in_valid(input_valid_q),.u(u_q),.v(v_q),
        .normalized_lower_root(lower_root_q),.out_valid,.out_error,.y0,.y1);
    // synthesis translate_off
    always @(posedge clk)if(rst_n && in_valid && (u>=P || v>=P || normalized_lower_root>=P))
        $fatal(1,"S_M2_FINAL_GS_INPUTREG_CANONICAL_INPUT_REQUIRED");
    // synthesis translate_on
endmodule
