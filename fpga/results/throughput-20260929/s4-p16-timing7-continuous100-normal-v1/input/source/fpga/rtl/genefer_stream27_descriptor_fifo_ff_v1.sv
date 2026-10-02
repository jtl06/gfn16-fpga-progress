// Exact depth-four descriptor ring. No added head latency or empty bypass.
// Payload is intentionally unreset; level alone qualifies head ownership.
module genefer_stream27_descriptor_fifo_ff_v1 (
 input logic clk,rst_n,clear,push,pop,
 input logic [31:0] push_index,
 input logic [7:0] push_generation,
 input logic push_double,
 output logic [31:0] head_index,
 output logic [7:0] head_generation,
 output logic head_double,
 output logic [2:0] level
);
 logic [1:0] read_pointer,write_pointer;
 (* ramstyle="logic" *) logic [40:0] descriptor[0:3];
 for(genvar slot=0;slot<4;slot=slot+1)begin: bank
  always_ff @(posedge clk)
   if(rst_n && !clear && push && write_pointer==2'(slot))
    descriptor[slot]<={push_index,push_generation,push_double};
 end
 assign {head_index,head_generation,head_double}=descriptor[read_pointer];
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin read_pointer<=0;write_pointer<=0;level<=0;end
  else if(clear)begin read_pointer<=0;write_pointer<=0;level<=0;end
  else begin
   if(push)write_pointer<=write_pointer+2'd1;
   if(pop)read_pointer<=read_pointer+2'd1;
   case({push,pop})
    2'b10:level<=level+3'd1;
    2'b01:level<=level-3'd1;
    default:begin end
   endcase
  end
 end
 // Push/pop legality belongs to unchanged host command_ready/feed_pop.
 // Clear wins and suppresses payload writes, including malformed clear+push.
endmodule
