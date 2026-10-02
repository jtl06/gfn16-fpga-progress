// Stage-shared E5/E6 owner transport. Caller retains all valid/fault authority.
// Invalid generation presentation is not an occupied owner token.
module genefer_stream27_stage_owner_pipe_compact_v2 #(
 parameter int unsigned GEN_W=25,PIPE_WORDS=6,FRAME_T=4096
) (
 input logic clk,rst_n,advance,in_slot_valid,frame_start,
 input logic [GEN_W-1:0] generation_in,
 output wire [GEN_W-1:0] generation_out
);
 if(FRAME_T<PIPE_WORDS)begin: literal_small_frame
  logic [GEN_W-1:0] generation_pipe[0:PIPE_WORDS-1];
  always_ff @(posedge clk)if(rst_n && advance)begin
   generation_pipe[0]<=generation_in;
   for(int k=1;k<PIPE_WORDS;k=k+1)generation_pipe[k]<=generation_pipe[k-1];
  end
  assign generation_out=generation_pipe[PIPE_WORDS-1];
 end else begin: compact_frame
  logic [GEN_W-1:0] owner0,owner1;
  logic [PIPE_WORDS-1:0] color_pipe;
  logic frame_color,next_color;
  wire selected_color=frame_start ? next_color : frame_color;
  always_ff @(posedge clk or negedge rst_n)begin
   if(!rst_n)begin frame_color<=0;next_color<=0;end
   else if(advance && in_slot_valid && frame_start)begin
    frame_color<=selected_color;next_color<=!next_color;
   end
  end
  // Payload holds on reset. Caller flushes its slot/start validity separately.
  always_ff @(posedge clk)if(rst_n && advance)begin
   color_pipe<={color_pipe[PIPE_WORDS-2:0],selected_color};
   if(in_slot_valid && frame_start)begin
    if(selected_color)owner1<=generation_in;else owner0<=generation_in;
   end
  end
  // PRE-edge decode retains an admitted tail before a same-edge owner write.
  assign generation_out=color_pipe[PIPE_WORDS-1] ? owner1 : owner0;
 end
 // synthesis translate_off
 initial if(GEN_W<1 || (PIPE_WORDS!=6 && PIPE_WORDS!=7) || FRAME_T<1)
  $fatal(1,"STAGE_OWNER_PIPE_PARAMETERS");
 // synthesis translate_on
endmodule
