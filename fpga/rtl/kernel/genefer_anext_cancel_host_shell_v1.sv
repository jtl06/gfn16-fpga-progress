// EARLY EXECUTABLE INTEGRATION SHELL. Real setup/canonical/host/control path;
// square service and its RAM traffic are explicit ports awaiting whole64 binding.
// This shell must not be reported as an end-to-end NTT square implementation.
module genefer_anext_cancel_host_shell_v1 #(parameter int AW=16) (
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
);
    genefer_track_a4_control_contract_v1 #(.AW(AW)) bus(.clk,.rst_n);
    assign bus.cmd_valid=cmd_valid;assign bus.cmd_opcode=cmd_opcode;assign bus.cmd_address=cmd_address;
    assign bus.cmd_word=cmd_word;assign bus.cmd_base=cmd_base;assign bus.cmd_double=cmd_double;assign bus.rsp_ready=rsp_ready;
    assign cmd_ready=bus.cmd_ready;assign rsp_valid=bus.rsp_valid;assign rsp_error=bus.rsp_error;
    assign rsp_opcode=bus.rsp_opcode;assign rsp_word=bus.rsp_word;assign rsp_error_code=bus.rsp_error_code;
    assign rsp_generation=bus.rsp_generation;assign image_generation=bus.image_generation;
    assign busy=bus.busy;assign fault_sticky=bus.fault_sticky;assign image_valid=bus.image_valid;assign prefill_valid=bus.prefill_valid;
    assign square_begin=bus.square_begin;assign square_double=bus.square_double;assign square_prefilled=bus.square_prefilled;
    assign square_base=bus.square_base;assign square_generation=bus.square_generation;
    assign square_limit=bus.square_coefficient_limit;assign square_reciprocal=bus.square_reciprocal;assign square_cancel=bus.cancel;
    assign bus.square_done=square_done;assign bus.square_error=square_error;assign bus.square_out_generation=square_out_generation;
    assign bus.square_coefficients_seen=square_coefficients_seen;assign bus.square_digits_written=square_digits_written;
    assign bus.square_patch_words_written=square_patch_words_written;
    assign bus.square_registered_child_tail_checked=square_tail_checked;assign bus.square_root_profile_coherent=square_root_coherent;
    genefer_track_a4_control_fsm_v2 #(.AW(AW)) control(bus);
    logic [2:0] accepted_opcode;
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)accepted_opcode<=0;
        else if(cmd_valid && cmd_ready)accepted_opcode<=cmd_opcode;
    end
    logic setup_busy,setup_valid;
    logic [31:0] setup_base_out;
    genefer_track_a4_setup_v1 #(.AW(AW)) setup_unit (
        .clk,.rst_n,.begin_setup(bus.setup_begin),.cancel(bus.cancel),.base(bus.setup_base),.generation(bus.setup_generation),
        .busy(setup_busy),.done(bus.setup_done),.error(bus.setup_error),.config_valid(setup_valid),
        .accepted_base(setup_base_out),.out_generation(bus.setup_out_generation),
        .coefficient_limit(bus.setup_coefficient_limit),.reciprocal(bus.setup_reciprocal)
    );
    logic cr_en,cr_corr,cr_valid,canonical_busy;
    logic [AW-1:0] cr_address,cw_offset;
    logic [31:0] cr_generation;
    logic [15:0] cw_mask;
    logic [511:0] cw_words;
    logic clear_corrections,set_minus_one;
    logic [3:0] canonical_error_code;
    logic hr_en,hw_en,hw_select;
    logic [AW-1:0] h_offset,h_tag;
    logic [15:0] h_mask;
    logic [511:0] h_words;
    logic [31:0] h_generation;
    logic mr_valid,image_error,arbitration_error,configured;
    logic [AW-1:0] mr_tag;
    logic [15:0] mr_mask;
    logic [31:0] mr_generation,active_base,active_generation,error_generation;
    logic [527:0] mr_words;
    logic [3:0] image_error_code;
    wire [3:0] canonical_bank=4'(cr_address>>(AW-4));
    logic [3:0] canonical_bank_d;
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)canonical_bank_d<=0;else if(cr_en)canonical_bank_d<=canonical_bank;
    end
    assign cr_valid=mr_valid && canonical_busy;
    genefer_track_a4_canonical_controller_v2 #(.AW(AW)) canonicalizer (
        .clk,.rst_n,.begin_canonical(bus.canonical_begin),.cancel(bus.cancel),.base(bus.canonical_base),.generation(bus.canonical_generation),
        .busy(canonical_busy),.done(bus.canonical_done),.error(bus.canonical_error),.minus_one(bus.canonical_minus_one),
        .error_code(canonical_error_code),.out_generation(bus.canonical_out_generation),.max_digit(bus.canonical_max_digit),
        .passes(bus.canonical_passes),.mem_read_en(cr_en),.mem_read_apply_corrections(cr_corr),.mem_read_address(cr_address),
        .mem_generation(cr_generation),.mem_read_valid(cr_valid),.mem_error(image_error || arbitration_error),
        .mem_read_value($signed(mr_words[int'(canonical_bank_d)*33+:33])),.mem_read_tag(mr_tag),.mem_read_generation(mr_generation),
        .mem_write_mask(cw_mask),.mem_write_offset(cw_offset),.mem_write_words(cw_words),
        .clear_corrections,.set_minus_one,.registered_child_tail_checked(bus.canonical_registered_child_tail_checked)
    );
    genefer_anext_cancel_host_word_v1 #(.AW(AW)) host_word (
        .clk,.rst_n,.begin_word(bus.host_word_begin),.cancel(bus.cancel),.write_word(bus.host_word_write),
        .address(bus.host_word_address),.write_data(bus.host_word_write_data),.generation(bus.host_word_generation),
        .done(bus.host_word_done),.error(bus.host_word_error),.read_data(bus.host_word_read_data),.out_generation(bus.host_word_out_generation),
        .mem_read_en(hr_en),.mem_write_en(hw_en),.mem_write_select(hw_select),.mem_offset(h_offset),.mem_tag(h_tag),.mem_mask(h_mask),
        .mem_write_words(h_words),.mem_generation(h_generation),.mem_error(image_error || arbitration_error),
        .mem_read_valid(mr_valid),.mem_read_tag(mr_tag),.mem_read_mask(mr_mask),.mem_read_generation(mr_generation),.mem_read_words(mr_words)
    );
    wire configure=bus.setup_begin || bus.canonical_begin || bus.host_word_begin || bus.square_begin || compute_configure;
    wire [31:0] config_base=bus.setup_begin ? bus.setup_base : bus.square_base;
    wire [31:0] memory_generation=bus.setup_begin ? bus.setup_generation : bus.square_generation;
    wire clear_image=(bus.setup_begin && accepted_opcode==bus.RELOAD_BEGIN) ||
        (bus.square_begin && bus.square_prefilled) || (compute_configure && compute_clear_image);
    wire multiple_reads=(cr_en && hr_en) || (cr_en && compute_read_en) || (hr_en && compute_read_en);
    wire multiple_writes=((|cw_mask) && hw_select) || ((|cw_mask) && compute_write_en) || (hw_select && compute_write_en);
    wire arbitration_fault=multiple_reads || multiple_writes;
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)arbitration_error<=0;else arbitration_error<=arbitration_fault && !bus.cancel;
    end
    wire read_enable=(cr_en || hr_en || compute_read_en) && !arbitration_fault;
    wire write_enable=((|cw_mask) || hw_select || compute_write_en) && !arbitration_fault;
    wire [AW-1:0] read_offset=cr_en ? AW'(32'(cr_address)&32'((1<<(AW-4))-1)) : hr_en ? h_offset : compute_read_offset;
    wire [AW-1:0] read_tag=cr_en ? cr_address : hr_en ? h_tag : compute_read_tag;
    wire [15:0] read_mask=cr_en ? (16'd1<<canonical_bank) : hr_en ? h_mask : compute_read_mask;
    wire read_corrections=cr_en ? cr_corr : hr_en ? 1'b1 : compute_read_apply_corrections;
    wire [AW-1:0] write_offset=(|cw_mask) ? cw_offset : hw_select ? h_offset : compute_write_offset;
    wire [15:0] write_mask=(|cw_mask) ? cw_mask : hw_select ? h_mask : compute_write_mask;
    wire [511:0] write_words=(|cw_mask) ? cw_words : hw_select ? h_words : compute_write_words;
    wire [1:0] write_kind=(|cw_mask) ? 2'd1 : hw_select ? 2'd2 : 2'd0;
    genefer_anext_cancel_digit_image_v1 #(.AW(AW)) image (
        .clk,.rst_n,.cancel(bus.cancel),.configure,.clear_image,.base(config_base),.generation(memory_generation),
        .configured,.active_base,.active_generation,
        .read_en(read_enable),.read_offset,.read_mask,.read_apply_corrections(read_corrections),.read_tag,
        .write_en(write_enable),.write_offset,.write_mask,.write_words,.write_kind,
        .read_valid(mr_valid),.read_mask_out(mr_mask),.read_tag_out(mr_tag),.read_generation(mr_generation),.read_words(mr_words),
        .error(image_error),.error_code(image_error_code),.error_generation,
        .clear_corrections,.set_minus_one,.boundary_commit(compute_boundary_commit),
        .boundary_low_words(compute_boundary_low),.boundary_high_words(compute_boundary_high),
        .c0_words,.c1_words,.shadow0_words,.shadow1_words,.shadow0_valid,.shadow1_valid
    );
    assign bus.registered_child_fault=image_error || arbitration_error;
    assign compute_read_valid=mr_valid && accepted_opcode==bus.SQUARE;
    assign compute_memory_error=image_error || arbitration_error;
    assign compute_read_tag_out=mr_tag;assign compute_read_mask_out=mr_mask;
    assign compute_read_generation=mr_generation;assign compute_read_words=mr_words;
endmodule
