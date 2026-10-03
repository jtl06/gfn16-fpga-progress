// S-M1 only: same advance/reset/head calendar as frozen mdc_fifo_sync.
// DEPTH<=32 is an explicit logic shift chain, not a feed-through RAM.
// No data reset: filled masks stale data until DEPTH new advances after reset.
// Larger delays delegate unchanged to the frozen synchronous RAM helper.
module genefer_stream27_mdc_fifo_smallreg_v1 #(
    parameter int unsigned WORD_W=38,
    parameter int unsigned DEPTH=4
) (
    input logic clk,rst_n,advance,
    input logic [WORD_W-1:0] write_word,
    output logic [WORD_W-1:0] head
);
    generate if(DEPTH<=32)begin: short_logic
        localparam int FILL_W=$clog2(DEPTH+1);
        logic [FILL_W-1:0] filled;
        (* ramstyle = "logic" *) logic [WORD_W-1:0] chain[0:DEPTH-1];
        assign head=filled==FILL_W'(DEPTH) ? chain[DEPTH-1] : '0;
        always_ff @(posedge clk)if(advance)begin
            chain[0]<=write_word;
            for(int i=1;i<DEPTH;i=i+1)chain[i]<=chain[i-1];
        end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)filled<='0;
            else if(advance && filled!=FILL_W'(DEPTH))filled<=filled+FILL_W'(1);
        end
    end else begin: unchanged_deep_ram
        genefer_stream27_mdc_fifo_sync #(.WORD_W(WORD_W),.DEPTH(DEPTH)) original (
            .clk,.rst_n,.advance,.write_word,.head
        );
    end endgenerate
    // synthesis translate_off
    initial if(WORD_W<1 || DEPTH<1 || (DEPTH&(DEPTH-1))!=0)$fatal(1,"SM1_FIFO_PARAMETERS");
    // synthesis translate_on
endmodule
