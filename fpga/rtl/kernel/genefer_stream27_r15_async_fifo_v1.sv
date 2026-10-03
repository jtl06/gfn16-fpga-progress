// Private bounded PCIe/core CDC transport, not a vendor-IP replacement.
// Common FIFO reset asynchronously asserts in BOTH domains; each domain
// synchronizes release. enable must remain low through the session/drain
// handshake. Changing enable does not flush data; reset is required to flush.
// No payload reset. Physical CDC timing/skew constraints and native two-clock
// tests remain mandatory before integration/promotion.
module genefer_stream27_r15_async_fifo_v1 #(
 parameter int WIDTH=256,ADDR_W=3
) (
 input logic rst_n,wr_clk,rd_clk,wr_enable,rd_enable,
 input logic wr_valid,input logic [WIDTH-1:0] wr_data,
 output logic wr_ready,
 output logic rd_valid,output logic [WIDTH-1:0] rd_data,
 input logic rd_ready
);
 localparam int PW=ADDR_W+1,DEPTH=1<<ADDR_W;
 logic [WIDTH-1:0] data[0:DEPTH-1];
 logic [PW-1:0] wbin,wgray,rbin,rgray;
 logic [PW-1:0] rgray_w1,rgray_w2,wgray_r1,wgray_r2;
 logic [1:0] wr_release,rd_release;
 logic full,empty;
 wire push=wr_valid && wr_ready,pop=rd_valid && rd_ready;
 wire [PW-1:0] wnext=wbin+PW'(push),rnext=rbin+PW'(pop);
 wire [PW-1:0] wgray_next=(wnext>>1)^wnext,rgray_next=(rnext>>1)^rnext;
 wire [PW-1:0] full_compare=rgray_w2 ^ (PW'(3)<<(PW-2));
 assign wr_ready=rst_n && wr_release[1] && wr_enable && !full;
 assign rd_valid=rst_n && rd_release[1] && rd_enable && !empty;
 assign rd_data=data[rbin[ADDR_W-1:0]];
 always_ff @(posedge wr_clk or negedge rst_n)begin
  if(!rst_n)begin
   wr_release<=0;rgray_w1<=0;rgray_w2<=0;wbin<=0;wgray<=0;full<=0;
  end else begin
   wr_release<={wr_release[0],1'b1};
   rgray_w1<=rgray;rgray_w2<=rgray_w1;
   if(wr_release[1])begin
    wbin<=wnext;wgray<=wgray_next;full<=wgray_next==full_compare;
   end
  end
 end
 always_ff @(posedge wr_clk)if(push)data[wbin[ADDR_W-1:0]]<=wr_data;
 always_ff @(posedge rd_clk or negedge rst_n)begin
  if(!rst_n)begin
   rd_release<=0;wgray_r1<=0;wgray_r2<=0;rbin<=0;rgray<=0;empty<=1;
  end else begin
   rd_release<={rd_release[0],1'b1};
   wgray_r1<=wgray;wgray_r2<=wgray_r1;
   if(rd_release[1])begin
    rbin<=rnext;rgray<=rgray_next;empty<=rgray_next==wgray_r2;
   end
  end
 end
 // synthesis translate_off
 initial if(ADDR_W<2 || ADDR_W>5 || WIDTH<1 || WIDTH>512)
  $fatal(1,"R15_CDC_SMALL_FIFO_GEOMETRY");
 // synthesis translate_on
endmodule
