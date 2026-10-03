// Common board/HIP/PLL reset fences both FIFO directions and the entire core.
// SESSION_SEED is0 in production; initialization is FPGA configuration state,
// not PERST state. Host must tear down DMA arenas across FPGA reconfiguration.
// Session survives ordinary PERST and never wraps. No FLR support is inferred
// unless that actual vendor event is explicitly connected to external_reset_n.
module genefer_stream27_r15_link_reset_v1 #(
 parameter logic [31:0] SESSION_SEED=32'd0
)(
 input logic pcie_clk,core_clk,external_reset_n,
 output logic common_reset_n,pcie_ready,core_ready,
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
 assign pcie_ready=pcie_release[1] && core_ready_p2 && common_reset_n;
 assign core_ready=core_release[1] && pcie_ready_c2 && common_reset_n;
 always_ff @(posedge pcie_clk or negedge external_reset_n)begin
  if(!external_reset_n)begin bootstrap<=0;recovery_pending<=1;end
  else begin
   bootstrap<={bootstrap[0],1'b1};
   if(bootstrap[1])recovery_pending<=0;
  end
 end
 // Deliberately not asynchronously reset by PERST; first released clock burns
 // a fresh transport session before common_reset_n can release either domain.
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
