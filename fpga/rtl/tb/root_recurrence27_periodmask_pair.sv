// Paired component equivalence probe; no integration or physical claim.
module root_recurrence27_periodmask_pair #(
    parameter int LANES=16,TAG_W=32,
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
) (
    input logic clk,rst_n,
    input logic seed_we,seed_clear,seed_bank,
    input logic [1:0] seed_context,
    input logic [6:0] seed_lane,
    input logic [31:0] seed_data,
    input logic start,config_bank,
    input logic [16:0] config_groups,config_period,
    input logic [6:0] config_active_lanes,
    input logic [31:0] config_step,
    input logic request_valid,
    output logic request_ready,
    input logic [TAG_W-1:0] request_tag,
    output logic root_valid,
    output logic [LANES*32-1:0] roots,
    output logic [LANES-1:0] root_mask,
    output logic [TAG_W-1:0] root_tag,
    output logic [16:0] root_group,
    output logic busy,done,error,seed_error,
    output logic [63:0] cycles,
    output logic pair_mismatch,
    output logic [31:0] probe_lanes,probe_p,probe_q
);
    logic baseline_request_ready,baseline_root_valid,baseline_busy,baseline_done,baseline_error,baseline_seed_error;
    logic [LANES*32-1:0] baseline_roots;
    logic [LANES-1:0] baseline_root_mask;
    logic [TAG_W-1:0] baseline_root_tag;
    logic [16:0] baseline_root_group;
    logic [63:0] baseline_cycles;
    assign probe_lanes=LANES;assign probe_p=P;assign probe_q=Q;
    genefer_root_recurrence27 #(.LANES(LANES),.TAG_W(TAG_W),.P(P),.Q(Q)) baseline (
        .clk(clk),
        .rst_n(rst_n),
        .seed_we(seed_we),
        .seed_clear(seed_clear),
        .seed_bank(seed_bank),
        .seed_context(seed_context),
        .seed_lane(seed_lane),
        .seed_data(seed_data),
        .start(start),
        .config_bank(config_bank),
        .config_groups(config_groups),
        .config_period(config_period),
        .config_active_lanes(config_active_lanes),
        .config_step(config_step),
        .request_valid(request_valid),
        .request_ready(baseline_request_ready),
        .request_tag(request_tag),
        .root_valid(baseline_root_valid),
        .roots(baseline_roots),
        .root_mask(baseline_root_mask),
        .root_tag(baseline_root_tag),
        .root_group(baseline_root_group),
        .busy(baseline_busy),
        .done(baseline_done),
        .error(baseline_error),
        .seed_error(baseline_seed_error),
        .cycles(baseline_cycles)
    );
    genefer_root_recurrence27_periodmask #(.LANES(LANES),.TAG_W(TAG_W),.P(P),.Q(Q)) candidate (
        .clk(clk),
        .rst_n(rst_n),
        .seed_we(seed_we),
        .seed_clear(seed_clear),
        .seed_bank(seed_bank),
        .seed_context(seed_context),
        .seed_lane(seed_lane),
        .seed_data(seed_data),
        .start(start),
        .config_bank(config_bank),
        .config_groups(config_groups),
        .config_period(config_period),
        .config_active_lanes(config_active_lanes),
        .config_step(config_step),
        .request_valid(request_valid),
        .request_ready(request_ready),
        .request_tag(request_tag),
        .root_valid(root_valid),
        .roots(roots),
        .root_mask(root_mask),
        .root_tag(root_tag),
        .root_group(root_group),
        .busy(busy),
        .done(done),
        .error(error),
        .seed_error(seed_error),
        .cycles(cycles)
    );
    assign pair_mismatch=
        (request_ready !== baseline_request_ready) ||
        (root_valid !== baseline_root_valid) ||
        (roots !== baseline_roots) ||
        (root_mask !== baseline_root_mask) ||
        (root_tag !== baseline_root_tag) ||
        (root_group !== baseline_root_group) ||
        (busy !== baseline_busy) ||
        (done !== baseline_done) ||
        (error !== baseline_error) ||
        (seed_error !== baseline_seed_error) ||
        (cycles !== baseline_cycles);
endmodule
