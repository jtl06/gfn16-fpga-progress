// Isolated three-field reset islands: asynchronous assertion, two-edge release.
// reset-ready is NOT profile/image/operation-ready. Caller preserves every
// original raw same-edge commit/accept kill and reload/quarantine predicate.
module genefer_anext_field_reset_release_v1 (
    input logic clk,rst_n,cancel,failed,
    output logic [2:0] field_rst_n,field_allow,
    output logic ready,kill
);
    wire assertion_rst_n=rst_n && !cancel && !failed;
    assign kill=!assertion_rst_n;
    for(genvar f=0;f<3;f=f+1)begin: field_local
        // Real field-specific fanout destinations; source attributes request
        // retention/nonmerge, not a claim about achieved physical locality.
        (* preserve, dont_merge *) logic assertion_guard_q;
        (* preserve, dont_merge *) logic release_driver_q;
        always_ff @(posedge clk or negedge assertion_rst_n)begin
            if(!assertion_rst_n)begin
                assertion_guard_q<=0;release_driver_q<=0;
            end else begin
                assertion_guard_q<=1;release_driver_q<=assertion_guard_q;
            end
        end
        // No raw-cancel combinational gate is reintroduced on the reset tree.
        assign field_rst_n[f]=release_driver_q;
        // Acceptance kill is immediate even before asynchronous FF propagation.
        assign field_allow[f]=assertion_rst_n && release_driver_q;
    end
    assign ready=assertion_rst_n && (&field_rst_n);
endmodule
