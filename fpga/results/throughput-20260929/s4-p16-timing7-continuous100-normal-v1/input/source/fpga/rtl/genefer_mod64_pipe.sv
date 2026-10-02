// Exact unsigned 64-bit remainder, throughput one word per clock.
// Four radix-2 restoring steps per registered stage; 16 pipeline stages.
// Payload travels with its word, including across bubbles. Canonical remainder
// invariant (rem < MODULUS) bounds each step to one conditional subtraction.
module genefer_mod64_pipe #(
    parameter logic [31:0] MODULUS = 32'd2013265921,
    parameter integer PAYLOAD_W = 1
) (
    input logic clk, rst_n, in_valid,
    input logic [63:0] word_in,
    input logic [PAYLOAD_W-1:0] payload_in,
    output logic out_valid,
    output logic [31:0] remainder,
    output logic [PAYLOAD_W-1:0] payload_out
);
    logic [15:0] valid;
    logic [63:0] words [0:15];
    logic [31:0] rems [0:15];
    logic [PAYLOAD_W-1:0] payloads [0:15];
    for (genvar s=0; s<16; s=s+1) begin: stage
        logic [63:0] next_word;
        logic [31:0] next_rem;
        logic [32:0] work_rem;
        always_comb begin
            if (s==0) begin
                next_word=word_in;
                next_rem=0;
            end else begin
                next_word=words[s-1];
                next_rem=rems[s-1];
            end
            work_rem=0;
            for (integer k=0; k<4; k=k+1) begin
                work_rem={next_rem,next_word[63]};
                next_word=next_word << 1;
                if (work_rem >= {1'b0,MODULUS})
                    work_rem=work_rem-{1'b0,MODULUS};
                next_rem=work_rem[31:0];
            end
        end
        always_ff @(posedge clk) begin
            words[s]<=next_word;
            rems[s]<=next_rem;
            if (s==0) payloads[s]<=payload_in;
            else payloads[s]<=payloads[s-1];
        end
        always_ff @(posedge clk or negedge rst_n) begin
            if (!rst_n) valid[s]<=0;
            else if (s==0) valid[s]<=in_valid;
            else valid[s]<=valid[s-1];
        end
    end
    assign remainder=rems[15];
    assign payload_out=payloads[15];
    assign out_valid=valid[15];
endmodule
