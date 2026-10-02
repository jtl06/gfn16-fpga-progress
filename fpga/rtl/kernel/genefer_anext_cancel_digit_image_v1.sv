// A4 digit image frontend, standalone source candidate. No core qualification.
// Read accepted E0 -> frozen synchronous RAM q plus captured correction/tag
// after E0; consumer samples E1. Caller owns complete-image and base-change
// validation, quarantine, and zero-materialization before set_minus_one.
module genefer_anext_cancel_digit_image_v1 #(parameter int AW=16) (
    input logic clk,rst_n,cancel,configure,clear_image,
    input logic [31:0] base,generation,
    output logic configured,
    output logic [31:0] active_base,active_generation,
    input logic read_en,
    input logic [AW-1:0] read_offset,read_tag,
    input logic [15:0] read_mask,
    input logic read_apply_corrections,
    input logic write_en,
    input logic [AW-1:0] write_offset,
    input logic [15:0] write_mask,
    input logic [511:0] write_words,
    input logic [1:0] write_kind,
    input logic clear_corrections,set_minus_one,boundary_commit,
    input logic [511:0] boundary_low_words,boundary_high_words,
    output logic read_valid,
    output logic [15:0] read_mask_out,
    output logic [AW-1:0] read_tag_out,
    output logic [31:0] read_generation,
    output logic [527:0] read_words,
    output logic error,
    output logic [3:0] error_code,
    output logic [31:0] error_generation,
    output logic [511:0] c0_words,c1_words,shadow0_words,shadow1_words,
    output logic [15:0] shadow0_valid,shadow1_valid
);
    localparam int RW=AW-4,T=1<<RW,N=1<<AW,K=2*N+384;
    localparam int MIN_PROOF=(2*K+2)/3+1;
    localparam int MIN_BASE=(2*N+5)>MIN_PROOF ? 2*N+5 : MIN_PROOF;
    logic signed [31:0] c0[0:15],c1[0:15],read_correction[0:15];
    logic [31:0] shadow0[0:15],shadow1[0:15],ram_q[0:15];
    logic fault;
    logic [3:0] fault_code;
    wire data_action=read_en || write_en;
    wire metadata_action=clear_corrections || set_minus_one || boundary_commit;
    wire request=configure || data_action || metadata_action;
    // Late same-edge kill freezes all image mutations, not a delayed/reset cancel.
    wire accept=rst_n && request && !fault && !cancel;
    wire read_accept=accept && read_en;
    wire write_accept=accept && write_en;
    always_comb begin
        fault=0;fault_code=0;
        if(request)begin
            if((configure && (data_action || metadata_action)) || (metadata_action && data_action) ||
               (clear_corrections && set_minus_one) || (clear_corrections && boundary_commit) ||
               (set_minus_one && boundary_commit))begin fault=1;fault_code=4'd1;end
            else if((configure && (base<32'(MIN_BASE) || base>32'd1000000000 || (!configured && !clear_image))) ||
                    (!configure && !configured))begin fault=1;fault_code=4'd2;end
            else if(!configure && generation!=active_generation)begin fault=1;fault_code=4'd3;end
            else if((read_en && int'(read_offset)>=T) ||
                    (write_en && (int'(write_offset)>=T || write_kind==2'd3)))begin fault=1;fault_code=4'd4;end
            else if(read_en && write_en && read_offset==write_offset && (|(read_mask & write_mask)))begin
                fault=1;fault_code=4'd5;
            end else begin
                if(write_en)for(int j=0;j<16;j=j+1)if(write_mask[j])begin
                    if((write_kind!=2'd2 && write_words[j*32+:32]>=active_base) ||
                       (write_kind==2'd2 && ($signed(write_words[j*32+:32]) < -32'sd1 ||
                        $signed({write_words[j*32+31],write_words[j*32+:32]}) >= $signed({1'b0,active_base}))))begin
                        fault=1;fault_code=4'd6;
                    end
                end
                if(boundary_commit)for(int j=0;j<16;j=j+1)begin
                    if(boundary_low_words[j*32+:32]>=active_base ||
                       $signed(boundary_high_words[j*32+:32]) < -32'(K) ||
                       $signed(boundary_high_words[j*32+:32]) > 32'(K))begin fault=1;fault_code=4'd7;end
                end
            end
        end
    end
    for(genvar lane=0;lane<16;lane=lane+1)begin: banks
        localparam int SOURCE=(lane+15)%16;
        genefer_sdp_ram32 #(.AW(RW),.DEPTH(T)) ram (
            .clk,.rst_n,.read_en(read_accept && read_mask[lane]),
            .write_en(write_accept && write_mask[lane]),
            .read_addr(read_offset[RW-1:0]),.write_addr(write_offset[RW-1:0]),
            .write_data(write_words[lane*32+:32]),.read_data(ram_q[lane])
        );
        assign read_words[lane*33+:33]=$signed({ram_q[lane][31],ram_q[lane]})+
                                      $signed({read_correction[lane][31],read_correction[lane]});
        assign c0_words[lane*32+:32]=c0[lane];
        assign c1_words[lane*32+:32]=c1[lane];
        assign shadow0_words[lane*32+:32]=shadow0[lane];
        assign shadow1_words[lane*32+:32]=shadow1[lane];
        // Shadow payloads and RAM do not reset; validity owns eligibility.
        always_ff @(posedge clk)begin
            if(write_accept && write_mask[lane] && write_kind==0)begin
                if(write_offset==0)shadow0[lane]<=write_words[lane*32+:32];
                if(write_offset==1)shadow1[lane]<=write_words[lane*32+:32];
            end
        end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin
                c0[lane]<=0;c1[lane]<=0;read_correction[lane]<=0;
                shadow0_valid[lane]<=0;shadow1_valid[lane]<=0;
            end else begin
                if(read_accept)begin
                    if(!read_apply_corrections)read_correction[lane]<=0;
                    else if(read_offset==0)read_correction[lane]<=c0[lane];
                    else if(read_offset==1)read_correction[lane]<=c1[lane];
                    else read_correction[lane]<=0;
                end
                if(accept && configure && clear_image)begin
                    c0[lane]<=0;c1[lane]<=0;shadow0_valid[lane]<=0;shadow1_valid[lane]<=0;
                end
                if(accept && clear_corrections)begin c0[lane]<=0;c1[lane]<=0;end
                if(accept && set_minus_one)begin c0[lane]<=lane==0 ? -32'sd1 : 32'sd0;c1[lane]<=0;end
                if(accept && boundary_commit)begin
                    if(lane==0)begin
                        c0[lane]<=32'(-$signed({1'b0,boundary_low_words[SOURCE*32+:32]}));
                        c1[lane]<=-$signed(boundary_high_words[SOURCE*32+:32]);
                    end else begin
                        c0[lane]<=boundary_low_words[SOURCE*32+:32];
                        c1[lane]<=$signed(boundary_high_words[SOURCE*32+:32]);
                    end
                end
                if(write_accept && write_mask[lane])begin
                    if(write_offset==0)begin
                        shadow0_valid[lane]<=write_kind==0;
                        if(write_kind==2)c0[lane]<=0;
                    end
                    if(write_offset==1)begin
                        shadow1_valid[lane]<=write_kind==0;
                        if(write_kind==2)c1[lane]<=0;
                    end
                end
            end
        end
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            configured<=0;active_base<=0;active_generation<=0;
            read_valid<=0;read_mask_out<=0;read_tag_out<=0;read_generation<=0;
            error<=0;error_code<=0;error_generation<=0;
        end else begin
            read_valid<=read_accept;read_mask_out<=read_accept ? read_mask : 16'd0;
            error<=request && fault && !cancel;error_code<=request && fault && !cancel ? fault_code : 4'd0;
            if(request && fault && !cancel)error_generation<=generation;
            if(read_accept)begin read_tag_out<=read_tag;read_generation<=generation;end
            if(accept && configure)begin configured<=1;active_base<=base;active_generation<=generation;end
        end
    end
    // synthesis translate_off
    initial if(AW<5 || AW>16)$fatal(1,"A4_DIGIT_IMAGE_GEOMETRY");
    // synthesis translate_on
endmodule
