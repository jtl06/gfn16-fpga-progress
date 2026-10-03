// Diagnostic shell: exact production watchdog plus preserved legacy policy.
module stream27_r15_watchdog_probe (
 input logic clk,rst_n,
 input logic [1:0] new_job,active,demand,aux_progress,stop,
 input logic [63:0] completed,
 input logic legacy_progress,
 output logic [1:0] error,
 output logic [29:0] ages,
 output logic legacy_error,
 output logic [31:0] legacy_age
);
 genefer_stream27_r15_progress_watchdog_v1 #(.CONTEXTS(2),.LIMIT(20480)) candidate
  (.clk,.rst_n,.new_job,.active,.demand,.aux_progress,.stop,.completed,.error,.ages);
 // Old host policy observed auxiliary events, not completed squares.
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin legacy_age<=0;legacy_error<=0;end
  else if(legacy_progress || (|new_job) || !(|active))legacy_age<=0;
  else if(legacy_age==20479)legacy_error<=1;
  else legacy_age<=legacy_age+1'b1;
 end
endmodule
