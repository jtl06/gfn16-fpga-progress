// Bounded component-only reset probe: actual transfer, routes, 384 SDP RAMs,
// sparse Montgomery leaves and fixed profile ROMs. No NTT/sequencer clone.
// Transfer cancel is the frozen synchronous full-clock contract. `failed`
// represents registered terminal quarantine, not leaf reset-ready. Subcycle
// assertion is safe to claim only when that transfer is quiet; an injected
// pending-transfer subcycle pulse must instead produce protocol quarantine.
module genefer_anext_field_reset_probe_v1 #(parameter int AW=5) (
    input logic clk,rst_n,cancel,failed,
    input logic transfer_read_en,transfer_write_en,
    input logic [AW-1:0] read_offset,write_offset,
    input logic [15:0] read_mask,write_mask,
    input logic [1535:0] write_words,
    input logic [31:0] generation,
    input logic direct_start,direct_mult_valid,
    input logic [95:0] mult_lhs,mult_rhs,
    input logic sim_bad_response_tag,sim_drop_response,
    input logic sim_bad_generation,sim_early_ready,sim_stale_valid,
    output logic [2:0] field_rst_n,field_allow,physical_read,physical_write,
    output logic reset_ready,kill,outer_fault,transfer_error,transfer_busy,transfer_quiet,
    output logic accepted_transfer_read,accepted_transfer_write,
    output logic [2:0] accepted_start,accepted_mult,
    output logic [2:0] caller_valid,
    output logic [47:0] caller_masks,
    output logic [3*AW-1:0] caller_offsets,
    output logic [1535:0] caller_words,
    output logic [31:0] caller_generation,
    output logic [2:0] mult_valid,rom_busy,rom_done,rom_valid,profile_loaded,
    output logic [95:0] mult_results,rom_words,profile_generations,
    output logic [47:0] rom_addresses,
    output logic [8:0] profile_counts
);
    localparam int RW=AW>7 ? AW-7 : 1;
    logic actual_ready;
    genefer_anext_field_reset_release_v1 reset_release (
        .clk,.rst_n,.cancel,.failed(failed || outer_fault),
        .field_rst_n,.field_allow,.ready(actual_ready),.kill
    );
    assign reset_ready=actual_ready || (sim_early_ready && rst_n && !cancel && !failed && !outer_fault);
    // Deliberately independent of field reset: a genuine transfer error cannot
    // disappear when its destination leaves are asynchronously cleared.
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)outer_fault<=0;
        else if(transfer_error)outer_fault<=1;
    end
    // Observe actual frozen source admission, including its response checker;
    // no delayed reset-ready gate is inserted on the first legal E0 request.
    assign accepted_transfer_read=transfer_read_en && !kill && !outer_fault && !transfer_error && !transfer.protocol_fault;
    assign accepted_transfer_write=transfer_write_en && !kill && !outer_fault && !transfer_error && !transfer.protocol_fault;
    logic field_read_en,field_write_en;
    logic [AW-1:0] field_read_offset,field_write_offset;
    logic [15:0] field_read_mask,field_write_mask;
    logic [1535:0] field_write_words,raw_field_words,transfer_words;
    logic [2:0] raw_field_valid,transfer_valid,route_errors;
    logic [47:0] raw_field_masks,transfer_masks;
    logic [3*AW-1:0] raw_field_offsets,transfer_offsets,injected_offsets;
    logic [2:0] injected_valid;
    assign injected_valid=raw_field_valid & ~(sim_drop_response ? 3'b001 : 3'b000);
    assign injected_offsets=raw_field_offsets ^ ((sim_bad_response_tag && raw_field_valid[0]) ? {{(2*AW){1'b0}},{{(AW-1){1'b0}},1'b1}} : {3*AW{1'b0}});
    genefer_track_a4_field_transfer_v2 #(.AW(AW)) transfer (
        .clk,.rst_n,.cancel(cancel || failed || outer_fault),
        .read_en(accepted_transfer_read),.write_en(accepted_transfer_write),
        .read_offset,.write_offset,.read_mask,.write_mask,.write_words,
        .read_valid(transfer_valid),.read_masks(transfer_masks),.read_offsets(transfer_offsets),.read_words(transfer_words),
        .busy(transfer_busy),.quiet(transfer_quiet),.error(transfer_error),
        .field_read_en,.field_write_en,.field_read_offset,.field_write_offset,
        .field_read_mask,.field_write_mask,.field_write_words,
        .field_read_valid(injected_valid),.field_read_masks(raw_field_masks),
        .field_read_offsets(injected_offsets),.field_read_words(raw_field_words),
        .field_error(|route_errors)
    );
    logic [2:0] consumed_valid;
    logic [31:0] consumed_generation,generation_pipe[0:4];
    // This is an actual caller edge sink, not a post-edge C++ approximation.
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            consumed_valid<=0;consumed_generation<=0;caller_masks<=0;caller_offsets<=0;
            for(int j=0;j<5;j=j+1)generation_pipe[j]<=0;
        end else if(cancel || failed || outer_fault)begin
            consumed_valid<=0;
            for(int j=0;j<5;j=j+1)generation_pipe[j]<=0;
        end else begin
            generation_pipe[0]<=generation;
            for(int j=1;j<5;j=j+1)generation_pipe[j]<=generation_pipe[j-1];
            consumed_valid<=transfer_valid & field_allow;
            if(&transfer_valid && &field_allow)begin
                caller_words<=transfer_words;caller_masks<=transfer_masks;caller_offsets<=transfer_offsets;
                consumed_generation<=generation_pipe[4];
            end
        end
    end
    assign caller_valid=(consumed_valid & field_allow) | (sim_stale_valid && !actual_ready ? 3'b001 : 3'b000);
    assign caller_generation=consumed_generation ^ (sim_bad_generation && |consumed_valid ? 32'd1 : 32'd0);
    for(genvar f=0;f<3;f=f+1)begin: field_leaf
        localparam logic [31:0] P=f==0 ? 32'd104857601 : f==1 ? 32'd69206017 : 32'd67239937;
        localparam logic [31:0] Q=32'd2-P;
        logic [31:0] ram_q[0:127],ram_w[0:127];
        logic [RW-1:0] ram_ra[0:127],ram_wa[0:127];
        logic [127:0] ram_re,ram_we;
        assign physical_read[f]=field_rst_n[f] && (|ram_re);
        assign physical_write[f]=field_rst_n[f] && (|ram_we);
        genefer_track_a4_blockroute_v2 #(.AW(AW),.RW(RW)) route (
            .clk,.rst_n(field_rst_n[f]),.enable(field_allow[f]),
            .read_en(field_read_en && field_allow[f]),.write_en(field_write_en && field_allow[f]),
            .read_offset(field_read_offset),.write_offset(field_write_offset),
            .read_mask(field_read_mask),.write_mask(field_write_mask),
            .write_words(field_write_words[f*512+:512]),.ram_q,
            .request(),.error(route_errors[f]),.read_valid(raw_field_valid[f]),
            .read_offset_out(raw_field_offsets[f*AW+:AW]),.read_mask_out(raw_field_masks[f*16+:16]),
            .read_words(raw_field_words[f*512+:512]),.ram_re,.ram_we,.ram_ra,.ram_wa,.ram_w
        );
        for(genvar bank=0;bank<128;bank=bank+1)begin: data_bank
            genefer_sdp_ram32 #(.AW(RW),.DEPTH(1<<(AW>7 ? AW-7 : 0))) ram (
                .clk,.rst_n(field_rst_n[f]),.read_en(ram_re[bank] && field_allow[f]),
                .write_en(ram_we[bank] && field_allow[f]),.read_addr(ram_ra[bank]),
                .write_addr(ram_wa[bank]),.write_data(ram_w[bank]),.read_data(ram_q[bank])
            );
        end
        logic raw_mult_valid,raw_rom_busy,raw_rom_done,raw_rom_valid,loaded;
        logic [31:0] raw_mult_result,raw_rom_word,profile_generation;
        logic [15:0] raw_rom_address;
        logic [2:0] profile_count;
        assign accepted_start[f]=direct_start && field_allow[f] && !raw_rom_busy;
        assign accepted_mult[f]=direct_mult_valid && field_allow[f];
        genefer_montgomery_mul27_sparse_pipe #(.P(P),.Q(Q)) multiply (
            .clk,.rst_n(field_rst_n[f]),.in_valid(accepted_mult[f]),
            .lhs(mult_lhs[f*32+:32]),.rhs(mult_rhs[f*32+:32]),
            .out_valid(raw_mult_valid),.result(raw_mult_result)
        );
        genefer_a10_profile3_rom_v1 #(.AW(AW),.P(P)) profile (
            .clk,.rst_n(field_rst_n[f]),.start(accepted_start[f]),
            .busy(raw_rom_busy),.done(raw_rom_done),.word_valid(raw_rom_valid),
            .word_addr(raw_rom_address),.word_data(raw_rom_word)
        );
        // Tiny probe collector observes the real four-word ROM contract.
        // Its reset validity is separate from reset-ready and retained RAM.
        always_ff @(posedge clk or negedge field_rst_n[f])begin
            if(!field_rst_n[f])begin loaded<=0;profile_count<=0;profile_generation<=0;end
            else if(field_allow[f])begin
                if(accepted_start[f])begin loaded<=0;profile_count<=0;profile_generation<=generation;end
                else if(raw_rom_valid)begin
                    profile_count<=profile_count+1'b1;
                    if(raw_rom_address==16'd3 && profile_count==3)loaded<=1;
                end
            end
        end
        assign mult_valid[f]=raw_mult_valid && field_allow[f];
        assign mult_results[f*32+:32]=raw_mult_result;
        assign rom_busy[f]=raw_rom_busy && field_allow[f];
        assign rom_done[f]=raw_rom_done && field_allow[f];
        assign rom_valid[f]=raw_rom_valid && field_allow[f];
        assign rom_addresses[f*16+:16]=raw_rom_address;
        assign rom_words[f*32+:32]=raw_rom_word;
        assign profile_loaded[f]=loaded && field_allow[f];
        assign profile_counts[f*3+:3]=profile_count;
        assign profile_generations[f*32+:32]=profile_generation;
    end
    // synthesis translate_off
    initial if(AW!=5 && AW!=8)$fatal(1,"ANEXT_RESET_COMPONENT_AW5_AW8_ONLY");
    // synthesis translate_on
endmodule
