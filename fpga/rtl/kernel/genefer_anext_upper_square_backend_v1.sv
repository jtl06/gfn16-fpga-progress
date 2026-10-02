// Exploratory real square assembly. Frozen arithmetic components are unchanged.
// r13 adds explicit field request/write/return transfers and image destinations.
// No whole-square latency or fit claim until native evidence closes this shell.
module genefer_anext_upper_square_backend_v1 #(parameter int AW=16) (
    input logic clk,rst_n,begin_square,cancel,double_bit,prefilled,
    input logic [31:0] base,generation,
    input logic [76:0] coefficient_limit,
    input logic [95:0] reciprocal,
    output logic busy,done,error,tail_checked,root_coherent,
    output logic [31:0] out_generation,
    output logic [AW:0] coefficients_seen,digits_written,
    output logic [5:0] patch_words_written,
    output logic [63:0] cycles,prefill_cycles,ntt_cycles,root_cycles,post_cycles,seed_setup_cycles,
    output logic profile_loads,profile_hits,
    output logic compute_configure,compute_clear_image,compute_read_en,compute_write_en,
    output logic [AW-1:0] compute_read_offset,compute_write_offset,compute_read_tag,
    output logic [15:0] compute_read_mask,compute_write_mask,
    output logic compute_read_apply_corrections,
    output logic [511:0] compute_write_words,
    output logic compute_boundary_commit,
    output logic [511:0] compute_boundary_low,compute_boundary_high,
    input logic compute_read_valid,compute_memory_error,
    input logic [AW-1:0] compute_read_tag_out,
    input logic [15:0] compute_read_mask_out,
    input logic [31:0] compute_read_generation,
    input logic [527:0] compute_read_words,
    input logic [511:0] c0_words,c1_words,shadow0_words,shadow1_words,
    input logic [15:0] shadow0_valid,shadow1_valid
);
    typedef enum logic [3:0] {IDLE,COLD_START,COLD_WAIT,NTT_START,NTT_WAIT,POST_WAIT,DRAIN,CHECK,FAILED,NTT_LAUNCH} state_t;
    state_t state;
    logic was_prefilled;
    logic [31:0] base_reg,generation_reg;
    logic prefill_busy,prefill_done,prefill_error,prefill_write;
    logic [63:0] cold_cycles;
    logic [AW-1:0] prefill_offset;
    logic [15:0] prefill_mask;
    logic [1535:0] prefill_words;
    logic seq_ready,seq_busy,seq_done,seq_error,cache_valid;
    logic [15:0] profile_words;
    logic [63:0] seq_cycles;
    logic post_ready,post_busy,post_done,post_error,post_tail;
    logic [7:0] post_error_code;
    logic post_read,post_write,post_image_write,post_boundary;
    logic [AW-1:0] post_read_offset,post_write_offset,post_image_offset;
    logic [15:0] post_read_mask,post_write_mask,post_image_mask;
    logic [1535:0] post_write_words;
    logic [511:0] post_image_words,post_low,post_high;
    logic transfer_busy,transfer_quiet,transfer_error;
    logic field_read,field_write,field_error;
    logic [AW-1:0] field_read_offset,field_write_offset;
    logic [15:0] field_read_mask,field_write_mask;
    logic [1535:0] field_write_words,raw_read_words,returned_words;
    logic [2:0] raw_read_valid,returned_valid;
    logic [47:0] raw_read_masks,returned_masks;
    logic [3*AW-1:0] raw_read_offsets,returned_offsets;
    logic [1:0] image_write_valid,image_boundary_valid;
    logic [AW-1:0] image_source_offset,image_destination_offset;
    logic [15:0] image_source_mask,image_destination_mask;
    logic [511:0] image_source_words,image_destination_words,low_source,low_destination,high_source,high_destination;
    // Starts depend on registered child errors, never child combinational valid.
    // Reject both source requests on ownership/conflict violation; already
    // accepted destination tokens are proposals until the final CHECK edge.
    logic admission_error;
    // r17: one registered admission edge isolates raw image legality from
    // start's global field-RAM gate. Owned by this operation's latched config.
    (* preserve, dont_merge *) logic ntt_admission;
    wire prefill_owner=state==COLD_WAIT;
    wire post_owner=state==POST_WAIT;
    wire raw_admission_fault=(prefill_write && !prefill_owner) ||
        (post_write && !post_owner) ||
        (post_read && state!=NTT_WAIT && state!=POST_WAIT);
    wire admitted_read=post_read && !raw_admission_fault;
    wire admitted_write=(prefill_write || post_write) && !raw_admission_fault;
    wire child_cancel=cancel || state==FAILED;
    wire fault=seq_error || post_error || prefill_error || transfer_error || compute_memory_error ||
        (begin_square && state!=IDLE) || admission_error;
    assign busy=state!=IDLE && state!=FAILED;
    assign prefill_cycles=was_prefilled ? 64'd0 : cold_cycles;
    assign compute_read_apply_corrections=1'b1;
    assign compute_configure=start_ntt && !was_prefilled;
    assign compute_clear_image=1'b1;
    wire admit_ntt=state==NTT_START && seq_ready && transfer_quiet && !fault && !cancel;
    // No transfer_quiet, seq_ready, raw child valid or raw admission fault here.
    wire start_ntt=ntt_admission && !fault && !cancel;
    wire start_post=state==NTT_WAIT && seq_done && post_ready && !fault && !cancel;
    genefer_track_a4_cold_prefill_v1 #(.AW(AW)) cold_prefill (
        .clk,.rst_n,.cancel(child_cancel),.begin_prefill(state==COLD_START),.base(base_reg),.generation(generation_reg),
        .busy(prefill_busy),.done(prefill_done),.error(prefill_error),.cycles(cold_cycles),
        .image_read_en(compute_read_en),.image_read_offset(compute_read_offset),.image_read_tag(compute_read_tag),
        .image_read_mask(compute_read_mask),.image_read_valid(compute_read_valid),.image_error(compute_memory_error),
        .image_read_tag_out(compute_read_tag_out),.image_read_mask_out(compute_read_mask_out),
        .image_read_generation(compute_read_generation),.image_read_words(compute_read_words),
        .field_write_en(prefill_write),.field_write_offset(prefill_offset),.field_write_mask(prefill_mask),
        .field_write_words(prefill_words),.transfer_quiet,.transfer_error
    );
    genefer_track_a4_field_transfer_v2 #(.AW(AW)) transfers (
        .clk,.rst_n,.cancel(child_cancel),.read_en(admitted_read),.write_en(admitted_write),
        .read_offset(post_read_offset),.write_offset(prefill_write ? prefill_offset : post_write_offset),
        .read_mask(post_read_mask),.write_mask(prefill_write ? prefill_mask : post_write_mask),
        .write_words(prefill_write ? prefill_words : post_write_words),
        .read_valid(returned_valid),.read_masks(returned_masks),.read_offsets(returned_offsets),.read_words(returned_words),
        .busy(transfer_busy),.quiet(transfer_quiet),.error(transfer_error),
        .field_read_en(field_read),.field_write_en(field_write),.field_read_offset,.field_write_offset,
        .field_read_mask,.field_write_mask,.field_write_words,
        .field_read_valid(raw_read_valid),.field_read_masks(raw_read_masks),.field_read_offsets(raw_read_offsets),
        .field_read_words(raw_read_words),.field_error
    );
    genefer_anext_upper_ntt_sequencer_v1 #(.AW(AW)) sequencer (
        .clk,.rst_n,.cancel(child_cancel),.start_ntt,.ready(seq_ready),.busy(seq_busy),.done(seq_done),.error(seq_error),
        .profile_cache_valid(cache_valid),.profile_coherent(root_coherent),.cycles(seq_cycles),.ntt_cycles,.root_cycles,
        .seed_setup_cycles,.profile_loads,.profile_hits,.profile_words_loaded(profile_words),
        .block_read_en(field_read),.block_write_en(field_write),.block_read_offset(field_read_offset),
        .block_write_offset(field_write_offset),.block_read_mask(field_read_mask),.block_write_mask(field_write_mask),
        .block_write_words(field_write_words),.block_read_valid(raw_read_valid),.block_read_masks(raw_read_masks),
        .block_read_offsets(raw_read_offsets),.block_read_words(raw_read_words),.block_error(field_error)
    );
    genefer_track_a4_post_ntt_v1 #(.AW(AW)) post_ntt (
        .clk,.rst_n,.prepare(begin_square && state==IDLE),.start_post,.cancel(child_cancel),.double_bit,.base,.generation,
        .coefficient_limit,.reciprocal,.ready(post_ready),.busy(post_busy),.done(post_done),.error(post_error),
        .tail_checked(post_tail),.error_code(post_error_code),.out_generation,.cycles(post_cycles),
        .coefficients_seen,.digits_written,.patch_words_written,
        .field_read_en(post_read),.field_write_en(post_write),.field_read_offset(post_read_offset),
        .field_write_offset(post_write_offset),.field_read_mask(post_read_mask),.field_write_mask(post_write_mask),
        .field_write_words(post_write_words),.field_read_valid(returned_valid),.field_read_masks(returned_masks),
        .field_read_offsets(returned_offsets),.field_read_words(returned_words),.field_error(transfer_error),
        .image_error(compute_memory_error),.image_write_en(post_image_write),.image_boundary_commit(post_boundary),
        .image_write_offset(post_image_offset),.image_write_mask(post_image_mask),.image_write_words(post_image_words),
        .boundary_low_words(post_low),.boundary_high_words(post_high),
        .shadow0_words,.shadow1_words,.c0_words,.c1_words,.shadow0_valid,.shadow1_valid
    );
    assign compute_write_en=image_write_valid[1] && !fault && !child_cancel;
    assign compute_boundary_commit=image_boundary_valid[1] && !fault && !child_cancel;
    assign compute_write_offset=image_destination_offset;
    assign compute_write_mask=image_destination_mask;
    assign compute_write_words=image_destination_words;
    assign compute_boundary_low=low_destination;
    assign compute_boundary_high=high_destination;
    always_ff @(posedge clk)if(rst_n && !child_cancel && !fault)begin
        if(post_image_write)begin image_source_words<=post_image_words;image_source_offset<=post_image_offset;image_source_mask<=post_image_mask;end
        if(image_write_valid[0])begin image_destination_words<=image_source_words;image_destination_offset<=image_source_offset;image_destination_mask<=image_source_mask;end
        if(post_boundary)begin low_source<=post_low;high_source<=post_high;end
        if(image_boundary_valid[0])begin low_destination<=low_source;high_destination<=high_source;end
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;done<=0;error<=0;tail_checked<=0;cycles<=0;base_reg<=0;generation_reg<=0;was_prefilled<=0;
            image_write_valid<=0;image_boundary_valid<=0;admission_error<=0;ntt_admission<=0;
        end else begin
            done<=0;ntt_admission<=0;
            if(raw_admission_fault)admission_error<=1;
            image_write_valid<={image_write_valid[0],post_image_write};
            image_boundary_valid<={image_boundary_valid[0],post_boundary};
            if(busy)cycles<=cycles+1'b1;
            case(state)
                IDLE:if(begin_square)begin
                    state<=prefilled ? NTT_START : COLD_START;base_reg<=base;generation_reg<=generation;was_prefilled<=prefilled;
                    cycles<=0;error<=0;tail_checked<=0;
                end
                COLD_START:state<=COLD_WAIT;
                COLD_WAIT:if(prefill_done)state<=NTT_START;
                NTT_START:if(admit_ntt)begin ntt_admission<=1;state<=NTT_LAUNCH;end
                NTT_LAUNCH:if(start_ntt)state<=NTT_WAIT;
                NTT_WAIT:if(seq_done)begin
                    if(!post_ready || !root_coherent)begin state<=FAILED;error<=1;end
                    else state<=POST_WAIT;
                end
                POST_WAIT:if(post_done)state<=DRAIN;
                DRAIN:if(transfer_quiet && !(|image_write_valid) && !(|image_boundary_valid))state<=CHECK;
                CHECK:begin
                    if(!post_tail || !root_coherent || out_generation!=generation_reg || !transfer_quiet ||
                        int'(coefficients_seen)!=(1<<AW) || int'(digits_written)!=(1<<AW) || patch_words_written!=6'd32)
                        begin state<=FAILED;error<=1;end
                    else begin state<=IDLE;done<=1;tail_checked<=1;end
                end
                default:;
            endcase
            if(fault || raw_admission_fault)begin ntt_admission<=0;state<=FAILED;error<=1;done<=0;tail_checked<=0;image_write_valid<=0;image_boundary_valid<=0;end
            if(cancel)begin admission_error<=0;ntt_admission<=0;state<=IDLE;done<=0;error<=0;tail_checked<=0;image_write_valid<=0;image_boundary_valid<=0;end
        end
    end
endmodule
