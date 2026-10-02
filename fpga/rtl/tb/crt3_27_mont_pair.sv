// G2 transaction-index probe. Different fixed latencies are intentional.
module crt3_27_mont_pair #(
    parameter int CANDIDATE_DELAY=15,FROZEN_DELAY=60
) (
    input logic clk,rst_n,in_valid,
    input logic [31:0] r1,r2,r3,
    input logic [1:0] test_mode,
    output logic baseline_ready,baseline_valid,candidate_ready,candidate_valid,
    output logic signed [95:0] baseline_coefficient,candidate_coefficient,
    output logic [31:0] probe_candidate_delay,probe_frozen_delay,probe_coefficient_bits,
    output logic [31:0] probe_p1,probe_p2,probe_p3
);
    // Mode0 streams both; modes1/2 isolate input rejection so one instance's
    // assertion cannot mask the other instance's missing canonical guard.
    genefer_crt3_27_pipe baseline (
        .clk,.rst_n,.in_valid(in_valid && test_mode!=2),.r1,.r2,.r3,
        .ready(baseline_ready),.out_valid(baseline_valid),.coefficient(baseline_coefficient)
    );
    genefer_crt3_27_mont_pipe candidate (
        .clk,.rst_n,.in_valid(in_valid && test_mode!=1),.r1,.r2,.r3,
        .ready(candidate_ready),.out_valid(candidate_valid),.coefficient(candidate_coefficient)
    );
    assign probe_candidate_delay=CANDIDATE_DELAY;
    assign probe_frozen_delay=FROZEN_DELAY;
    assign probe_coefficient_bits=96;
    assign probe_p1=104857601;assign probe_p2=69206017;assign probe_p3=67239937;
    // synthesis translate_off
    initial if(CANDIDATE_DELAY!=15 || FROZEN_DELAY!=60)
        $fatal(1,"CRT27_MONT_WRAPPER_PROFILE");
    // synthesis translate_on
endmodule
