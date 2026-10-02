// Provisional executable post-NTT service. prepare overlaps the NTT; start_post
// accepts the first block-row residue read on that edge. Proposed T+58 interval.
// Uses qualified shared cells; no whole-core/native qualification implied here.
module genefer_track_a4_post_ntt_v1 #(parameter int AW=16) (
    input logic clk,rst_n,prepare,start_post,cancel,double_bit,
    input logic [31:0] base,generation,
    input logic [76:0] coefficient_limit,
    input logic [95:0] reciprocal,
    output logic ready,busy,done,error,tail_checked,
    output logic [7:0] error_code,
    output logic [31:0] out_generation,
    output logic [63:0] cycles,
    output logic [AW:0] coefficients_seen,digits_written,
    output logic [5:0] patch_words_written,
    output logic field_read_en,field_write_en,
    output logic [AW-1:0] field_read_offset,field_write_offset,
    output logic [15:0] field_read_mask,field_write_mask,
    output logic [1535:0] field_write_words,
    input logic [2:0] field_read_valid,
    input logic [47:0] field_read_masks,
    input logic [3*AW-1:0] field_read_offsets,
    input logic [1535:0] field_read_words,
    input logic field_error,image_error,
    output logic image_write_en,image_boundary_commit,
    output logic [AW-1:0] image_write_offset,
    output logic [15:0] image_write_mask,
    output logic [511:0] image_write_words,boundary_low_words,boundary_high_words,
    input logic [511:0] shadow0_words,shadow1_words,c0_words,c1_words,
    input logic [15:0] shadow0_valid,shadow1_valid
);
    localparam int N=1<<AW,T=N/16;
    localparam logic [31:0] PRIME[0:2]='{32'd104857601,32'd69206017,32'd67239937};
    typedef enum logic [3:0] {IDLE,ARM,WAIT_NTT,RUN,PATCH,DRAIN,CHECK,FAILED} state_t;
    state_t state;
    logic [31:0] base_reg;
    logic [76:0] limit_reg;
    logic [95:0] reciprocal_reg;
    logic double_reg,lane_begin;
    logic [AW:0] issued_rows,crt_rows,digit_rows,normal_written;
    logic [1:0] patch_issued;
    logic boundary_committed,lanes_finished;
    logic fault;
    logic [7:0] fault_code;
    wire pipeline_rst_n=rst_n && !cancel && state!=IDLE && state!=ARM && state!=FAILED;
    assign ready=state==WAIT_NTT && !lane_begin;
    assign busy=state==RUN || state==PATCH || state==DRAIN || state==CHECK;
    wire issue_window=state==RUN || (ready && start_post);
    assign field_read_en=issue_window && int'(issued_rows)<T && !fault && !cancel;
    assign field_read_offset=AW'(issued_rows);
    assign field_read_mask=16'hffff;
    wire residues_valid=&field_read_valid;
    logic [15:0] crt_valid,crt_ready;
    logic signed [95:0] coefficient[0:15];
    logic [AW-1:0] crt_tag[0:15];
    logic [15:0] crt_tag_valid;
    wire crt_accept=state==RUN && residues_valid && !fault;
    always_ff @(posedge clk or negedge pipeline_rst_n)begin
        if(!pipeline_rst_n)begin crt_tag_valid<=0;for(int d=0;d<16;d=d+1)crt_tag[d]<=0;end
        else begin
            crt_tag_valid<={crt_tag_valid[14:0],crt_accept};
            if(crt_accept)crt_tag[0]<=field_read_offsets[0+:AW];
            for(int d=1;d<16;d=d+1)if(crt_tag_valid[d-1])crt_tag[d]<=crt_tag[d-1];
        end
    end
    logic [15:0] lane_busy,lane_done,lane_error,lane_digit_valid,lane_boundary_valid;
    logic [3:0] lane_error_code[0:15];
    logic [AW-1:0] lane_offset[0:15];
    logic [31:0] lane_digit[0:15],lane_low[0:15];
    logic signed [31:0] lane_high[0:15];
    for(genvar lane=0;lane<16;lane=lane+1)begin: carry_lanes
        genefer_crt3_27_mont_pipe crt (
            .clk,.rst_n(pipeline_rst_n),.in_valid(crt_accept),
            .r1(field_read_words[lane*32+:32]),.r2(field_read_words[512+lane*32+:32]),
            .r3(field_read_words[1024+lane*32+:32]),.ready(crt_ready[lane]),
            .out_valid(crt_valid[lane]),.coefficient(coefficient[lane])
        );
        genefer_track_a4_blockcarry_lane_v1 #(.AW(AW)) carry_lane (
            .clk,.rst_n(pipeline_rst_n),.begin_block(lane_begin),
            .in_valid(state==RUN && (&crt_valid) && !fault),.block_start(crt_tag[15]==0),
            .block_end(int'(crt_tag[15])==T-1),.base(base_reg),.reciprocal(reciprocal_reg),
            .coefficient_limit(limit_reg),.coefficient(double_reg ? (coefficient[lane]<<<1) : coefficient[lane]),
            .offset(crt_tag[15]),.busy(lane_busy[lane]),.done(lane_done[lane]),.error(lane_error[lane]),
            .error_code(lane_error_code[lane]),.digit_valid(lane_digit_valid[lane]),.digit(lane_digit[lane]),
            .digit_offset(lane_offset[lane]),.boundary_valid(lane_boundary_valid[lane]),
            .boundary_low(lane_low[lane]),.boundary_high(lane_high[lane])
        );
        assign image_write_words[lane*32+:32]=lane_digit[lane];
        assign boundary_low_words[lane*32+:32]=lane_low[lane];
        assign boundary_high_words[lane*32+:32]=lane_high[lane];
    end
    assign image_write_en=state==RUN && (&lane_digit_valid) && !fault && !cancel;
    assign image_write_offset=lane_offset[0];
    assign image_write_mask=16'hffff;
    assign image_boundary_commit=state==RUN && (&lane_boundary_valid) && !fault && !cancel;

    wire patch_accept=state==PATCH && patch_issued<2 && !fault;
    wire digit_accept=image_write_en || patch_accept;
    wire [AW:0] digit_payload=patch_accept ? {1'b1,AW'(patch_issued)} : {1'b0,lane_offset[0]};
    logic [47:0] reduce_valid,reduce_error,signed_valid,signed_error;
    logic [31:0] reduced[0:47],signed_reduced[0:47];
    logic [AW:0] reduce_tag[0:47];
    logic [AW-1:0] signed_tag[0:47];
    logic normal_valid,patch_digit_valid,patch_sum_valid,patch_write_valid;
    logic [AW-1:0] normal_offset,patch_digit_offset,patch_sum_offset,patch_write_offset;
    logic [1535:0] normal_words,patch_digit_words,patch_sum_words,patch_write_words;
    for(genvar f=0;f<3;f=f+1)begin: fields
        for(genvar lane=0;lane<16;lane=lane+1)begin: reducers
            localparam int INDEX=f*16+lane;
            wire [31:0] patch_digit=patch_issued==0 ? shadow0_words[lane*32+:32] : shadow1_words[lane*32+:32];
            wire signed [31:0] correction=$signed(patch_issued==0 ? c0_words[lane*32+:32] : c1_words[lane*32+:32]);
            genefer_digit_reduce27_pipe #(.P(PRIME[f]),.PAYLOAD_W(AW+1)) digit_reduce (
                .clk,.rst_n(pipeline_rst_n),.in_valid(digit_accept),
                .digit(patch_accept ? patch_digit : lane_digit[lane]),.payload_in(digit_payload),
                .out_valid(reduce_valid[INDEX]),.out_error(reduce_error[INDEX]),
                .residue(reduced[INDEX]),.payload_out(reduce_tag[INDEX])
            );
            genefer_stream27_signed_boundary_reduce27_pipe #(.P(PRIME[f]),.AW(AW),.BLOCKS(16),.PAYLOAD_W(AW)) correction_reduce (
                .clk,.rst_n(pipeline_rst_n),.in_valid(patch_accept),.boundary_high(patch_issued==1),
                .correction,.base(base_reg),.payload_in(AW'(patch_issued)),
                .out_valid(signed_valid[INDEX]),.out_error(signed_error[INDEX]),
                .residue(signed_reduced[INDEX]),.payload_out(signed_tag[INDEX])
            );
            wire [32:0] patch_sum={1'b0,patch_digit_words[INDEX*32+:32]}+{1'b0,signed_reduced[INDEX]};
            always_ff @(posedge clk)if(pipeline_rst_n)begin
                if((&reduce_valid) && !reduce_tag[0][AW])normal_words[INDEX*32+:32]<=reduced[INDEX];
                if((&reduce_valid) && reduce_tag[0][AW])patch_digit_words[INDEX*32+:32]<=reduced[INDEX];
                if(patch_digit_valid && (&signed_valid))
                    patch_sum_words[INDEX*32+:32]<=32'(patch_sum>={1'b0,PRIME[f]} ? patch_sum-{1'b0,PRIME[f]} : patch_sum);
                if(patch_sum_valid)patch_write_words[INDEX*32+:32]<=patch_sum_words[INDEX*32+:32];
            end
        end
    end
    always_ff @(posedge clk or negedge pipeline_rst_n)begin
        if(!pipeline_rst_n)begin
            normal_valid<=0;patch_digit_valid<=0;patch_sum_valid<=0;patch_write_valid<=0;
            normal_offset<=0;patch_digit_offset<=0;patch_sum_offset<=0;patch_write_offset<=0;
        end else begin
            normal_valid<=(&reduce_valid) && !reduce_tag[0][AW];
            patch_digit_valid<=(&reduce_valid) && reduce_tag[0][AW];
            patch_sum_valid<=patch_digit_valid && (&signed_valid);
            patch_write_valid<=patch_sum_valid;
            if(&reduce_valid)begin normal_offset<=reduce_tag[0][AW-1:0];patch_digit_offset<=reduce_tag[0][AW-1:0];end
            if(patch_digit_valid && (&signed_valid))patch_sum_offset<=signed_tag[0];
            if(patch_sum_valid)patch_write_offset<=patch_sum_offset;
        end
    end
    assign field_write_en=(normal_valid || patch_write_valid) && !fault && !cancel;
    assign field_write_offset=patch_write_valid ? patch_write_offset : normal_offset;
    assign field_write_mask=16'hffff;
    assign field_write_words=patch_write_valid ? patch_write_words : normal_words;
    always_comb begin
        fault=0;fault_code=0;
        if(state!=IDLE && state!=ARM && state!=FAILED)begin
            if(prepare || (start_post && !ready))begin fault=1;fault_code=8'd1;end
            else if(field_error || image_error || (|lane_error) || (|reduce_error) || (|signed_error))begin fault=1;fault_code=8'd2;end
            else if((field_read_valid!=0 && !residues_valid) || (crt_valid!=0 && !(&crt_valid)) ||
                    (lane_digit_valid!=0 && !(&lane_digit_valid)) || (lane_boundary_valid!=0 && !(&lane_boundary_valid)) ||
                    (reduce_valid!=0 && !(&reduce_valid)) || (signed_valid!=0 && !(&signed_valid)))begin fault=1;fault_code=8'd3;end
            else if((&crt_valid)!=crt_tag_valid[15])begin fault=1;fault_code=8'd4;end
            else if(residues_valid && (state!=RUN || field_read_masks!={48{1'b1}} ||
                    field_read_offsets[0+:AW]!=AW'(crt_rows) || field_read_offsets[AW+:AW]!=field_read_offsets[0+:AW] ||
                    field_read_offsets[2*AW+:AW]!=field_read_offsets[0+:AW]))begin fault=1;fault_code=8'd5;end
            else if((&lane_digit_valid) && lane_offset[0]!=AW'(digit_rows))begin fault=1;fault_code=8'd6;end
            else if(normal_valid && (state!=RUN || normal_offset!=AW'(normal_written)))begin fault=1;fault_code=8'd7;end
            else if(state==PATCH && patch_issued<2 && (shadow0_valid!=16'hffff || shadow1_valid!=16'hffff || !boundary_committed || !lanes_finished))begin fault=1;fault_code=8'd8;end
            else if(patch_digit_valid!=(&signed_valid) || (patch_digit_valid && patch_digit_offset!=signed_tag[0]))begin fault=1;fault_code=8'd9;end
            else if(normal_valid && patch_write_valid)begin fault=1;fault_code=8'd10;end
            else if(patch_write_valid && patch_write_offset!=AW'(patch_words_written[5:4]))begin fault=1;fault_code=8'd11;end
            for(int lane=0;lane<16;lane=lane+1)
                if(lane_digit_valid[lane] && lane_offset[lane]!=lane_offset[0])begin fault=1;fault_code=8'd12;end
            for(int i=0;i<48;i=i+1)begin
                if(reduce_valid[i] && reduce_tag[i]!=reduce_tag[0])begin fault=1;fault_code=8'd13;end
                if(signed_valid[i] && signed_tag[i]!=signed_tag[0])begin fault=1;fault_code=8'd14;end
            end
        end
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;done<=0;error<=0;error_code<=0;tail_checked<=0;out_generation<=0;cycles<=0;
            base_reg<=0;limit_reg<=0;reciprocal_reg<=0;double_reg<=0;lane_begin<=0;
            issued_rows<=0;crt_rows<=0;digit_rows<=0;normal_written<=0;patch_issued<=0;
            boundary_committed<=0;lanes_finished<=0;coefficients_seen<=0;digits_written<=0;patch_words_written<=0;
        end else begin
            done<=0;lane_begin<=0;
            if(state==IDLE && prepare)begin
                state<=ARM;base_reg<=base;limit_reg<=coefficient_limit;reciprocal_reg<=reciprocal;
                double_reg<=double_bit;out_generation<=generation;error<=0;error_code<=0;tail_checked<=0;cycles<=0;
                issued_rows<=0;crt_rows<=0;digit_rows<=0;normal_written<=0;patch_issued<=0;
                boundary_committed<=0;lanes_finished<=0;coefficients_seen<=0;digits_written<=0;patch_words_written<=0;
            end
            if(state==ARM)begin state<=WAIT_NTT;lane_begin<=1;end
            if(ready && start_post)begin state<=RUN;cycles<=1;end
            else if(busy)cycles<=cycles+1'b1;
            if(field_read_en)issued_rows<=issued_rows+1'b1;
            if(crt_accept)begin crt_rows<=crt_rows+1'b1;coefficients_seen<=coefficients_seen+(AW+1)'(16);end
            if(image_write_en)begin digit_rows<=digit_rows+1'b1;digits_written<=digits_written+(AW+1)'(16);end
            if(image_boundary_commit)boundary_committed<=1;
            if(&lane_done)lanes_finished<=1;
            if(field_write_en && normal_valid)begin
                normal_written<=normal_written+1'b1;
                if(int'(normal_written)==T-1)begin
                    if(!boundary_committed || !lanes_finished)begin state<=FAILED;error<=1;error_code<=8'd15;end
                    else state<=PATCH;
                end
            end
            if(patch_accept)begin patch_issued<=patch_issued+1'b1;if(patch_issued==1)state<=DRAIN;end
            if(field_write_en && patch_write_valid)begin
                patch_words_written<=patch_words_written+6'd16;
                if(patch_words_written==6'd16)state<=CHECK;
            end
            if(state==CHECK && !fault)begin
                if(int'(coefficients_seen)!=N || int'(digits_written)!=N || patch_words_written!=6'd32 ||
                   int'(issued_rows)!=T || int'(normal_written)!=T || !boundary_committed || !lanes_finished ||
                   normal_valid || patch_write_valid || patch_sum_valid || patch_digit_valid || (|reduce_valid) ||
                   (|signed_valid) || (|lane_busy) || (|crt_tag_valid))begin
                    state<=FAILED;error<=1;error_code<=8'd16;
                end else begin state<=IDLE;done<=1;tail_checked<=1;end
            end
            if(fault)begin state<=FAILED;error<=1;error_code<=fault_code;done<=0;tail_checked<=0;end
            if(cancel)begin state<=IDLE;done<=0;error<=0;tail_checked<=0;lane_begin<=0;end
        end
    end
endmodule
