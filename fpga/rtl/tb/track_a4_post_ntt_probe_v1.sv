// Real CRT/lane/reducer/route/RAM post-service probe, no NTT simulation surrogate.
// Host loads exact coefficient residues and verifies resulting redundant image
// plus the complete next-image ordinary residues stored in all three fields.
module track_a4_post_ntt_probe_v1 #(parameter int AW=5) (
    input logic clk,rst_n,prepare,start_post,cancel,double_bit,configure_image,
    input logic [31:0] base,generation,
    input logic [76:0] coefficient_limit,
    input logic [95:0] reciprocal,
    input logic host_field_load,host_field_read,image_read,
    input logic [AW-1:0] host_offset,
    input logic [1535:0] host_field_words,
    output logic ready,busy,done,error,tail_checked,
    output logic [7:0] error_code,
    output logic [31:0] out_generation,
    output logic [63:0] cycles,
    output logic [AW:0] coefficients_seen,digits_written,
    output logic [5:0] patch_words_written,
    output logic [2:0] host_field_valid,
    output logic [1535:0] host_field_read_words,
    output logic image_read_valid,
    output logic [527:0] image_read_words,
    output logic [511:0] c0_words,c1_words,shadow0_words,shadow1_words,
    output logic [15:0] shadow0_valid,shadow1_valid
);
    localparam int RW=AW>7 ? AW-7 : 1,DEPTH=1<<(AW>7 ? AW-7 : 0);
    logic fr,fw,iw,bc;
    logic [AW-1:0] fro,fwo,iwo;
    logic [15:0] frm,fwm,iwm;
    logic [1535:0] fww;
    logic [511:0] iww,bl,bh;
    logic [2:0] fv,fe;
    logic [47:0] fm;
    logic [3*AW-1:0] fo;
    logic [1535:0] fd;
    logic image_error,configured;
    logic [3:0] image_error_code;
    logic [31:0] active_base,active_generation,image_error_generation;
    logic [AW-1:0] image_tag;
    logic [15:0] image_mask;
    logic [31:0] image_generation;
    genefer_track_a4_post_ntt_v1 #(.AW(AW)) service (
        .clk,.rst_n,.prepare,.start_post,.cancel,.double_bit,.base,.generation,.coefficient_limit,.reciprocal,
        .ready,.busy,.done,.error,.tail_checked,.error_code,.out_generation,.cycles,.coefficients_seen,.digits_written,.patch_words_written,
        .field_read_en(fr),.field_write_en(fw),.field_read_offset(fro),.field_write_offset(fwo),
        .field_read_mask(frm),.field_write_mask(fwm),.field_write_words(fww),.field_read_valid(fv),
        .field_read_masks(fm),.field_read_offsets(fo),.field_read_words(fd),.field_error(|fe),.image_error,
        .image_write_en(iw),.image_boundary_commit(bc),.image_write_offset(iwo),.image_write_mask(iwm),.image_write_words(iww),
        .boundary_low_words(bl),.boundary_high_words(bh),.shadow0_words,.shadow1_words,.c0_words,.c1_words,.shadow0_valid,.shadow1_valid
    );
    for(genvar f=0;f<3;f=f+1)begin: fields
        logic [31:0] q[0:127],w[0:127];
        logic [127:0] re,we;
        logic [RW-1:0] ra[0:127],wa[0:127];
        logic request;
        genefer_track_a4_blockroute_v2 #(.AW(AW),.RW(RW)) route (
            .clk,.rst_n,.enable(1'b1),.read_en(fr || host_field_read),.write_en(fw || host_field_load),
            .read_offset(fr ? fro : host_offset),.write_offset(fw ? fwo : host_offset),
            .read_mask(fr ? frm : 16'hffff),.write_mask(fw ? fwm : 16'hffff),
            .write_words(fw ? fww[f*512+:512] : host_field_words[f*512+:512]),.ram_q(q),.request,
            .error(fe[f]),.read_valid(fv[f]),.read_offset_out(fo[f*AW+:AW]),.read_mask_out(fm[f*16+:16]),
            .read_words(fd[f*512+:512]),.ram_re(re),.ram_we(we),.ram_ra(ra),.ram_wa(wa),.ram_w(w)
        );
        for(genvar bank=0;bank<128;bank=bank+1)begin: banks
            genefer_sdp_ram32 #(.AW(RW),.DEPTH(DEPTH)) ram (
                .clk,.rst_n,.read_en(re[bank]),.write_en(we[bank]),.read_addr(ra[bank]),.write_addr(wa[bank]),
                .write_data(w[bank]),.read_data(q[bank])
            );
        end
    end
    assign host_field_valid=fv;
    assign host_field_read_words=fd;
    genefer_track_a4_digit_image_v1 #(.AW(AW)) image (
        .clk,.rst_n,.configure(configure_image),.clear_image(1'b1),.base,.generation,
        .configured,.active_base,.active_generation,
        .read_en(image_read),.read_offset(host_offset),.read_tag(host_offset),.read_mask(16'hffff),.read_apply_corrections(1'b1),
        .write_en(iw),.write_offset(iwo),.write_mask(iwm),.write_words(iww),.write_kind(2'd0),
        .clear_corrections(1'b0),.set_minus_one(1'b0),.boundary_commit(bc),.boundary_low_words(bl),.boundary_high_words(bh),
        .read_valid(image_read_valid),.read_mask_out(image_mask),.read_tag_out(image_tag),.read_generation(image_generation),.read_words(image_read_words),
        .error(image_error),.error_code(image_error_code),.error_generation(image_error_generation),
        .c0_words,.c1_words,.shadow0_words,.shadow1_words,.shadow0_valid,.shadow1_valid
    );
endmodule
