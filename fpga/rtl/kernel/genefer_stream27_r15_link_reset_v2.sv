// Private additive reset-release repair. Common reset ASSERTS asynchronously;
// application reset DEASSERTS only after two edges in its own clock domain.
// Session survives ordinary PERST, not FPGA reconfiguration. No wrap/reuse.
module genefer_stream27_r15_link_reset_v2 #(
 parameter logic [31:0] SESSION_SEED=32'd0
)(
 input logic pcie_clk,core_clk,external_reset_n,
 output logic common_reset_n,pcie_reset_n,core_reset_n,pcie_ready,core_ready,
 output logic [31:0] session,
 output logic exhausted
);
 logic [31:0] session_counter=SESSION_SEED;
 logic session_exhausted=1'b0;
 logic recovery_pending;
 logic [1:0] bootstrap,pcie_release,core_release;
 logic core_ready_p1,core_ready_p2,pcie_ready_c1,pcie_ready_c2;
 assign session=session_counter;
 assign exhausted=session_exhausted;
 assign common_reset_n=external_reset_n && bootstrap[1] && !recovery_pending && !session_exhausted;
 assign pcie_reset_n=pcie_release[1] && common_reset_n;
 assign core_reset_n=core_release[1] && common_reset_n;
 assign pcie_ready=pcie_reset_n && core_ready_p2;
 assign core_ready=core_reset_n && pcie_ready_c2;
 always_ff @(posedge pcie_clk or negedge external_reset_n)begin
  if(!external_reset_n)begin bootstrap<=0;recovery_pending<=1;end
  else begin
   bootstrap<={bootstrap[0],1'b1};
   if(bootstrap[1])recovery_pending<=0;
  end
 end
 always_ff @(posedge pcie_clk)begin
  if(external_reset_n && bootstrap[1] && recovery_pending && !session_exhausted)begin
   if(session_counter==32'hffffffff)session_exhausted<=1;
   else session_counter<=session_counter+32'd1;
  end
 end
 always_ff @(posedge pcie_clk or negedge common_reset_n)begin
  if(!common_reset_n)begin pcie_release<=0;core_ready_p1<=0;core_ready_p2<=0;end
  else begin
   pcie_release<={pcie_release[0],1'b1};
   core_ready_p1<=core_release[1];core_ready_p2<=core_ready_p1;
  end
 end
 always_ff @(posedge core_clk or negedge common_reset_n)begin
  if(!common_reset_n)begin core_release<=0;pcie_ready_c1<=0;pcie_ready_c2<=0;end
  else begin
   core_release<={core_release[0],1'b1};
   pcie_ready_c1<=pcie_release[1];pcie_ready_c2<=pcie_ready_c1;
  end
 end
endmodule
