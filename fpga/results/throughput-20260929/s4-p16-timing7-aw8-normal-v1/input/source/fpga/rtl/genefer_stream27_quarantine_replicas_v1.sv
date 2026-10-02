// Same-origin-edge copies of an existing sticky fault setter. No pipeline,
// pending-gated acceptance, reset-release change or physical-locality claim.
// Caller retains its original public fault register and supplies its exact
// setter, including original stop qualification. All copies reset together.
module genefer_stream27_quarantine_replicas_v1 #(parameter int COPIES=2) (
    input logic clk,rst_n,fault_set,
    output logic [COPIES-1:0] quarantine
);
    for(genvar copy=0;copy<COPIES;copy=copy+1)begin: destination
        (* preserve, dont_merge *) logic fault_q;
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)fault_q<=1'b0;
            else if(fault_set)fault_q<=1'b1;
        end
        assign quarantine[copy]=fault_q;
    end
    // synthesis translate_off
    initial if(COPIES!=2)$fatal(1,"S4_FAULT_REPLICAS_TWO_TRANSFORM_DESTINATIONS");
    // synthesis translate_on
endmodule
