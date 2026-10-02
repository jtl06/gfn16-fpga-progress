// D1->D2, T8 transport/commit qualification top, not an arithmetic field.
// All data/slot outputs registered in the cells; fault_pending is deliberately
// combinational so a malformed input blocks an older pending terminal write.
module genefer_stream27_mdc_slots_chain_v2 #(
    parameter int unsigned BROKEN_FILTERED_LINK = 0,
    parameter int unsigned BROKEN_STALE_COMMIT = 0
) (
    input logic clk, rst_n,
    input logic in_slot_valid, frame_start,
    input logic [26:0] upper_in, lower_in,
    input logic [15:0] upper_payload, lower_payload,
    input logic context_in,
    input logic [7:0] generation_in,
    input logic [1:0] context_enabled,
    input logic [15:0] live_generations,
    output logic out_slot_valid, out_frame_start, out_eligible, out_error,
    output logic [1:0] stage_errors,
    output logic fault_pending,
    output logic [26:0] upper_out, lower_out,
    output logic [15:0] upper_payload_out, lower_payload_out,
    output logic context_out,
    output logic [7:0] generation_out,
    output logic commit_valid, commit_frame_start,
    output logic [26:0] commit_upper, commit_lower,
    output logic [15:0] commit_upper_payload, commit_lower_payload,
    output logic commit_context,
    output logic [7:0] commit_generation
);
    logic first_slot, first_start, first_eligible, first_fault;
    logic second_slot, second_start, second_eligible, second_fault;
    logic [26:0] first_upper, first_lower;
    logic [15:0] first_upper_payload, first_lower_payload;
    logic first_context;
    logic [7:0] first_generation, commit_expected_generation;
    logic link_valid, commit_authorized;
    assign out_error = |stage_errors;
    assign fault_pending = first_fault | second_fault;
    assign link_valid = (BROKEN_FILTERED_LINK != 0) ? first_eligible : first_slot;
    assign out_slot_valid = second_slot && !out_error;
    assign out_frame_start = second_start && !out_error;
    assign out_eligible = second_eligible && !out_error;
    assign commit_expected_generation = context_out ? live_generations[15:8] : live_generations[7:0];
    assign commit_authorized = (BROKEN_STALE_COMMIT != 0) ? out_eligible :
        (out_slot_valid && context_enabled[context_out] && generation_out == commit_expected_generation);

    genefer_stream27_mdc_commutator_slots_v2 #(.DEPTH(1), .FRAME_T(8), .CONTEXTS(2)) first (
        .clk(clk), .rst_n(rst_n), .in_slot_valid(in_slot_valid), .frame_start(frame_start),
        .upper_in(upper_in), .lower_in(lower_in), .upper_payload(upper_payload), .lower_payload(lower_payload),
        .context_in(context_in), .generation_in(generation_in), .context_enabled(context_enabled),
        .live_generations(live_generations), .quarantine(out_error),
        .out_slot_valid(first_slot), .out_frame_start(first_start), .out_eligible(first_eligible),
        .out_error(stage_errors[0]), .fault_pending(first_fault),
        .upper_out(first_upper), .lower_out(first_lower), .upper_payload_out(first_upper_payload),
        .lower_payload_out(first_lower_payload), .context_out(first_context), .generation_out(first_generation));
    genefer_stream27_mdc_commutator_slots_v2 #(.DEPTH(2), .FRAME_T(8), .CONTEXTS(2)) second (
        .clk(clk), .rst_n(rst_n), .in_slot_valid(link_valid), .frame_start(first_start && link_valid),
        .upper_in(first_upper), .lower_in(first_lower), .upper_payload(first_upper_payload),
        .lower_payload(first_lower_payload), .context_in(first_context), .generation_in(first_generation),
        .context_enabled(context_enabled), .live_generations(live_generations), .quarantine(out_error),
        .out_slot_valid(second_slot), .out_frame_start(second_start), .out_eligible(second_eligible),
        .out_error(stage_errors[1]), .fault_pending(second_fault),
        .upper_out(upper_out), .lower_out(lower_out), .upper_payload_out(upper_payload_out),
        .lower_payload_out(lower_payload_out), .context_out(context_out), .generation_out(generation_out));

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin commit_valid <= 1'b0; commit_frame_start <= 1'b0; end
        else begin
            commit_valid <= 1'b0; commit_frame_start <= 1'b0;
            if (!fault_pending && commit_authorized) begin
                commit_valid <= 1'b1; commit_frame_start <= out_frame_start;
                commit_upper <= upper_out; commit_lower <= lower_out;
                commit_upper_payload <= upper_payload_out; commit_lower_payload <= lower_payload_out;
                commit_context <= context_out; commit_generation <= generation_out;
            end
        end
    end
endmodule
