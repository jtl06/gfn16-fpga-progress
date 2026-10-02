// Source-only old/new host/setup/canonical/real-RAM pair.
// BOTH compute enable paths retain actual backend child_cancel qualification.
// Standalone image pair below intentionally compares gated old vs raw late kill. External square traffic is not an arithmetic engine.
module genefer_anext_cancel_host_pair_v1 #(parameter int AW=16) (
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
    output logic square_begin,square_double,square_prefilled,square_cancel,
    output logic [31:0] square_base,square_generation,
    output logic [76:0] square_limit,
    output logic [95:0] square_reciprocal,
    input logic square_done,square_error,square_tail_checked,square_root_coherent,
    input logic [31:0] square_out_generation,
    input logic [AW:0] square_coefficients_seen,square_digits_written,
    input logic [5:0] square_patch_words_written,
    input logic compute_configure,compute_clear_image,compute_read_en,compute_write_en,
    input logic [AW-1:0] compute_read_offset,compute_write_offset,compute_read_tag,
    input logic [15:0] compute_read_mask,compute_write_mask,
    input logic compute_read_apply_corrections,
    input logic [511:0] compute_write_words,
    input logic compute_boundary_commit,
    input logic [511:0] compute_boundary_low,compute_boundary_high,
    output logic compute_read_valid,compute_memory_error,
    output logic [AW-1:0] compute_read_tag_out,
    output logic [15:0] compute_read_mask_out,
    output logic [31:0] compute_read_generation,
    output logic [527:0] compute_read_words,
    output logic [511:0] c0_words,c1_words,shadow0_words,shadow1_words,
    output logic [15:0] shadow0_valid,shadow1_valid
