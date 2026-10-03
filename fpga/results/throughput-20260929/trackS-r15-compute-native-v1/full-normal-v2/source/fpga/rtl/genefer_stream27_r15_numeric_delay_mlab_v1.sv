module genefer_stream27_r15_numeric_delay_mlab_v1 #(
 parameter int unsigned WORD_W=27,DELAY=6)(
 input logic clk,rst_n,input logic [WORD_W-1:0] write_word,
 output wire [WORD_W-1:0] head);
 // Eight physical slots, DELAY5/6 logical edges. Read offset4/3 is
 // unconditionally distinct from write pointer, including reset/bad inputs.
 localparam logic [2:0] READ_OFFSET=3'(9-DELAY);
 logic [2:0] pointer,filled;
 wire [2:0] read_pointer=pointer+READ_OFFSET;
 (* ramstyle="MLAB, no_rw_check" *) logic [WORD_W-1:0] memory[0:7];
 logic [WORD_W-1:0] prefetched;
 assign head=filled==3'(DELAY) ? prefetched : '0;
 always_ff @(posedge clk)begin
  prefetched<=memory[read_pointer];memory[pointer]<=write_word;
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin pointer<=0;filled<=0;end
  else begin pointer<=pointer+3'd1;if(filled!=3'(DELAY))filled<=filled+3'd1;end
 end
 // synthesis translate_off
 initial if(WORD_W<1 || (DELAY!=5 && DELAY!=6))$fatal(1,"R15_NUMERIC_DELAY_PARAMETERS");
 // synthesis translate_on
endmodule
