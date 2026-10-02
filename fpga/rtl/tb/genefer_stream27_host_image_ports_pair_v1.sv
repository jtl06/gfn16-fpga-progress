// Component/idle-host comparison only. The actual promoted T5b top remains
// byte-identical (704f7fed...), NTT_LANES=64, and start is tied low.
module genefer_stream27_host_image_ports_pair_v1 #(
    parameter int AW=5,P=16,
    parameter int ROW_W=AW-$clog2(P)
) (
    input logic clk,rst_n,host_access,load_we,read_en,
    input logic [AW-1:0] host_addr,
    input logic signed [31:0] write_data,
    input logic row_read_req,
    input logic [ROW_W-1:0] row_read_address,
    input logic commit_we,
    input logic [AW-1:0] commit_address,
    input logic [31:0] commit_word,
    output logic read_valid,
    output logic signed [95:0] read_data,
    output logic row_read_valid,
    output logic [P*32-1:0] row_read_data,
    output logic parent_read_valid,
    output logic signed [95:0] parent_read_data,
    output logic parent_busy,parent_done,parent_error
);
    wire parent_host_window=rst_n && host_access && !commit_we && !row_read_req;
    wire parent_load=rst_n && (commit_we || (parent_host_window && load_we));
    // Present simultaneous host load/read to T5b itself: its frozen idle
    // scalar implementation must suppress read-valid when the write wins.
    wire parent_read=parent_host_window && read_en;
    wire [AW-1:0] parent_address=commit_we ? commit_address : host_addr;
    wire signed [31:0] parent_word=$signed(commit_we ? commit_word : write_data);
    genefer_stream27_host_image_ports_v1 #(.AW(AW),.P(P),.ROW_W(ROW_W)) image (
        .clk,.rst_n,.host_access,.load_we,.read_en,.host_addr,.write_data,
        .row_read_req,.row_read_address,.commit_we,.commit_address,.commit_word,
        .read_valid,.read_data,.row_read_valid,.row_read_data
    );
    genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1 #(
        .AW(AW),.NTT_LANES(64)
    ) promoted_t5b (
        .clk,.rst_n,.load_we(parent_load),.read_en(parent_read),.start(1'b0),
        .host_addr(parent_address),.write_data(parent_word),.base(32'd1000000000),.double_bit(1'b0),
        .read_valid(parent_read_valid),.read_data(parent_read_data),
        .busy(parent_busy),.done(parent_done),.error(parent_error),
        .cycles(),.conversion_cycles(),.root_cycles(),.ntt_cycles(),.crt_cycles(),.carry_cycles(),
        .carry_passes(),.profile_cache_valid(),.profile_loads(),.profile_hits(),
        .profile_words_loaded(),.seed_setup_cycles()
    );
endmodule
