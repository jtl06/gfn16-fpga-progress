// Paired AW5 integration probe; not a physical top.
module root_lookahead_engine_pair_v1 #(
    parameter int AW=16, LANES=64, HOST_LANES=16,
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
) (
    input logic clk,rst_n,load_we,read_en,
    input logic [AW-1:0] host_addr,
    input logic [31:0] write_data,
    output logic read_valid,
    output logic [31:0] read_data,
    input logic vector_load_we,vector_read_en,
    input logic [AW-1:0] vector_addr,
    input logic [HOST_LANES-1:0] vector_lane_mask,
    input logic [HOST_LANES*32-1:0] vector_write_data,
    output logic vector_read_valid,host_error,
    output logic [HOST_LANES-1:0] vector_read_mask,
    output logic [HOST_LANES*32-1:0] vector_read_data,
    input logic profile_begin,profile_we,profile_commit,
    input logic [4:0] profile_size_log2,
    input logic [31:0] profile_modulus,profile_data,
    input logic [7:0] profile_format,
    input logic [15:0] profile_addr,
    output logic profile_loaded,profile_loading,profile_error,
    output logic [4:0] profile_loaded_size,
    output logic [15:0] profile_next_addr,
    output logic [63:0] seed_setup_cycles,
    input logic start,inverse,dif,
    input logic [1:0] root_phase,op,
    input logic [4:0] size_log2,
    input logic [31:0] scale,
    output logic busy,done,error,
    output logic [63:0] cycles,butterflies,data_reads,data_writes,root_reads,wait_cycles,
    output logic pair_mismatch
);
    logic baseline_read_valid;
    logic [31:0] baseline_read_data;
    logic baseline_vector_read_valid;
    logic baseline_host_error;
    logic [HOST_LANES-1:0] baseline_vector_read_mask;
    logic [HOST_LANES*32-1:0] baseline_vector_read_data;
    logic baseline_profile_loaded;
    logic baseline_profile_loading;
    logic baseline_profile_error;
    logic [4:0] baseline_profile_loaded_size;
    logic [15:0] baseline_profile_next_addr;
    logic [63:0] baseline_seed_setup_cycles;
    logic baseline_busy;
    logic baseline_done;
    logic baseline_error;
    logic [63:0] baseline_cycles;
    logic [63:0] baseline_butterflies;
    logic [63:0] baseline_data_reads;
    logic [63:0] baseline_data_writes;
    logic [63:0] baseline_root_reads;
    logic [63:0] baseline_wait_cycles;
    genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_engine #(.AW(AW),.LANES(LANES),.HOST_LANES(HOST_LANES),.P(P),.Q(Q)) baseline (
        .clk(clk),
        .rst_n(rst_n),
        .load_we(load_we),
        .read_en(read_en),
        .host_addr(host_addr),
        .write_data(write_data),
        .read_valid(baseline_read_valid),
        .read_data(baseline_read_data),
        .vector_load_we(vector_load_we),
        .vector_read_en(vector_read_en),
        .vector_addr(vector_addr),
        .vector_lane_mask(vector_lane_mask),
        .vector_write_data(vector_write_data),
        .vector_read_valid(baseline_vector_read_valid),
        .host_error(baseline_host_error),
        .vector_read_mask(baseline_vector_read_mask),
        .vector_read_data(baseline_vector_read_data),
        .profile_begin(profile_begin),
        .profile_we(profile_we),
        .profile_commit(profile_commit),
        .profile_size_log2(profile_size_log2),
        .profile_modulus(profile_modulus),
        .profile_data(profile_data),
        .profile_format(profile_format),
        .profile_addr(profile_addr),
        .profile_loaded(baseline_profile_loaded),
        .profile_loading(baseline_profile_loading),
        .profile_error(baseline_profile_error),
        .profile_loaded_size(baseline_profile_loaded_size),
        .profile_next_addr(baseline_profile_next_addr),
        .seed_setup_cycles(baseline_seed_setup_cycles),
        .start(start),
        .inverse(inverse),
        .dif(dif),
        .root_phase(root_phase),
        .op(op),
        .size_log2(size_log2),
        .scale(scale),
        .busy(baseline_busy),
        .done(baseline_done),
        .error(baseline_error),
        .cycles(baseline_cycles),
        .butterflies(baseline_butterflies),
        .data_reads(baseline_data_reads),
        .data_writes(baseline_data_writes),
        .root_reads(baseline_root_reads),
        .wait_cycles(baseline_wait_cycles)
    );
    genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_lookahead_v1_engine #(.AW(AW),.LANES(LANES),.HOST_LANES(HOST_LANES),.P(P),.Q(Q)) candidate (
        .clk(clk),
        .rst_n(rst_n),
        .load_we(load_we),
        .read_en(read_en),
        .host_addr(host_addr),
        .write_data(write_data),
        .read_valid(read_valid),
        .read_data(read_data),
        .vector_load_we(vector_load_we),
        .vector_read_en(vector_read_en),
        .vector_addr(vector_addr),
        .vector_lane_mask(vector_lane_mask),
        .vector_write_data(vector_write_data),
        .vector_read_valid(vector_read_valid),
        .host_error(host_error),
        .vector_read_mask(vector_read_mask),
        .vector_read_data(vector_read_data),
        .profile_begin(profile_begin),
        .profile_we(profile_we),
        .profile_commit(profile_commit),
        .profile_size_log2(profile_size_log2),
        .profile_modulus(profile_modulus),
        .profile_data(profile_data),
        .profile_format(profile_format),
        .profile_addr(profile_addr),
        .profile_loaded(profile_loaded),
        .profile_loading(profile_loading),
        .profile_error(profile_error),
        .profile_loaded_size(profile_loaded_size),
        .profile_next_addr(profile_next_addr),
        .seed_setup_cycles(seed_setup_cycles),
        .start(start),
        .inverse(inverse),
        .dif(dif),
        .root_phase(root_phase),
        .op(op),
        .size_log2(size_log2),
        .scale(scale),
        .busy(busy),
        .done(done),
        .error(error),
        .cycles(cycles),
        .butterflies(butterflies),
        .data_reads(data_reads),
        .data_writes(data_writes),
        .root_reads(root_reads),
        .wait_cycles(wait_cycles)
    );
    assign pair_mismatch=
        (read_valid !== baseline_read_valid) ||
        (vector_read_valid !== baseline_vector_read_valid) ||
        (host_error !== baseline_host_error) ||
        (vector_read_mask !== baseline_vector_read_mask) ||
        (profile_loaded !== baseline_profile_loaded) ||
        (profile_loading !== baseline_profile_loading) ||
        (profile_error !== baseline_profile_error) ||
        (profile_loaded_size !== baseline_profile_loaded_size) ||
        (profile_next_addr !== baseline_profile_next_addr) ||
        (seed_setup_cycles !== baseline_seed_setup_cycles) ||
        (busy !== baseline_busy) ||
        (done !== baseline_done) ||
        (error !== baseline_error) ||
        (cycles !== baseline_cycles) ||
        (butterflies !== baseline_butterflies) ||
        (data_reads !== baseline_data_reads) ||
        (data_writes !== baseline_data_writes) ||
        (root_reads !== baseline_root_reads) ||
        (wait_cycles !== baseline_wait_cycles) ||
        (read_valid && read_data !== baseline_read_data) ||
        (vector_read_valid && vector_read_mask[0] && vector_read_data[0+:32] !== baseline_vector_read_data[0+:32]) ||
        (vector_read_valid && vector_read_mask[1] && vector_read_data[32+:32] !== baseline_vector_read_data[32+:32]) ||
        (vector_read_valid && vector_read_mask[2] && vector_read_data[64+:32] !== baseline_vector_read_data[64+:32]) ||
        (vector_read_valid && vector_read_mask[3] && vector_read_data[96+:32] !== baseline_vector_read_data[96+:32]) ||
        (vector_read_valid && vector_read_mask[4] && vector_read_data[128+:32] !== baseline_vector_read_data[128+:32]) ||
        (vector_read_valid && vector_read_mask[5] && vector_read_data[160+:32] !== baseline_vector_read_data[160+:32]) ||
        (vector_read_valid && vector_read_mask[6] && vector_read_data[192+:32] !== baseline_vector_read_data[192+:32]) ||
        (vector_read_valid && vector_read_mask[7] && vector_read_data[224+:32] !== baseline_vector_read_data[224+:32]) ||
        (vector_read_valid && vector_read_mask[8] && vector_read_data[256+:32] !== baseline_vector_read_data[256+:32]) ||
        (vector_read_valid && vector_read_mask[9] && vector_read_data[288+:32] !== baseline_vector_read_data[288+:32]) ||
        (vector_read_valid && vector_read_mask[10] && vector_read_data[320+:32] !== baseline_vector_read_data[320+:32]) ||
        (vector_read_valid && vector_read_mask[11] && vector_read_data[352+:32] !== baseline_vector_read_data[352+:32]) ||
        (vector_read_valid && vector_read_mask[12] && vector_read_data[384+:32] !== baseline_vector_read_data[384+:32]) ||
        (vector_read_valid && vector_read_mask[13] && vector_read_data[416+:32] !== baseline_vector_read_data[416+:32]) ||
        (vector_read_valid && vector_read_mask[14] && vector_read_data[448+:32] !== baseline_vector_read_data[448+:32]) ||
        (vector_read_valid && vector_read_mask[15] && vector_read_data[480+:32] !== baseline_vector_read_data[480+:32]);
endmodule
