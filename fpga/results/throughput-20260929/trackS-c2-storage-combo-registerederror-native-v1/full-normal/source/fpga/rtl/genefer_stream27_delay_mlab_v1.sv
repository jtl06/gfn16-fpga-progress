// P2 leaf: exact smallreg advance/head/reset calendar, MLAB only at D=4..32.
// Payload RAM and prefetch register are deliberately unreset. Filled masks
// stale words through D fresh advances. Addresses never collide at D>=4.
module genefer_stream27_delay_mlab_v1 #(
    parameter int unsigned WORD_W=38,
    parameter int unsigned DEPTH=4
) (
    input logic clk,rst_n,advance,
    input logic [WORD_W-1:0] write_word,
    output logic [WORD_W-1:0] head
);
    generate if(DEPTH<=2)begin: shallow_registers
        genefer_stream27_mdc_fifo_smallreg_v1 #(.WORD_W(WORD_W),.DEPTH(DEPTH)) original (
            .clk,.rst_n,.advance,.write_word,.head
        );
    end else if(DEPTH<=32)begin: short_mlab
        localparam int unsigned PTR_W=$clog2(DEPTH);
        localparam int unsigned FILL_W=$clog2(DEPTH+1);
        logic [PTR_W-1:0] pointer,next_pointer;
        logic [FILL_W-1:0] filled;
        (* ramstyle = "MLAB, no_rw_check" *) logic [WORD_W-1:0] memory[0:DEPTH-1];
        logic [WORD_W-1:0] prefetched;
        assign next_pointer=pointer+PTR_W'(1);
        assign head=filled==FILL_W'(DEPTH) ? prefetched : '0;
        always_ff @(posedge clk)if(advance)begin
            prefetched<=memory[next_pointer];
            memory[pointer]<=write_word;
        end
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)begin pointer<='0;filled<='0;end
            else if(advance)begin
                pointer<=next_pointer;
                if(filled!=FILL_W'(DEPTH))filled<=filled+FILL_W'(1);
            end
        end
    end else begin: unchanged_deep_ram
        genefer_stream27_mdc_fifo_sync #(.WORD_W(WORD_W),.DEPTH(DEPTH)) original (
            .clk,.rst_n,.advance,.write_word,.head
        );
    end endgenerate
    // synthesis translate_off
    initial if(WORD_W<1 || DEPTH<1 || (DEPTH&(DEPTH-1))!=0)$fatal(1,"P2_MLAB_PARAMETERS");
    // synthesis translate_on
endmodule
