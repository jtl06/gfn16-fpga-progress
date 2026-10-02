// Provisional2-edge host word service: beginE0, RAM requestE1, checked doneE2.
module genefer_anext_cancel_host_word_v1 #(parameter int AW=16) (
    input logic clk,rst_n,begin_word,cancel,write_word,
    input logic [AW-1:0] address,
    input logic signed [31:0] write_data,
    input logic [31:0] generation,
    output logic done,error,
    output logic signed [31:0] read_data,
    output logic [31:0] out_generation,
    output logic mem_read_en,mem_write_en,mem_write_select,
    output logic [AW-1:0] mem_offset,mem_tag,
    output logic [15:0] mem_mask,
    output logic [511:0] mem_write_words,
    output logic [31:0] mem_generation,
    input logic mem_error,mem_read_valid,
    input logic [AW-1:0] mem_read_tag,
    input logic [15:0] mem_read_mask,
    input logic [31:0] mem_read_generation,
    input logic [527:0] mem_read_words
);
    localparam int T=1<<(AW-4);
    typedef enum logic [1:0] {IDLE,ACCESS,CHECK} state_t;
    state_t state;
    logic write_reg;
    logic [AW-1:0] address_reg;
    logic signed [31:0] word_reg;
    wire [3:0] bank=4'(address_reg>>(AW-4));
    wire signed [32:0] selected_word=$signed(mem_read_words[int'(bank)*33+:33]);
    assign mem_offset=AW'(32'(address_reg)&32'(T-1));
    assign mem_tag=address_reg;
    assign mem_mask=16'd1<<bank;
    assign mem_generation=out_generation;
    assign mem_read_en=state==ACCESS && !write_reg && !mem_error && !cancel;
    // Payload owner is independent of cancel; the original eligible enable stays immediate.
    assign mem_write_select=state==ACCESS && write_reg && !mem_error;
    assign mem_write_en=mem_write_select && !cancel;
    always_comb begin mem_write_words=0;mem_write_words[int'(bank)*32+:32]=word_reg;end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin state<=IDLE;done<=0;error<=0;read_data<=0;out_generation<=0;write_reg<=0;address_reg<=0;word_reg<=0;end
        else begin
            done<=0;error<=0;
            if(state==IDLE && begin_word)begin
                state<=ACCESS;write_reg<=write_word;address_reg<=address;word_reg<=write_data;out_generation<=generation;
            end
            if(state==ACCESS)state<=CHECK;
            if(state==CHECK)begin
                state<=IDLE;done<=1;
                if(mem_error || (!write_reg && (!mem_read_valid || mem_read_tag!=address_reg ||
                    mem_read_mask!=mem_mask || mem_read_generation!=out_generation ||
                    selected_word[32]!=selected_word[31])))error<=1;
                else if(!write_reg)read_data<=selected_word[31:0];
            end
            if(state!=IDLE && (begin_word || mem_error))begin state<=IDLE;done<=1;error<=1;end
            if(cancel)begin state<=IDLE;done<=0;error<=0;end
        end
    end
endmodule
