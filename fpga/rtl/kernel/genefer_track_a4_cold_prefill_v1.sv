// Canonical image -> ordinary three-field residues. No numeric NTT here.
// Frontend response passes explicit source and destination data registers.
// Output goes through the shared r13 field transfer bridge; completion waits
// for that bridge's destination-write and registered-error tail.
module genefer_track_a4_cold_prefill_v1 #(parameter int AW=16) (
    input logic clk,rst_n,cancel,begin_prefill,
    input logic [31:0] base,generation,
    output logic busy,done,error,
    output logic [63:0] cycles,
    output logic image_read_en,
    output logic [AW-1:0] image_read_offset,image_read_tag,
    output logic [15:0] image_read_mask,
    input logic image_read_valid,image_error,
    input logic [AW-1:0] image_read_tag_out,
    input logic [15:0] image_read_mask_out,
    input logic [31:0] image_read_generation,
    input logic [527:0] image_read_words,
    output logic field_write_en,
    output logic [AW-1:0] field_write_offset,
    output logic [15:0] field_write_mask,
    output logic [1535:0] field_write_words,
    input logic transfer_quiet,transfer_error
);
    localparam int T=(1<<AW)/16;
    localparam logic [31:0] PRIME[0:2]='{32'd104857601,32'd69206017,32'd67239937};
    typedef enum logic [1:0] {IDLE,RUN,DRAIN,FAILED} state_t;
    state_t state;
    logic [31:0] base_reg,generation_reg;
    logic [AW:0] issued,received,written;
    logic read_due;
    logic [AW-1:0] due_tag,source_tag,destination_tag;
    logic [1:0] capture_valid;
    logic [511:0] source_words,destination_words;
    logic [47:0] reduced_valid,reduced_error;
    logic [AW-1:0] reduced_tag[0:47];
    logic input_legal,fault;
    wire pipeline_rst_n=rst_n && !cancel && state!=IDLE && state!=FAILED;
    assign busy=state==RUN || state==DRAIN;
    assign image_read_en=state==RUN && int'(issued)<T && !fault && !cancel;
    assign image_read_offset=AW'(issued);
    assign image_read_tag=AW'(issued);
    assign image_read_mask=16'hffff;
    always_comb begin
        input_legal=1;
        for(int lane=0;lane<16;lane=lane+1)
            if($signed(image_read_words[lane*33+:33]) < -33'sd1 ||
               $signed(image_read_words[lane*33+:33]) >= $signed({1'b0,base_reg}))input_legal=0;
        fault=busy && (begin_prefill || image_error || transfer_error || (|reduced_error) ||
            image_read_valid!=read_due ||
            (image_read_valid && (!input_legal || image_read_tag_out!=due_tag ||
                image_read_mask_out!=16'hffff || image_read_generation!=generation_reg)) ||
            (reduced_valid!=0 && !(&reduced_valid)) ||
            ((&reduced_valid) && reduced_tag[0]!=AW'(written)));
        for(int i=0;i<48;i=i+1)
            if(busy && reduced_valid[i] && reduced_tag[i]!=reduced_tag[0])fault=1;
    end
    assign field_write_en=busy && (&reduced_valid) && !fault && !cancel;
    assign field_write_offset=reduced_tag[0];
    assign field_write_mask=16'hffff;
    for(genvar f=0;f<3;f=f+1)begin: field_reducers
        for(genvar lane=0;lane<16;lane=lane+1)begin: lanes
            localparam int I=f*16+lane;
            genefer_digit_reduce27_pipe #(.P(PRIME[f]),.PAYLOAD_W(AW)) reduce_digit (
                .clk,.rst_n(pipeline_rst_n),.in_valid(capture_valid[1]),
                .digit(destination_words[lane*32+:32]),.payload_in(destination_tag),
                .out_valid(reduced_valid[I]),.out_error(reduced_error[I]),
                .residue(field_write_words[I*32+:32]),.payload_out(reduced_tag[I])
            );
        end
    end
    always_ff @(posedge clk)if(pipeline_rst_n && !fault)begin
        if(image_read_valid && input_legal)
            for(int lane=0;lane<16;lane=lane+1)source_words[lane*32+:32]<=image_read_words[lane*33+:32];
        if(capture_valid[0])destination_words<=source_words;
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;done<=0;error<=0;cycles<=0;base_reg<=0;generation_reg<=0;
            issued<=0;received<=0;written<=0;read_due<=0;due_tag<=0;capture_valid<=0;source_tag<=0;destination_tag<=0;
        end else begin
            done<=0;read_due<=image_read_en;
            capture_valid<={capture_valid[0],image_read_valid && busy && !fault};
            if(image_read_en)begin issued<=issued+1'b1;due_tag<=image_read_tag;end
            if(image_read_valid && busy && !fault)begin received<=received+1'b1;source_tag<=image_read_tag_out;end
            if(capture_valid[0])destination_tag<=source_tag;
            if(busy)cycles<=cycles+1'b1;
            if(state==IDLE && begin_prefill)begin
                state<=RUN;done<=0;error<=0;cycles<=0;base_reg<=base;generation_reg<=generation;
                issued<=0;received<=0;written<=0;read_due<=0;capture_valid<=0;
            end
            if(field_write_en)begin written<=written+1'b1;if(int'(written)==T-1)state<=DRAIN;end
            if(state==DRAIN && transfer_quiet && !fault)begin
                if(int'(issued)!=T || int'(received)!=T || int'(written)!=T ||
                    read_due || (|capture_valid) || (|reduced_valid))begin state<=FAILED;error<=1;end
                else begin state<=IDLE;done<=1;end
            end
            if(fault)begin state<=FAILED;error<=1;done<=0;capture_valid<=0;read_due<=0;end
            if(cancel)begin state<=IDLE;done<=0;error<=0;capture_valid<=0;read_due<=0;end
        end
    end
endmodule
