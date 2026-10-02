// Source-only small real-RAM block acceptance probe with an actual E1 sink.
// No new arithmetic architecture; native qualification is a separate gate.
module genefer_anext_pointdata27_block_probe_v1 #(
    parameter int AW=5,
    parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
) (
    input logic clk,rst_n,
    input logic legacy_load_we,legacy_read_en,legacy_vector_load_we,legacy_vector_read_en,
    input logic block_external_conflict,block_read_en,block_write_en,
    input logic [AW-1:0] block_read_offset,block_write_offset,
    input logic [15:0] block_read_mask,block_write_mask,
    input logic [511:0] block_write_words,
    output logic block_read_valid,block_error,
    output logic [AW-1:0] block_read_offset_out,
    output logic [15:0] block_read_mask_out,
    output logic [511:0] block_read_words,
    output logic consumed_valid,
    output logic [AW-1:0] consumed_offset,
    output logic [15:0] consumed_mask,
    output logic [511:0] consumed_words,
    input logic profile_begin,profile_we,profile_commit,profile_abort,
    input logic [4:0] profile_size_log2,
    input logic [31:0] profile_modulus,profile_data,
    input logic [7:0] profile_format,
    input logic [15:0] profile_addr,
    output logic profile_loaded,profile_loading,profile_error,
    output logic [31:0] profile_epoch,
    input logic start,inverse,dif,
    input logic [1:0] root_phase,op,
    input logic [4:0] size_log2,
    input logic [31:0] scale,
    output logic busy,done,error,legacy_read_valid,legacy_vector_read_valid,
    output logic [63:0] cycles
);
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin consumed_valid<=0;consumed_mask<=0;consumed_offset<=0;end
        else begin
            consumed_valid<=block_read_valid;
            if(block_read_valid)begin
                consumed_offset<=block_read_offset_out;consumed_mask<=block_read_mask_out;
                consumed_words<=block_read_words;
            end
        end
    end
    genefer_anext_pointdata27_block_engine_v1 #(.AW(AW),.LANES(64),.P(P),.Q(Q)) engine (
        .clk,.rst_n,.load_we(legacy_load_we),.read_en(legacy_read_en),
        .host_addr({AW{1'b0}}),.write_data(P-32'd1),.read_valid(legacy_read_valid),.read_data(),
        .vector_load_we(legacy_vector_load_we),.vector_read_en(legacy_vector_read_en),
        .vector_addr({AW{1'b0}}),.vector_lane_mask(64'hffffffffffffffff),
        .vector_write_data({64{P-32'd1}}),.vector_read_valid(legacy_vector_read_valid),
        .host_error(),.vector_read_mask(),.vector_read_data(),
        .block_external_conflict,.block_read_en,.block_write_en,
        .block_read_offset,.block_write_offset,.block_read_mask,.block_write_mask,.block_write_words,
        .block_read_valid,.block_error,.block_read_offset_out,.block_read_mask_out,.block_read_words,
        .profile_begin,.profile_we,.profile_commit,.profile_abort,.profile_size_log2,.profile_modulus,
        .profile_data,.profile_format,.profile_addr,.profile_loaded,.profile_loading,.profile_error,
        .profile_loaded_size(),.profile_next_addr(),.seed_setup_cycles(),.root_rom_reads(),
        .normalization_products(),.profile_epoch,
        .start,.inverse,.dif,.root_phase,.op,.size_log2,.scale,.busy,.done,.error,
        .cycles,.butterflies(),.data_reads(),.data_writes(),.root_reads(),.wait_cycles()
    );
endmodule
