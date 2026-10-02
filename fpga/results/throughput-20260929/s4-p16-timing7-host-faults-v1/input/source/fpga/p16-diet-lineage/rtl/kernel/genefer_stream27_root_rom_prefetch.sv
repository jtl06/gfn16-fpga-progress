// Source-only S3 row-root wrapper. One synchronous read/edge, no async ROM
// access, no extra butterfly edge. Incoming physical row0 uses FIRST_ROOT;
// accepting row r prefetches root r+1 for the following physical row.
// FIRST_ROOT makes immediate post-reset row0 independent of retained ROM q.
// Initialize ROM from the exact compiler-produced R-form roots. A missing
// HEX_FILE is a preparation failure, not permission to fit unknown constants.
module genefer_stream27_root_rom_prefetch #(
    parameter int unsigned PERIOD = 4,
    parameter logic [26:0] FIRST_ROOT = 27'd0,
    parameter string HEX_FILE = ""
) (
    input logic clk, rst_n, in_slot_valid, frame_start,
    output logic [26:0] root
);
    generate if (PERIOD == 1) begin : constant_root
        assign root = FIRST_ROOT;
    end else begin : synchronous_root
        localparam int unsigned ADDR_W = $clog2(PERIOD);
        (* ramstyle = "M20K" *) logic [26:0] roots [0:PERIOD-1];
        logic [ADDR_W-1:0] current_row, following_row;
        logic [26:0] prefetched;
        assign following_row = frame_start ? ADDR_W'(1) : current_row + ADDR_W'(1);
        assign root = frame_start ? FIRST_ROOT : prefetched;
        initial $readmemh(HEX_FILE, roots);
        // No reset on ROM payload/read register; first-row constant bypass is
        // the eligibility-safe initialization mechanism.
        always_ff @(posedge clk)
            if (rst_n && in_slot_valid) prefetched <= roots[following_row];
        always_ff @(posedge clk or negedge rst_n) begin
            if (!rst_n) current_row <= '0;
            else if (in_slot_valid) current_row <= following_row;
        end
    end endgenerate
    // synthesis translate_off
    initial begin
        if (PERIOD < 1 || (PERIOD & (PERIOD-1)) != 0)
            $fatal(1, "FIELD_ROOT_PERIOD");
        if (PERIOD > 1 && HEX_FILE == "") $fatal(1, "FIELD_ROOT_ROM_MISSING");
    end
    // synthesis translate_on
endmodule
