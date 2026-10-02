// Source-only S-M1 pilot: all supported short depths plus unchanged deep fallback.
module stream27_sm1_fifo_probe_v1 (
    input logic clk,rst_n,advance,
    input logic [37:0] write_word,
    output logic [6:0] mismatch,
    output logic [265:0] heads
);
    for(genvar i=0;i<7;i=i+1)begin: depths
        wire [37:0] reference_head,candidate_head;
        genefer_stream27_mdc_fifo_sync #(.WORD_W(38),.DEPTH(1<<i)) reference_fifo (
            .clk,.rst_n,.advance,.write_word,.head(reference_head));
        genefer_stream27_mdc_fifo_smallreg_v1 #(.WORD_W(38),.DEPTH(1<<i)) candidate_fifo (
            .clk,.rst_n,.advance,.write_word,.head(candidate_head));
        assign mismatch[i]=reference_head!=candidate_head;
        assign heads[i*38+:38]=candidate_head;
    end
endmodule
