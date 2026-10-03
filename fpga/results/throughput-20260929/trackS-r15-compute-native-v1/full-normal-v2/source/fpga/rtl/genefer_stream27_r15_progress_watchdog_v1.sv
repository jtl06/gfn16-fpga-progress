// Minimal per-context liveness, not arithmetic protection or host GL.
module genefer_stream27_r15_progress_watchdog_v1 #(
 parameter int CONTEXTS=2,LIMIT=20480,AGE_W=$clog2(LIMIT+1)
) (
 input logic clk,rst_n,
 input logic [CONTEXTS-1:0] new_job,active,demand,aux_progress,stop,
 input logic [CONTEXTS*32-1:0] completed,
 output logic [CONTEXTS-1:0] error,
 output logic [CONTEXTS*AGE_W-1:0] ages
);
 logic [31:0] completed_seen[0:CONTEXTS-1];
 logic [AGE_W-1:0] age[0:CONTEXTS-1];
 for(genvar c=0;c<CONTEXTS;c++)begin: context_watch
  assign ages[c*AGE_W+:AGE_W]=age[c];
  // A decreasing counter is not progress. Accepted new-job/reset is explicit.
  wire square_progress=completed[c*32+:32]>completed_seen[c];
  always_ff @(posedge clk or negedge rst_n)begin
   if(!rst_n)begin completed_seen[c]<=0;age[c]<=0;error[c]<=0;end
   else begin
    completed_seen[c]<=new_job[c] ? 32'd0 : completed[c*32+:32];
    // Stop/cancel disarms elapsed age, but never clears a sticky failure.
    if(new_job[c] || !active[c] || stop[c] || !demand[c] ||
       square_progress || aux_progress[c])age[c]<=0;
    else if(age[c]==AGE_W'(LIMIT-1))error[c]<=1;
    else age[c]<=age[c]+1'b1;
   end
  end
 end
endmodule
