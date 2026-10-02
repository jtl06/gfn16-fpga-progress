// Exact unsigned remainder for a fixed <=27-bit modulus, II1.
// Two restoring bits per registered stage; ceil(WORD_W/2) stages.
// WORD_W=53,53,51 are proven lossless for the three CRT27 reductions.
module genefer_mod27_pair_pipe #(
    parameter integer WORD_W=53, PAYLOAD_W=1,
    parameter logic [26:0] MODULUS=27'd67239937
) (
    input logic clk,rst_n,in_valid,
    input logic [WORD_W-1:0] word_in,
    input logic [PAYLOAD_W-1:0] payload_in,
    output logic out_valid,
    output logic [31:0] remainder,
    output logic [PAYLOAD_W-1:0] payload_out
);
    localparam integer STAGES=(WORD_W+1)/2, PAD_W=2*STAGES;
    logic [STAGES-1:0] valid;
    logic [PAD_W-1:0] words[0:STAGES-1];
    logic [26:0] rems[0:STAGES-1];
    logic [PAYLOAD_W-1:0] payloads[0:STAGES-1];
    for(genvar s=0;s<STAGES;s=s+1)begin: stage
        logic [PAD_W-1:0] next_word;
        logic [26:0] next_rem;
        logic [27:0] work_rem;
        wire stage_valid;
        if(s==0)assign stage_valid=in_valid;
        else assign stage_valid=valid[s-1];
        always_comb begin
            if(s==0)begin next_word=PAD_W'(word_in);next_rem=0;end
            else begin next_word=words[s-1];next_rem=rems[s-1];end
            work_rem=0;
            for(integer k=0;k<2;k=k+1)begin
                work_rem={next_rem,next_word[PAD_W-1]};
                next_word=next_word<<1;
                if(work_rem>={1'b0,MODULUS})work_rem=work_rem-{1'b0,MODULUS};
                next_rem=work_rem[26:0];
            end
        end
        always_ff @(posedge clk)begin
            words[s]<=next_word;rems[s]<=next_rem;
            if(s==0)payloads[s]<=payload_in;
            else payloads[s]<=payloads[s-1];
        end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)valid[s]<=0;
            else valid[s]<=stage_valid;
        end
    end
    assign remainder={5'b0,rems[STAGES-1]};
    assign payload_out=payloads[STAGES-1];
    assign out_valid=valid[STAGES-1];
    // synthesis translate_off
    initial begin
        if(WORD_W<1 || WORD_W>64 || PAYLOAD_W<1 || MODULUS<2)
            $fatal(1,"invalid mod27 pair parameters");
    end
    always @(posedge clk)if(rst_n && out_valid && remainder>=32'(MODULUS))
        $fatal(1,"mod27 pair remainder bound");
    // synthesis translate_on
endmodule
