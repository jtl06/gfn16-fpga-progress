// Additive physical-slot successor. Compile with frozen commutator_sync.sv
// for genefer_stream27_mdc_fifo_smallreg_v1; that helper and its RAM timing are unchanged.
// Every occupied output updates data/tags, including canceled generations.
// Finite tags MUST NOT be reused/re-enabled until old slots and commits drain.
module genefer_stream27_mdc_commutator_slots_sm1_v1 #(
    parameter int unsigned DATA_W = 27,
    parameter int unsigned PAYLOAD_W = 16,
    parameter int unsigned GEN_W = 8,
    parameter int unsigned DEPTH = 4,
    parameter int unsigned FRAME_T = 8,
    parameter int unsigned CONTEXTS = 1
) (
    input logic clk, rst_n,
    input logic in_slot_valid, frame_start,
    input logic [DATA_W-1:0] upper_in, lower_in,
    input logic [PAYLOAD_W-1:0] upper_payload, lower_payload,
    input logic context_in,
    input logic [GEN_W-1:0] generation_in,
    input logic [CONTEXTS-1:0] context_enabled,
    input logic [CONTEXTS*GEN_W-1:0] live_generations,
    // Registered OR of all stage errors freezes the chain after first fault.
    input logic quarantine,
    output logic out_slot_valid, out_frame_start, out_eligible, out_error,
    // Pre-edge fault authority for terminal commit; not a registered data port.
    output logic fault_pending,
    output logic [DATA_W-1:0] upper_out, lower_out,
    output logic [PAYLOAD_W-1:0] upper_payload_out, lower_payload_out,
    output logic context_out,
    output logic [GEN_W-1:0] generation_out
);
    localparam int unsigned COUNT_W = $clog2(FRAME_T+1);
    localparam int unsigned SHIFT = $clog2(DEPTH);
    typedef struct packed {
        logic valid;
        logic [DATA_W-1:0] data;
        logic [PAYLOAD_W-1:0] payload;
        logic owner;
        logic [GEN_W-1:0] generation;
    } word_t;
    localparam int unsigned WORD_W = $bits(word_t);
    logic [COUNT_W-1:0] remaining, offset, output_offset;
    logic frame_owner, output_owner;
    logic [GEN_W-1:0] frame_generation, output_generation;
    logic malformed, phase, advance, owner_bad, eligible;
    word_t x, y, head_upper, head_lower, write_upper, result_lower;
    logic [GEN_W-1:0] expected_generation;

    always_comb begin
        malformed = (frame_start && ((remaining != '0) || !in_slot_valid)) ||
                    (in_slot_valid && !frame_start && (remaining == '0)) ||
                    (!in_slot_valid && (remaining != '0)) ||
                    (in_slot_valid && (CONTEXTS == 1) && context_in) ||
                    (in_slot_valid && !frame_start && (remaining != '0) &&
                     ((context_in != frame_owner) || (generation_in != frame_generation)));
        phase = in_slot_valid && !frame_start && offset[SHIFT];
        x = '0; y = '0;
        x.valid = in_slot_valid; x.data = upper_in; x.payload = upper_payload;
        x.owner = context_in; x.generation = generation_in;
        y.valid = in_slot_valid; y.data = lower_in; y.payload = lower_payload;
        y.owner = context_in; y.generation = generation_in;
        write_upper = phase ? head_lower : x;
        result_lower = phase ? x : head_lower;
        owner_bad = (head_upper.valid != result_lower.valid) ||
                    (head_upper.valid && ((head_upper.owner != result_lower.owner) ||
                     (head_upper.generation != result_lower.generation))) ||
                    (head_upper.valid && (output_offset != '0) &&
                     ((head_upper.owner != output_owner) ||
                      (head_upper.generation != output_generation)));
        expected_generation = live_generations[GEN_W-1:0];
        if (CONTEXTS == 2)
            expected_generation = head_upper.owner ?
                GEN_W'(live_generations >> GEN_W) : live_generations[GEN_W-1:0];
        eligible = head_upper.valid && !owner_bad &&
                   (head_upper.generation == expected_generation) &&
                   (head_upper.owner ? ((CONTEXTS == 2) && context_enabled[CONTEXTS-1]) : context_enabled[0]);
        fault_pending = out_error || (!quarantine && (malformed || owner_bad));
        advance = rst_n && !quarantine && !fault_pending;
    end

    genefer_stream27_mdc_fifo_smallreg_v1 #(.WORD_W(WORD_W), .DEPTH(DEPTH)) upper_fifo (
        .clk(clk), .rst_n(rst_n), .advance(advance), .write_word(write_upper), .head(head_upper));
    genefer_stream27_mdc_fifo_smallreg_v1 #(.WORD_W(WORD_W), .DEPTH(DEPTH)) lower_fifo (
        .clk(clk), .rst_n(rst_n), .advance(advance), .write_word(y), .head(head_lower));

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_slot_valid <= 1'b0; out_frame_start <= 1'b0;
            out_eligible <= 1'b0; out_error <= 1'b0;
            remaining <= '0; offset <= '0; output_offset <= '0;
        end else begin
            out_slot_valid <= 1'b0; out_frame_start <= 1'b0; out_eligible <= 1'b0;
            if (!quarantine && (malformed || owner_bad)) out_error <= 1'b1;
            if (advance) begin
                if (in_slot_valid) begin
                    if (frame_start) begin
                        remaining <= COUNT_W'(FRAME_T-1); offset <= COUNT_W'(1);
                        frame_owner <= context_in; frame_generation <= generation_in;
                    end else begin
                        remaining <= remaining - COUNT_W'(1); offset <= offset + COUNT_W'(1);
                    end
                end
                if (head_upper.valid) begin
                    out_slot_valid <= 1'b1;
                    out_frame_start <= (output_offset == '0);
                    out_eligible <= eligible;
                    output_offset <= (output_offset == COUNT_W'(FRAME_T-1)) ? '0 : output_offset + COUNT_W'(1);
                    if (output_offset == '0) begin
                        output_owner <= head_upper.owner; output_generation <= head_upper.generation;
                    end
                    upper_out <= head_upper.data; lower_out <= result_lower.data;
                    upper_payload_out <= head_upper.payload; lower_payload_out <= result_lower.payload;
                    context_out <= head_upper.owner; generation_out <= head_upper.generation;
                end
            end
        end
    end

    // synthesis translate_off
    initial begin
        if (DEPTH < 1 || (DEPTH & (DEPTH-1)) != 0 || FRAME_T < 2*DEPTH ||
            FRAME_T % (2*DEPTH) != 0 || DATA_W < 1 || PAYLOAD_W < 1 || GEN_W < 1 ||
            (CONTEXTS != 1 && CONTEXTS != 2)) $fatal(1, "SLOTS_PARAMETERS");
    end
    // synthesis translate_on
endmodule
