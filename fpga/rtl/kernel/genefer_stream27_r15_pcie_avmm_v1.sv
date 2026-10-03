// PRIVATE application endpoint. Addresses are BYTES relative to application
// apertures, not vendor BAR/descriptor addresses. No CDC or compute logic here.
// One 512-bit command holding register; one non-DATA response credit. Common
// reset/drain/session authority is owned by the shell/core executor.
module genefer_stream27_r15_pcie_avmm_v1 #(
 parameter integer N=65536
)(
 input logic clk, reset, link_ready,
 input logic [63:0] ctrl_address,
 input logic ctrl_read, ctrl_write,
 input logic [31:0] ctrl_writedata,
 input logic [3:0] ctrl_byteenable,
 output logic ctrl_waitrequest,
 output logic [31:0] ctrl_readdata,
 output logic ctrl_readdatavalid,
 input logic [63:0] cold_address,
 input logic cold_write,
 input logic [255:0] cold_writedata,
 input logic [31:0] cold_byteenable,
 input logic [4:0] cold_burstcount,
 output logic cold_waitrequest,
 input logic [63:0] export_address,
 input logic export_read,
 input logic [4:0] export_burstcount,
 output logic export_waitrequest,
 output logic [255:0] export_readdata,
 output logic export_readdatavalid,
 output logic cmd_valid,
 output logic [511:0] cmd_data,
 input logic cmd_ready,
 input logic resp_valid,
 input logic [511:0] resp_data,
 output logic resp_ready,
 output logic protocol_error
);
 localparam logic [3:0] DATA=0,BEGIN=1,COMMIT=2,CANCEL=3,START=4,
   SNAPSHOT=5,READ_A=6,DESCRIPTOR=7,ABORT=15;
 logic [31:0] hdr_context,hdr_owner_lo,hdr_owner_hi,hdr_count,hdr_base,
   hdr_generation,hdr_mode,hdr_mask,token_session,token_lease,start_mask;
 logic [31:0] desc_context,desc_index,desc_generation,desc_double;
 logic header_locked, waiting, abort_due,abort_sent;
 logic [3:0] waiting_op;
 logic waiting_context;
 logic [55:0] waiting_owner;
 logic [31:0] waiting_lease;
 logic [31:0] waiting_session;
 logic ctrl_response;
 logic [7:0] read_address;
 logic [511:0] snapshot;
 logic [55:0] owner_cache[0:1];
 logic [31:0] lease_cache[0:1];
 logic [1:0] cache_valid;
 logic [31:0] last_lease;
 logic [31:0] ingress_accepted;
 logic nonok_error;
 logic [4:0] cold_left,cold_total,export_left;
 logic [63:0] cold_base;
 logic export_context;
 logic [31:0] export_index;
 logic ctrl_stalled,cold_stalled,export_stalled;
 logic [101:0] held_ctrl;
 logic [357:0] held_cold;
 logic [69:0] held_export;
 wire [101:0] ctrl_payload={ctrl_address,ctrl_read,ctrl_write,ctrl_writedata,ctrl_byteenable};
 wire [357:0] cold_payload={cold_address,cold_write,cold_writedata,cold_byteenable,cold_burstcount};
 wire [69:0] export_payload={export_address,export_read,export_burstcount};
 wire ctrl_active=ctrl_read||ctrl_write;
 wire [31:0] status_word={18'b0,(export_left!=0),cmd_valid,snapshot[151:150],snapshot[149:148],
   snapshot[147:146],snapshot[145:144],header_locked,snapshot[152],protocol_error,link_ready};
 wire [31:0] error_word={29'b0,nonok_error,snapshot[152],protocol_error};
 // Exact used RESP bit mask: reject hidden/truncated authority/reserved bits.
 localparam logic [511:0] RESP_MASK =
   (512'hf << 0)|(512'hff << 8)|(512'h1 << 16)|
   (512'hffffffff << 32)|(512'hffffffff << 64)|(512'hffff << 96)|
   (512'hffffffff << 112)|(512'h1ff << 144)|
   (512'hffffffff << 160)|(512'hffffffff << 192)|
   (512'hffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff << 256);

 function automatic logic [511:0] packet(input logic [3:0] op,
   input logic c,input logic [55:0] own,input logic [31:0] session,lease,index,word,gen);
   logic [511:0] q;
   begin
    q='0;q[3:0]=op;q[4]=c;q[60:5]=own;q[92:61]=session;q[124:93]=lease;
    if(op==BEGIN)begin
     q[156:125]=hdr_count;q[188:157]=hdr_base;q[220:189]=hdr_mask;
     q[223:221]=hdr_mode[2:0];
    end
    q[255:224]=index;q[287:256]=word;q[319:288]=gen;
    packet=q;
   end
 endfunction
 function automatic logic address_known(input logic [7:0] a);
  begin address_known=(a<=8'h7c && a[1:0]==0); end
 endfunction
 function automatic logic [31:0] reg_read(input logic [7:0] a,input logic [511:0] s);
  begin
   case(a)
    8'h00:reg_read=32'h52313541;8'h04:reg_read=32'h00010000;
    8'h08:reg_read=s[63:32];
    8'h0c:reg_read={18'b0,(export_left!=0),cmd_valid,s[151:150],s[149:148],
      s[147:146],s[145:144],header_locked,s[152],protocol_error,link_ready};
    8'h10:reg_read=hdr_context;8'h14:reg_read=hdr_owner_lo;8'h18:reg_read=hdr_owner_hi;
    8'h1c:reg_read=hdr_count;8'h20:reg_read=hdr_base;8'h24:reg_read=hdr_generation;
    8'h28,8'h2c,8'h30,8'h34,8'h38,8'h3c,8'h40:reg_read=0;
    8'h44:reg_read=ingress_accepted;8'h48:reg_read=s[191:160];
    8'h4c:reg_read={29'b0,nonok_error,s[152],protocol_error};
    8'h50:reg_read=hdr_mode;
    8'h54:reg_read=hdr_context[0]?{16'b0,s[143:128]}:{16'b0,s[127:112]};
    8'h58:reg_read=(hdr_context[0]?{24'b0,s[111:104]}:{24'b0,s[103:96]})+32'd1;
    8'h5c:reg_read=last_lease;
    8'h60:reg_read=hdr_mask;8'h64:reg_read=token_session;8'h68:reg_read=token_lease;
    8'h6c:reg_read=start_mask;8'h70:reg_read=desc_context;8'h74:reg_read=desc_index;
    8'h78:reg_read=desc_generation;8'h7c:reg_read=desc_double;
    default:reg_read=0;
   endcase
  end
 endfunction
 task automatic fault;
  begin protocol_error<=1;if(!abort_sent)abort_due<=1; end
 endtask
 task automatic issue(input logic [511:0] q,input logic is_ctrl);
  begin
   cmd_data<=q;cmd_valid<=1;
   if(q[3:0]!=DATA)begin
    waiting<=1;waiting_op<=q[3:0];waiting_context<=q[4];waiting_owner<=q[60:5];
    waiting_lease<=q[124:93];waiting_session<=q[92:61];ctrl_response<=is_ctrl;
   end
  end
 endtask

 always_comb begin
  ctrl_waitrequest=reset||!link_ready||cmd_valid||waiting||export_left!=0||
   (cold_left!=0 && !(ctrl_write && ctrl_address==64'h40 && ctrl_writedata==2));
  cold_waitrequest=reset||!link_ready||protocol_error||cmd_valid||waiting||export_left!=0||ctrl_active;
  export_waitrequest=reset||!link_ready||protocol_error||cmd_valid||waiting||cold_left!=0||
   export_left!=0||ctrl_active||cold_write;
  resp_ready=!reset;
 end
 always_ff @(posedge clk)begin
  if(reset)begin
   cmd_valid<=0;cmd_data<=0;protocol_error<=0;abort_due<=0;abort_sent<=0;waiting<=0;waiting_op<=0;
   ctrl_response<=0;ctrl_readdatavalid<=0;ctrl_readdata<=0;export_readdatavalid<=0;export_readdata<=0;
   hdr_context<=0;hdr_owner_lo<=0;hdr_owner_hi<=0;hdr_count<=0;hdr_base<=0;hdr_generation<=0;
   hdr_mode<=0;hdr_mask<=0;token_session<=0;token_lease<=0;start_mask<=0;
   desc_context<=0;desc_index<=0;desc_generation<=0;desc_double<=0;
   header_locked<=0;read_address<=0;snapshot<=0;cache_valid<=0;last_lease<=0;nonok_error<=0;ingress_accepted<=0;
   waiting_context<=0;waiting_owner<=0;waiting_lease<=0;waiting_session<=0;
   owner_cache[0]<=0;owner_cache[1]<=0;lease_cache[0]<=0;lease_cache[1]<=0;
   cold_left<=0;cold_total<=0;cold_base<=0;export_left<=0;export_context<=0;export_index<=0;
   ctrl_stalled<=0;cold_stalled<=0;export_stalled<=0;held_ctrl<=0;held_cold<=0;held_export<=0;
  end else begin
   ctrl_readdatavalid<=0;export_readdatavalid<=0;
   if(cmd_valid&&cmd_ready)cmd_valid<=0;
   // Avalon masters must keep the current request+beat stable while stalled.
   if(ctrl_stalled && ctrl_payload!=held_ctrl)fault();
   if(cold_stalled && cold_payload!=held_cold)fault();
   if(export_stalled && export_payload!=held_export)fault();
   ctrl_stalled<=ctrl_active&&ctrl_waitrequest;held_ctrl<=ctrl_payload;
   cold_stalled<=cold_write&&cold_waitrequest;held_cold<=cold_payload;
   export_stalled<=export_read&&export_waitrequest;held_export<=export_payload;

   if(resp_valid)begin
    if(!waiting || resp_data[3:0]!=waiting_op || resp_data[16]!=waiting_context ||
       (resp_data&~RESP_MASK)!=0 || resp_data[15:8]>2)begin fault();end
    else begin
     snapshot<=resp_data;waiting<=0;
     if(resp_data[15:8]!=0)begin nonok_error<=1;fault();end
     if(waiting_op==BEGIN)begin
       if(resp_data[15:8]==0 && resp_data[95:64]!=0 && resp_data[63:32]==waiting_session)begin
       last_lease<=resp_data[95:64]-1;lease_cache[waiting_context]<=resp_data[95:64]-1;
       owner_cache[waiting_context]<=waiting_owner;cache_valid[waiting_context]<=1;ingress_accepted<=0;
      end else begin header_locked<=0;cache_valid[waiting_context]<=0;fault();end
     end
     if(waiting_op==COMMIT || waiting_op==CANCEL)header_locked<=0;
     if(waiting_op==CANCEL)cache_valid[waiting_context]<=0;
     if(ctrl_response)begin ctrl_readdata<=reg_read(read_address,resp_data);ctrl_readdatavalid<=1;end
     if(waiting_op==READ_A)begin
      export_readdatavalid<=1;
      if(resp_data[15:8]==0 && !protocol_error &&
         resp_data[287:256]==(32'h52314100|{31'b0,export_context}) &&
         resp_data[63:32]==waiting_session &&
         resp_data[319:288]==resp_data[63:32] &&
         resp_data[375:320]==owner_cache[export_context] && resp_data[383:376]==0 &&
         resp_data[415:384]==export_index)begin export_readdata<=resp_data[511:256];end
      else begin export_readdata<=0;fault();end
      export_index<=export_index+1;export_left<=export_left-1;
     end
    end
   end

   if(!cmd_valid && !waiting)begin
    if(abort_due)begin
     issue(packet(ABORT,hdr_context[0],0,snapshot[63:32],0,0,0,0),0);abort_due<=0;abort_sent<=1;
    end else if(protocol_error && export_left!=0)begin
     // Complete accepted Avalon read beats with INVALID records on failure.
     // The host sees sticky ERROR and must not interpret these as A32 payload.
     export_readdata<=0;export_readdatavalid<=1;export_left<=export_left-1;
    end else if(export_left!=0 && !protocol_error)begin
     issue(packet(READ_A,export_context,owner_cache[export_context],snapshot[63:32],
       lease_cache[export_context],export_index,0,0),0);
    end else if(ctrl_active&&!ctrl_waitrequest)begin
     if(ctrl_address[63:8]!=0 || !address_known(ctrl_address[7:0]) ||
        ctrl_byteenable!=4'hf || (ctrl_read&&ctrl_write))begin
      fault();if(ctrl_read)begin ctrl_readdatavalid<=1;ctrl_readdata<=0;end
     end else if(ctrl_read)begin
      read_address<=ctrl_address[7:0];
      if(protocol_error || ctrl_address==0 || ctrl_address==4)begin
       ctrl_readdata<=reg_read(ctrl_address[7:0],snapshot);ctrl_readdatavalid<=1;
      end else issue(packet(SNAPSHOT,hdr_context[0],0,0,0,0,0,0),1);
     end else if(protocol_error)begin /* reset required; no new authority */ end
     else if(ctrl_address==64'h40)begin
      case(ctrl_writedata)
       1:if(header_locked || cold_left!=0 || hdr_context>1 || hdr_owner_hi[31:24]!=0 ||
            hdr_mode>7 || hdr_generation>255)fault();
         else begin header_locked<=1;cache_valid[hdr_context[0]]<=0;
          issue(packet(BEGIN,hdr_context[0],{hdr_owner_hi[23:0],hdr_owner_lo},token_session,
           snapshot[95:64],0,0,hdr_generation),0);end
       2:if(cold_left!=0)fault();else issue(packet(COMMIT,hdr_context[0],
         {hdr_owner_hi[23:0],hdr_owner_lo},token_session,token_lease,0,0,hdr_generation),0);
       3:issue(packet(CANCEL,hdr_context[0],{hdr_owner_hi[23:0],hdr_owner_lo},token_session,
         token_lease,0,0,hdr_generation),0);
       4:if(start_mask==0 || start_mask>3 || header_locked)fault();
         else issue(packet(START,0,0,token_session,token_lease,start_mask,0,0),0);
       7:if(desc_context>1 || desc_generation>255 || desc_double>1)fault();
         else issue(packet(DESCRIPTOR,desc_context[0],0,token_session,token_lease,
           desc_index,desc_double,desc_generation),0);
       default:fault();
      endcase
     end else if(header_locked && ctrl_address!=64'h64 && ctrl_address!=64'h68)fault();
     else begin
      case(ctrl_address[7:0])
       8'h10:if(ctrl_writedata>1)fault();else hdr_context<=ctrl_writedata;
       8'h14:hdr_owner_lo<=ctrl_writedata;
       8'h18:if(ctrl_writedata[31:24]!=0)fault();else hdr_owner_hi<=ctrl_writedata;
       8'h1c:hdr_count<=ctrl_writedata;8'h20:hdr_base<=ctrl_writedata;8'h24:hdr_generation<=ctrl_writedata;
       8'h50:hdr_mode<=ctrl_writedata;8'h60:hdr_mask<=ctrl_writedata;
       8'h64:token_session<=ctrl_writedata;8'h68:token_lease<=ctrl_writedata;8'h6c:start_mask<=ctrl_writedata;
       8'h70:desc_context<=ctrl_writedata;8'h74:desc_index<=ctrl_writedata;
       8'h78:desc_generation<=ctrl_writedata;8'h7c:desc_double<=ctrl_writedata;
       8'h28,8'h2c,8'h30,8'h34,8'h38,8'h3c:if(ctrl_writedata!=0)fault();
       default:fault();
      endcase
     end
    end else if(cold_write&&!cold_waitrequest)begin
     if(!header_locked || cold_address[63:22]!=0 || cold_address[4:0]!=0 ||
        cold_byteenable!=32'hffffffff || cold_burstcount==0 ||
        (cold_left==0 && ({1'b0,cold_address[21:0]}+({18'b0,cold_burstcount}<<5))>23'h400000) ||
        (cold_left!=0 && (cold_address!=cold_base || cold_burstcount!=cold_total)) ||
        (cold_writedata[31:0]!=32'h52315000 && cold_writedata[31:0]!=32'h52315001) ||
        cold_writedata[159:152]!=0 || cold_writedata[255:224]!=0 || cold_writedata[191:160]>=N+32)
      fault();
     else begin
      if(cold_left==0)begin cold_base<=cold_address;cold_total<=cold_burstcount;cold_left<=cold_burstcount-1;end
      else cold_left<=cold_left-1;
      ingress_accepted<=ingress_accepted+1;
      issue(packet(DATA,cold_writedata[0],cold_writedata[151:96],cold_writedata[63:32],
        cold_writedata[95:64],cold_writedata[191:160],cold_writedata[223:192],0),0);
     end
    end else if(export_read&&!export_waitrequest)begin
     if(export_address[63:23]!=0 || export_address[4:0]!=0 || export_burstcount==0 ||
        ({1'b0,export_address[21:5]}+{13'b0,export_burstcount})>N || !cache_valid[export_address[22]])begin
      fault();export_left<=export_burstcount==0?5'd1:export_burstcount;
     end
     else begin export_context<=export_address[22];export_index<={15'b0,export_address[21:5]};export_left<=export_burstcount;end
    end
   end
  end
 end
endmodule
