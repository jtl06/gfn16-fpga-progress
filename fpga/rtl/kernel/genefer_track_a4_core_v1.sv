// Exploratory executable integration: host protocol + real three-field NTT +
// CRT/block carry/patched prefill. Not a promoted whole-core implementation.
module genefer_track_a4_core_v1 #(parameter int AW=16) (
    input logic clk,rst_n,cmd_valid,rsp_ready,
    input logic [2:0] cmd_opcode,
    input logic [AW-1:0] cmd_address,
    input logic signed [31:0] cmd_word,
    input logic [31:0] cmd_base,
    input logic cmd_double,
    output logic cmd_ready,rsp_valid,rsp_error,busy,fault_sticky,image_valid,prefill_valid,
    output logic [2:0] rsp_opcode,
    output logic signed [31:0] rsp_word,
    output logic [7:0] rsp_error_code,
    output logic [31:0] rsp_generation,image_generation,
    output logic [63:0] square_cycles,prefill_cycles,ntt_cycles,root_cycles,post_cycles,seed_setup_cycles,
    output logic profile_loads,profile_hits
);
    logic square_begin,square_double,square_prefilled,square_cancel;
    logic [31:0] square_base,square_generation;
    logic [76:0] square_limit;
    logic [95:0] square_reciprocal;
    logic square_busy,square_done,square_error,square_tail_checked,square_root_coherent;
    logic [31:0] square_out_generation;
    logic [AW:0] square_coefficients_seen,square_digits_written;
    logic [5:0] square_patch_words_written;
    logic compute_configure,compute_clear_image,compute_read_en,compute_write_en;
    logic [AW-1:0] compute_read_offset,compute_write_offset,compute_read_tag;
    logic [15:0] compute_read_mask,compute_write_mask;
    logic compute_read_apply_corrections;
    logic [511:0] compute_write_words;
    logic compute_boundary_commit;
    logic [511:0] compute_boundary_low,compute_boundary_high;
    logic compute_read_valid,compute_memory_error;
    logic [AW-1:0] compute_read_tag_out;
    logic [15:0] compute_read_mask_out;
    logic [31:0] compute_read_generation;
    logic [527:0] compute_read_words;
    logic [511:0] c0_words,c1_words,shadow0_words,shadow1_words;
    logic [15:0] shadow0_valid,shadow1_valid;
    genefer_track_a4_host_shell_v2 #(.AW(AW)) host (
        .clk,.rst_n,.cmd_valid,.rsp_ready,.cmd_opcode,.cmd_address,.cmd_word,.cmd_base,.cmd_double,
        .cmd_ready,.rsp_valid,.rsp_error,.busy,.fault_sticky,.image_valid,.prefill_valid,
        .rsp_opcode,.rsp_word,.rsp_error_code,.rsp_generation,.image_generation,
        .square_begin,.square_double,.square_prefilled,.square_cancel,.square_base,.square_generation,.square_limit,.square_reciprocal,
        .square_done,.square_error,.square_tail_checked,.square_root_coherent,.square_out_generation,
        .square_coefficients_seen,.square_digits_written,.square_patch_words_written,
        .compute_configure,.compute_clear_image,.compute_read_en,.compute_write_en,
        .compute_read_offset,.compute_write_offset,.compute_read_tag,.compute_read_mask,.compute_write_mask,
        .compute_read_apply_corrections,.compute_write_words,.compute_boundary_commit,.compute_boundary_low,.compute_boundary_high,
        .compute_read_valid,.compute_memory_error,.compute_read_tag_out,.compute_read_mask_out,.compute_read_generation,.compute_read_words,
        .c0_words,.c1_words,.shadow0_words,.shadow1_words,.shadow0_valid,.shadow1_valid
    );
    genefer_track_a4_square_backend_v1 #(.AW(AW)) square_backend (
        .clk,.rst_n,.begin_square(square_begin),.cancel(square_cancel),.double_bit(square_double),.prefilled(square_prefilled),
        .base(square_base),.generation(square_generation),.coefficient_limit(square_limit),.reciprocal(square_reciprocal),
        .busy(square_busy),.done(square_done),.error(square_error),.tail_checked(square_tail_checked),.root_coherent(square_root_coherent),
        .out_generation(square_out_generation),.coefficients_seen(square_coefficients_seen),.digits_written(square_digits_written),
        .patch_words_written(square_patch_words_written),.cycles(square_cycles),.prefill_cycles,.ntt_cycles,.root_cycles,.post_cycles,.seed_setup_cycles,
        .profile_loads,.profile_hits,
        .compute_configure,.compute_clear_image,.compute_read_en,.compute_write_en,
        .compute_read_offset,.compute_write_offset,.compute_read_tag,.compute_read_mask,.compute_write_mask,
        .compute_read_apply_corrections,.compute_write_words,.compute_boundary_commit,.compute_boundary_low,.compute_boundary_high,
        .compute_read_valid,.compute_memory_error,.compute_read_tag_out,.compute_read_mask_out,.compute_read_generation,.compute_read_words,
        .c0_words,.c1_words,.shadow0_words,.shadow1_words,.shadow0_valid,.shadow1_valid
    );
endmodule
