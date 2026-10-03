// PRIVATE full64 byte-address guard BEFORE Qsys64->25 address narrowing.
// Coarse apertures only: cold DATA framing/range/owner remains application-owned.
// One write-beat and one read-request hold register, no payload-sized staging.
// Previously admitted/offered downstream VALID stays held through fault until
// acceptance/reset. No new host work forwards after fault. No physical rollback.
module genefer_stream27_r15_dma_aperture_v1(
 input logic clk,reset,
 input logic [63:0] wr_address,
 input logic wr_write,
 input logic [255:0] wr_writedata,
 input logic [31:0] wr_byteenable,
 input logic [4:0] wr_burstcount,
 output logic wr_waitrequest,
 output logic [63:0] down_wr_address,
 output logic down_wr_write,
 output logic [255:0] down_wr_writedata,
 output logic [31:0] down_wr_byteenable,
 output logic [4:0] down_wr_burstcount,
 input logic down_wr_waitrequest,
 input logic [63:0] rd_address,
 input logic rd_read,
 input logic [4:0] rd_burstcount,
 output logic rd_waitrequest,
 output logic [255:0] rd_readdata,
 output logic rd_readdatavalid,
 output logic [63:0] down_rd_address,
 output logic down_rd_read,
 output logic [4:0] down_rd_burstcount,
 input logic down_rd_waitrequest,
 input logic [255:0] down_rd_readdata,
 input logic down_rd_readdatavalid,
 output logic fault_valid,
 input logic fault_ready,
 output logic protocol_error
);
 logic wr_hold,rd_hold;
 logic [63:0] wr_base;
 logic [4:0] wr_total,wr_left;
 logic rd_active,rd_local_zero;
 logic [4:0] rd_left,rd_expected;
 logic [255:0] rd_data_q;
 logic fault_pending,fault_sent,wr_bad_pending,rd_bad_pending;
 logic [4:0] wr_bad_count,rd_bad_count;
 logic wr_stalled,rd_stalled;
 logic [357:0] held_wr;
 logic [69:0] held_rd;
 wire [357:0] offered_wr={(wr_left==0?wr_address:64'b0),wr_write,wr_writedata,
   wr_byteenable,(wr_left==0?wr_burstcount:5'b0)};
 wire [69:0] offered_rd={rd_address,rd_read,rd_burstcount};
 function automatic logic range_ok(input logic [63:0] a,input logic [4:0] count,input logic write_bus);
  logic [64:0] e;
  begin
   e={1'b0,a}+({60'b0,count}<<5);
   if(write_bus)range_ok=(count!=0) &&
    ((a<64'h400000 && e<=65'h400000) ||
     (a>=64'h1000000 && a<64'h1002000 && e<=65'h1002000) ||
     (a>=64'h1002000 && a<64'h1004000 && e<=65'h1004000));
   else range_ok=(count!=0) && a<64'h800000 && e<=65'h800000;
  end
 endfunction
 wire bad_wr_first=!protocol_error && wr_write && wr_left==0 && !wr_bad_pending && !range_ok(wr_address,wr_burstcount,1);
 wire bad_rd_first=!protocol_error && rd_read && !rd_active && !rd_bad_pending && !range_ok(rd_address,rd_burstcount,0);
 wire held_bad=(wr_stalled && offered_wr!=held_wr) || (rd_stalled && offered_rd!=held_rd);
 wire down_wr_fire=down_wr_write && !down_wr_waitrequest;
 wire down_rd_fire=down_rd_read && !down_rd_waitrequest;
 wire response_credit=(rd_expected!=0) || down_rd_fire;
 wire stray_response=down_rd_readdatavalid && !response_credit;
 wire current_error=!protocol_error && (bad_wr_first || bad_rd_first || held_bad || stray_response);
 wire terminal=protocol_error || current_error;
 wire fault_accept=fault_valid && fault_ready;
 wire wr_fire=wr_write && !wr_waitrequest;
 wire rd_fire=rd_read && !rd_waitrequest;
 wire [4:0] effective_wr_count=wr_bad_pending?wr_bad_count:(wr_burstcount==0?5'd1:wr_burstcount);
 wire [4:0] effective_rd_count=rd_bad_pending?rd_bad_count:(rd_burstcount==0?5'd1:rd_burstcount);

 always_comb begin
  // fault_ready is the same-domain application's !reset && pcie_ready.
  // fault_valid never depends on fault_ready, so no readiness feedback loop.
  fault_valid=!reset && !fault_sent && (fault_pending || current_error);
  down_wr_write=!reset && wr_hold;
  down_rd_read=!reset && rd_hold;
  // A response staged on the prior edge loses data authority immediately at
  // a new fault origin, even before the sticky bit's next clock assignment.
  rd_readdata=terminal?256'b0:rd_data_q;
  wr_waitrequest=1;rd_waitrequest=1;
  if(!reset && fault_ready)begin
   if(!terminal)begin wr_waitrequest=wr_hold;rd_waitrequest=rd_active;end
   else begin
    // Fault-origin invalid first requests (or their held pending copies) and
    // already-admitted writeburst tails drain locally, never through Qsys.
    if(wr_left!=0 || wr_bad_pending || bad_wr_first)wr_waitrequest=0;
    if(!rd_active && (rd_bad_pending || bad_rd_first))rd_waitrequest=0;
   end
  end
 end
 always_ff @(posedge clk)begin
  if(reset)begin
   wr_hold<=0;rd_hold<=0;wr_base<=0;wr_total<=0;wr_left<=0;
   down_wr_address<=0;down_wr_writedata<=0;down_wr_byteenable<=0;down_wr_burstcount<=0;
   down_rd_address<=0;down_rd_burstcount<=0;rd_active<=0;rd_local_zero<=0;rd_left<=0;rd_expected<=0;
   rd_data_q<=0;rd_readdatavalid<=0;protocol_error<=0;fault_pending<=0;fault_sent<=0;
   wr_bad_pending<=0;rd_bad_pending<=0;wr_bad_count<=0;rd_bad_count<=0;
   wr_stalled<=0;rd_stalled<=0;held_wr<=0;held_rd<=0;
  end else begin
   rd_readdatavalid<=0;
   wr_stalled<=wr_write && wr_waitrequest;held_wr<=offered_wr;
   rd_stalled<=rd_read && rd_waitrequest;held_rd<=offered_rd;
   if(current_error)begin protocol_error<=1;if(!fault_sent)fault_pending<=1;end
   if(fault_accept)begin fault_pending<=0;fault_sent<=1;end
   if(bad_wr_first && !wr_fire && !protocol_error)begin
    wr_bad_pending<=1;wr_bad_count<=wr_burstcount==0?5'd1:wr_burstcount;
   end
   if(bad_rd_first && !rd_fire && !protocol_error)begin
    rd_bad_pending<=1;rd_bad_count<=rd_burstcount==0?5'd1:rd_burstcount;
   end
   if(down_wr_fire)wr_hold<=0;
   if(down_rd_fire)begin rd_hold<=0;rd_expected<=down_rd_burstcount;end
   if(wr_fire)begin
    if(wr_left==0)begin wr_base<=wr_address;wr_total<=effective_wr_count;wr_left<=effective_wr_count-1;end
    else wr_left<=wr_left-1;
    wr_bad_pending<=0;
    if(!terminal)begin
     wr_hold<=1;down_wr_address<=wr_left==0?wr_address:wr_base;
     down_wr_burstcount<=wr_left==0?wr_burstcount:wr_total;
     down_wr_writedata<=wr_writedata;down_wr_byteenable<=wr_byteenable;
    end
   end
   if(rd_fire)begin
    rd_active<=1;rd_left<=effective_rd_count;rd_bad_pending<=0;
    if(!terminal)begin rd_hold<=1;rd_local_zero<=0;down_rd_address<=rd_address;down_rd_burstcount<=rd_burstcount;end
    else rd_local_zero<=1;
   end
   if(down_rd_readdatavalid && response_credit)begin
    rd_readdatavalid<=1;rd_data_q<=terminal?256'b0:down_rd_readdata;
    rd_expected<=(down_rd_fire?down_rd_burstcount:rd_expected)-1;
    rd_left<=rd_left-1;if(rd_left==1)rd_active<=0;
   end else if(rd_active && rd_local_zero && fault_sent)begin
    rd_readdatavalid<=1;rd_data_q<=0;
    rd_left<=rd_left-1;if(rd_left==1)begin rd_active<=0;rd_local_zero<=0;end
   end
  end
 end
endmodule