,
    input logic [AW-5:0] peek_offset,
    output logic [511:0] old_ram_peek,new_ram_peek,
    output logic shell_pair_mismatch,
    output logic host_begin,host_done,canonical_begin,canonical_done,canonical_read_en,
    output logic old_hw_en,new_hw_en,new_hw_select,
    output logic old_image_write_accept,new_image_write_accept,
    output logic [AW-1:0] old_write_offset,new_write_offset,
    output logic [15:0] old_write_mask,new_write_mask,
    output logic [1:0] old_write_kind,new_write_kind,
    output logic [511:0] old_write_words,new_write_words,
    input logic i_cancel,i_configure,i_clear_image,i_read_en,i_write_en,
    input logic [31:0] i_base,i_generation,
    input logic [AW-1:0] i_read_offset,i_read_tag,i_write_offset,
    input logic [15:0] i_read_mask,i_write_mask,
    input logic i_read_apply_corrections,
    input logic [511:0] i_write_words,
    input logic [1:0] i_write_kind,
    input logic i_clear_corrections,i_set_minus_one,i_boundary_commit,
    input logic [511:0] i_boundary_low_words,i_boundary_high_words,
    output logic i_configured,i_read_valid,i_error,image_pair_mismatch,
    output logic [31:0] i_active_base,i_active_generation,i_read_generation,i_error_generation,
    output logic [15:0] i_read_mask_out,i_shadow0_valid,i_shadow1_valid,
    output logic [AW-1:0] i_read_tag_out,
    output logic [3:0] i_error_code,
    output logic [527:0] i_read_words,
    output logic [511:0] i_c0_words,i_c1_words,i_shadow0_words,i_shadow1_words,
    output logic [511:0] old_i_ram_peek,new_i_ram_peek,
    output logic old_i_write_accept,new_i_write_accept
);
 genefer_track_a4_host_shell_v2 #(.AW(AW)) old (
  .clk,.rst_n,.cmd_valid,.rsp_ready,.cmd_opcode,.cmd_address,.cmd_word,.cmd_base,.cmd_double,.square_done,.square_error,.square_tail_checked,.square_root_coherent,.square_out_generation,.square_coefficients_seen,.square_digits_written,.square_patch_words_written,.compute_configure(compute_configure && !old.square_cancel),.compute_clear_image(compute_clear_image && !old.square_cancel),.compute_read_en(compute_read_en && !old.square_cancel),.compute_write_en(compute_write_en && !old.square_cancel),.compute_read_offset,.compute_write_offset,.compute_read_tag,.compute_read_mask,.compute_write_mask,.compute_read_apply_corrections,.compute_write_words,.compute_boundary_commit(compute_boundary_commit && !old.square_cancel),.compute_boundary_low,.compute_boundary_high,.cmd_ready(),.rsp_valid(),.rsp_error(),.busy(),.fault_sticky(),.image_valid(),.prefill_valid(),.rsp_opcode(),.rsp_word(),.rsp_error_code(),.rsp_generation(),.image_generation(),.square_begin(),.square_double(),.square_prefilled(),.square_cancel(),.square_base(),.square_generation(),.square_limit(),.square_reciprocal(),.compute_read_valid(),.compute_memory_error(),.compute_read_tag_out(),.compute_read_mask_out(),.compute_read_generation(),.compute_read_words(),.c0_words(),.c1_words(),.shadow0_words(),.shadow1_words(),.shadow0_valid(),.shadow1_valid());
 genefer_anext_cancel_host_shell_v1 #(.AW(AW)) actual (
  .clk,.rst_n,.cmd_valid,.rsp_ready,.cmd_opcode,.cmd_address,.cmd_word,.cmd_base,.cmd_double,.square_done,.square_error,.square_tail_checked,.square_root_coherent,.square_out_generation,.square_coefficients_seen,.square_digits_written,.square_patch_words_written,.compute_configure(compute_configure && !actual.square_cancel),.compute_clear_image(compute_clear_image && !actual.square_cancel),.compute_read_en(compute_read_en && !actual.square_cancel),.compute_write_en(compute_write_en && !actual.square_cancel),.compute_read_offset,.compute_write_offset,.compute_read_tag,.compute_read_mask,.compute_write_mask,.compute_read_apply_corrections,.compute_write_words,.compute_boundary_commit(compute_boundary_commit && !actual.square_cancel),.compute_boundary_low,.compute_boundary_high,.cmd_ready,.rsp_valid,.rsp_error,.busy,.fault_sticky,.image_valid,.prefill_valid,.rsp_opcode,.rsp_word,.rsp_error_code,.rsp_generation,.image_generation,.square_begin,.square_double,.square_prefilled,.square_cancel,.square_base,.square_generation,.square_limit,.square_reciprocal,.compute_read_valid,.compute_memory_error,.compute_read_tag_out,.compute_read_mask_out,.compute_read_generation,.compute_read_words,.c0_words,.c1_words,.shadow0_words,.shadow1_words,.shadow0_valid,.shadow1_valid);
 assign host_begin=actual.bus.host_word_begin;assign host_done=actual.bus.host_word_done;
 assign canonical_begin=actual.bus.canonical_begin;assign canonical_done=actual.bus.canonical_done;
 assign canonical_read_en=actual.cr_en;
 assign old_hw_en=old.hw_en;assign new_hw_en=actual.hw_en;
 assign new_hw_select=actual.host_word.mem_write_select;
 assign old_image_write_accept=old.image.write_accept;assign new_image_write_accept=actual.image.write_accept;
 assign old_write_offset=old.write_offset;assign new_write_offset=actual.write_offset;
 assign old_write_mask=old.write_mask;assign new_write_mask=actual.write_mask;
 assign old_write_kind=old.write_kind;assign new_write_kind=actual.write_kind;
 assign old_write_words=old.write_words;assign new_write_words=actual.write_words;
 always_comb begin
  shell_pair_mismatch=old.cmd_ready!=actual.cmd_ready || old.rsp_valid!=actual.rsp_valid || old.rsp_error!=actual.rsp_error || old.busy!=actual.busy || old.fault_sticky!=actual.fault_sticky || old.image_valid!=actual.image_valid || old.prefill_valid!=actual.prefill_valid || old.rsp_opcode!=actual.rsp_opcode || old.rsp_word!=actual.rsp_word || old.rsp_error_code!=actual.rsp_error_code || old.rsp_generation!=actual.rsp_generation || old.image_generation!=actual.image_generation || old.square_begin!=actual.square_begin || old.square_double!=actual.square_double || old.square_prefilled!=actual.square_prefilled || old.square_cancel!=actual.square_cancel || old.square_base!=actual.square_base || old.square_generation!=actual.square_generation || old.square_limit!=actual.square_limit || old.square_reciprocal!=actual.square_reciprocal || old.compute_read_valid!=actual.compute_read_valid || old.compute_memory_error!=actual.compute_memory_error || old.compute_read_tag_out!=actual.compute_read_tag_out || old.compute_read_mask_out!=actual.compute_read_mask_out || old.compute_read_generation!=actual.compute_read_generation || old.c0_words!=actual.c0_words || old.c1_words!=actual.c1_words || old.shadow0_valid!=actual.shadow0_valid || old.shadow1_valid!=actual.shadow1_valid;
  for(int b=0;b<16;b=b+1)begin
   if(compute_read_valid && compute_read_mask_out[b])shell_pair_mismatch=shell_pair_mismatch || old.compute_read_words[33*b+:33]!=actual.compute_read_words[33*b+:33];
   if(shadow0_valid[b])shell_pair_mismatch=shell_pair_mismatch || old.shadow0_words[32*b+:32]!=actual.shadow0_words[32*b+:32];
   if(shadow1_valid[b])shell_pair_mismatch=shell_pair_mismatch || old.shadow1_words[32*b+:32]!=actual.shadow1_words[32*b+:32];
  end
 end
 genefer_track_a4_digit_image_v1 #(.AW(AW)) old_image (
  .clk,.rst_n,.configure(i_configure && !i_cancel),.clear_image(i_clear_image && !i_cancel),.read_en(i_read_en && !i_cancel),.write_en(i_write_en && !i_cancel),.clear_corrections(i_clear_corrections && !i_cancel),.set_minus_one(i_set_minus_one && !i_cancel),.boundary_commit(i_boundary_commit && !i_cancel),.base(i_base),.generation(i_generation),.read_offset(i_read_offset),.read_tag(i_read_tag),.read_mask(i_read_mask),.read_apply_corrections(i_read_apply_corrections),.write_offset(i_write_offset),.write_mask(i_write_mask),.write_words(i_write_words),.write_kind(i_write_kind),.boundary_low_words(i_boundary_low_words),.boundary_high_words(i_boundary_high_words),.configured(),.active_base(),.active_generation(),.read_valid(),.read_mask_out(),.read_tag_out(),.read_generation(),.read_words(),.error(),.error_code(),.error_generation(),.c0_words(),.c1_words(),.shadow0_words(),.shadow1_words(),.shadow0_valid(),.shadow1_valid());
 genefer_anext_cancel_digit_image_v1 #(.AW(AW)) late_image (
  .clk,.rst_n,.cancel(i_cancel),.configure(i_configure),.clear_image(i_clear_image),.read_en(i_read_en),.write_en(i_write_en),.clear_corrections(i_clear_corrections),.set_minus_one(i_set_minus_one),.boundary_commit(i_boundary_commit),.base(i_base),.generation(i_generation),.read_offset(i_read_offset),.read_tag(i_read_tag),.read_mask(i_read_mask),.read_apply_corrections(i_read_apply_corrections),.write_offset(i_write_offset),.write_mask(i_write_mask),.write_words(i_write_words),.write_kind(i_write_kind),.boundary_low_words(i_boundary_low_words),.boundary_high_words(i_boundary_high_words),.configured(i_configured),.active_base(i_active_base),.active_generation(i_active_generation),.read_valid(i_read_valid),.read_mask_out(i_read_mask_out),.read_tag_out(i_read_tag_out),.read_generation(i_read_generation),.read_words(i_read_words),.error(i_error),.error_code(i_error_code),.error_generation(i_error_generation),.c0_words(i_c0_words),.c1_words(i_c1_words),.shadow0_words(i_shadow0_words),.shadow1_words(i_shadow1_words),.shadow0_valid(i_shadow0_valid),.shadow1_valid(i_shadow1_valid));
 always_comb begin
  image_pair_mismatch=old_image.configured!=late_image.configured || old_image.active_base!=late_image.active_base || old_image.active_generation!=late_image.active_generation || old_image.read_valid!=late_image.read_valid || old_image.read_mask_out!=late_image.read_mask_out || old_image.read_tag_out!=late_image.read_tag_out || old_image.read_generation!=late_image.read_generation || old_image.error!=late_image.error || old_image.error_code!=late_image.error_code || old_image.error_generation!=late_image.error_generation || old_image.c0_words!=late_image.c0_words || old_image.c1_words!=late_image.c1_words || old_image.shadow0_valid!=late_image.shadow0_valid || old_image.shadow1_valid!=late_image.shadow1_valid;
  for(int b=0;b<16;b=b+1)begin
   if(i_read_valid && i_read_mask_out[b])image_pair_mismatch=image_pair_mismatch || old_image.read_words[33*b+:33]!=late_image.read_words[33*b+:33];
   if(i_shadow0_valid[b])image_pair_mismatch=image_pair_mismatch || old_image.shadow0_words[32*b+:32]!=late_image.shadow0_words[32*b+:32];
   if(i_shadow1_valid[b])image_pair_mismatch=image_pair_mismatch || old_image.shadow1_words[32*b+:32]!=late_image.shadow1_words[32*b+:32];
  end
 end
 assign old_i_write_accept=old_image.write_accept;assign new_i_write_accept=late_image.write_accept;
 for(genvar b=0;b<16;b=b+1)begin: peek
  assign old_ram_peek[32*b+:32]=old.image.banks[b].ram.mem[peek_offset];
  assign new_ram_peek[32*b+:32]=actual.image.banks[b].ram.mem[peek_offset];
  assign old_i_ram_peek[32*b+:32]=old_image.banks[b].ram.mem[peek_offset];
  assign new_i_ram_peek[32*b+:32]=late_image.banks[b].ram.mem[peek_offset];
 end
endmodule
