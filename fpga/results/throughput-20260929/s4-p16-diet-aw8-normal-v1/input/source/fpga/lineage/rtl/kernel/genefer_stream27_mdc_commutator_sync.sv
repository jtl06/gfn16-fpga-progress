// Isolated S3 primitive. Synchronous lookahead RAM reads, no async RAM read.
// Dense frames of FRAME_T rows; gaps may have any nonnegative length.
// Each FIFO delays L clocks. Registered pair output is consumed next edge.
// Per-context cancellation changes live_generations/context_enabled externally;
// it NEVER clears/stalls FIFO state. Do not reuse a generation before drain.
module genefer_stream27_mdc_commutator_sync #(
    parameter int unsigned DATA_W = 27,
    parameter int unsigned PAYLOAD_W = 16,
    parameter int unsigned GEN_W = 8,
    parameter int unsigned DEPTH = 4,
    parameter int unsigned FRAME_T = 8,
    parameter int unsigned CONTEXTS = 2
) (
    input logic clk, rst_n,
    input logic in_valid, frame_start,
    input logic [DATA_W-1:0] upper_in, lower_in,
    input logic [PAYLOAD_W-1:0] upper_payload, lower_payload,
    input logic context_in,
    input logic [GEN_W-1:0] generation_in,
    input logic [CONTEXTS-1:0] context_enabled,
    input logic [CONTEXTS*GEN_W-1:0] live_generations,
    output logic out_valid, out_error,
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
    logic [COUNT_W-1:0] remaining, offset;
    logic frame_owner;
    logic [GEN_W-1:0] frame_generation;
    logic malformed, phase, advance, owner_bad, eligible;
    word_t x, y, head_upper, head_lower, write_upper, result_lower;
    logic [GEN_W-1:0] expected_generation;

    always_comb begin
        malformed = (frame_start && ((remaining != '0) || !in_valid)) ||
                    (in_valid && !frame_start && (remaining == '0)) ||
                    (!in_valid && (remaining != '0)) ||
                    (in_valid && (CONTEXTS == 1) && context_in) ||
                    (in_valid && !frame_start && (remaining != '0) &&
                     ((context_in != frame_owner) || (generation_in != frame_generation)));
        phase = in_valid && !frame_start && offset[SHIFT];
        x = '0; y = '0;
        x.valid = in_valid; x.data = upper_in; x.payload = upper_payload;
        x.owner = context_in; x.generation = generation_in;
        y.valid = in_valid; y.data = lower_in; y.payload = lower_payload;
        y.owner = context_in; y.generation = generation_in;
        write_upper = phase ? head_lower : x;
        result_lower = phase ? x : head_lower;
        owner_bad = (head_upper.valid != result_lower.valid) ||
                    (head_upper.valid && ((head_upper.owner != result_lower.owner) ||
                     (head_upper.generation != result_lower.generation)));
        // Fixed mux for 1|2 contexts: no out-of-range dynamic select.
        expected_generation = live_generations[GEN_W-1:0];
        if (CONTEXTS == 2)
            expected_generation = head_upper.owner ?
                GEN_W'(live_generations >> GEN_W) : live_generations[GEN_W-1:0];
        eligible = head_upper.valid && !owner_bad &&
                   (head_upper.generation == expected_generation) &&
                   (head_upper.owner ? ((CONTEXTS == 2) && context_enabled[CONTEXTS-1]) : context_enabled[0]);
        advance = rst_n && !out_error && !malformed && !owner_bad;
    end

    genefer_stream27_mdc_fifo_sync #(.WORD_W(WORD_W), .DEPTH(DEPTH)) upper_fifo (
        .clk(clk), .rst_n(rst_n), .advance(advance), .write_word(write_upper), .head(head_upper));
    genefer_stream27_mdc_fifo_sync #(.WORD_W(WORD_W), .DEPTH(DEPTH)) lower_fifo (
        .clk(clk), .rst_n(rst_n), .advance(advance), .write_word(y), .head(head_lower));

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_valid <= 1'b0; out_error <= 1'b0;
            remaining <= '0; offset <= '0;
        end else begin
            out_valid <= 1'b0;
            if (malformed || owner_bad) out_error <= 1'b1;
            if (advance) begin
                if (in_valid) begin
                    if (frame_start) begin
                        remaining <= COUNT_W'(FRAME_T-1); offset <= COUNT_W'(1);
                        frame_owner <= context_in; frame_generation <= generation_in;
                    end else begin
                        remaining <= remaining - COUNT_W'(1); offset <= offset + COUNT_W'(1);
                    end
                end
                if (eligible) begin
                    out_valid <= 1'b1;
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
            (CONTEXTS != 1 && CONTEXTS != 2)) $fatal(1, "COMM_PARAMETERS");
    end
    // synthesis translate_on
endmodule

module genefer_stream27_mdc_fifo_sync #(
    parameter int unsigned WORD_W = 53,
    parameter int unsigned DEPTH = 4
) (
    input logic clk, rst_n, advance,
    input logic [WORD_W-1:0] write_word,
    output logic [WORD_W-1:0] head
);
    generate if (DEPTH == 1) begin : register_cell
        logic occupied;
        logic [WORD_W-1:0] value;
        assign head = occupied ? value : '0;
        always_ff @(posedge clk or negedge rst_n) begin
            if (!rst_n) occupied <= 1'b0;
            else if (advance) occupied <= 1'b1;
        end
        always_ff @(posedge clk) if (advance) value <= write_word;
    end else begin : synchronous_ram
        localparam int unsigned PTR_W = $clog2(DEPTH);
        localparam int unsigned FILL_W = $clog2(DEPTH+1);
        logic [PTR_W-1:0] pointer, next_pointer;
        logic [FILL_W-1:0] filled;
        logic [WORD_W-1:0] memory [0:DEPTH-1];
        logic [WORD_W-1:0] prefetched;
        assign next_pointer = pointer + PTR_W'(1);
        assign head = (filled == FILL_W'(DEPTH)) ? prefetched : '0;
        // Distinct addresses for DEPTH>=2: old-data collision mode irrelevant.
        // No reset in this block: neither payload nor tag RAM is reset.
        always_ff @(posedge clk) begin
            if (advance) begin
                prefetched <= memory[next_pointer];
                memory[pointer] <= write_word;
            end
        end
        always_ff @(posedge clk or negedge rst_n) begin
            if (!rst_n) begin pointer <= '0; filled <= '0; end
            else if (advance) begin
                pointer <= next_pointer;
                if (filled != FILL_W'(DEPTH)) filled <= filled + FILL_W'(1);
            end
        end
    end endgenerate
endmodule
