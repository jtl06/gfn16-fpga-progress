// Private core-domain command executor. Ordered512 FIFO encoding is specified
// by stream27_r15_shell_packets_v1.py. No PCIe IP, N-sized staging or warm stall.
module genefer_stream27_r15_core_transport_v1 #(parameter int AW=8,P=16)(
 input logic clk,rst_n,link_ready,input logic [31:0] session,
 input logic cmd_valid,input logic [511:0] cmd_data,output logic cmd_ready,
 input logic cmd_empty,
 output logic resp_valid,output logic [511:0] resp_data,input logic resp_ready,
 output logic transport_error,
 output logic dc_link_drained,dc_begin,dc_cancel,dc_commit,dc_word_valid,dc_context,
 output logic [55:0] dc_owner,
 output logic [31:0] dc_session,dc_lease,dc_current_session,dc_count,dc_mask,
 output logic [2:0] dc_mode,output logic [255:0] dc_profile,
 output logic [AW+1:0] dc_index,output logic [31:0] dc_word,
 output logic dc_transport_empty,
 input logic dc_word_ready,dc_active,dc_error,
 input logic [1:0] dc_loaded,dc_idle,
 input logic [31:0] dc_next_epoch,dc_next_lease,
 input logic [15:0] dc_job_generation,input logic [AW+2:0] dc_applied,
 output logic [1:0] start_contexts,
 output logic command_context,command_valid,command_double,
 output logic [31:0] command_index,output logic [7:0] command_generation,
 input logic command_ready,command_accept,
 output logic host_context,read_en,output logic [AW-1:0] host_addr,
 input logic read_valid,read_context,input logic [55:0] read_owner,input logic [95:0] read_data,
 input logic core_error,input logic [1:0] busy,canonical_ready
);
 localparam int N=1<<AW;
 localparam logic [3:0] DATA=0,BEGIN_LOAD=1,COMMIT_LOAD=2,CANCEL_LOAD=3,
  START_JOB=4,SNAPSHOT=5,READ_A=6,DESCRIPTOR=7,ABORT_LINK=15;
 typedef enum logic [3:0] {IDLE,EXECUTE,WAIT_BEGIN,WAIT_COMMIT,WAIT_CANCEL,
                           WAIT_START,WAIT_READ,WAIT_DESCRIPTOR,RESPOND} state_t;
 state_t state;
 logic [511:0] held;
 logic sticky_error;
 logic [31:0] accepted;
 logic [6:0] wait_count;
 logic [1:0] cache_valid;
 logic [55:0] cache_owner[0:1];
 logic [31:0] cache_lease[0:1],cache_session[0:1];
 wire [3:0] op=held[3:0];
 wire ctx=held[4];wire [55:0] owner=held[60:5];
 wire [31:0] token_session=held[92:61],token_lease=held[124:93];
 wire [31:0] count=held[156:125],base=held[188:157],mask=held[220:189];
 wire [2:0] mode=held[223:221];
 wire [31:0] index=held[255:224],word_value=held[287:256],generation=held[319:288];
 wire [1:0] start_mask=index[1:0];
 wire fatal_now=sticky_error || core_error || dc_error;
 wire reserved_good=held[511:320]==0;
 wire current_token=token_session==session;
 wire read_good=current_token && cache_valid[ctx] && cache_session[ctx]==session &&
  cache_owner[ctx]==owner && cache_lease[ctx]==token_lease && index<32'(N);
 wire start_good=current_token && dc_next_lease!=0 && token_lease==dc_next_lease-32'd1 &&
  index[31:2]==0 && start_mask!=0 && (start_mask & ~dc_loaded)==0 &&
  (start_mask & ~cache_valid)==0 && (&dc_idle) && !dc_active;
 wire execute_good=state==EXECUTE && !fatal_now && reserved_good && link_ready;
 assign transport_error=fatal_now;
 assign dc_link_drained=link_ready && !sticky_error;
 assign cmd_ready=state==IDLE && link_ready && resp_ready;
 assign resp_valid=state==RESPOND && link_ready;
 assign dc_begin=execute_good && op==BEGIN_LOAD && current_token;
 assign dc_cancel=execute_good && op==CANCEL_LOAD && current_token;
 assign dc_commit=execute_good && op==COMMIT_LOAD && current_token && cmd_empty;
 assign dc_word_valid=execute_good && op==DATA && current_token && index<32'(N+32);
 assign dc_context=ctx;assign dc_owner=owner;assign dc_session=token_session;assign dc_lease=token_lease;
 assign dc_current_session=session;assign dc_count=count;assign dc_mask=mask;assign dc_mode=mode;
 assign dc_profile={192'b0,generation,base};
 assign dc_index=index[AW+1:0];assign dc_word=word_value;assign dc_transport_empty=cmd_empty;
 assign start_contexts=execute_good && op==START_JOB && start_good ? start_mask:2'b0;
 assign command_context=ctx;assign command_double=word_value[0];assign command_index=index;
 assign command_generation=generation[7:0];
 assign command_valid=(state==EXECUTE || state==WAIT_DESCRIPTOR) && op==DESCRIPTOR &&
  !fatal_now && reserved_good && current_token && generation[31:8]==0 && word_value[31:1]==0 && busy[ctx] && link_ready;
 assign host_context=ctx;assign host_addr=index[AW-1:0];
 assign read_en=execute_good && op==READ_A && read_good && !dc_active &&
  dc_idle[ctx] && canonical_ready[ctx];

 // Captures all status at one core edge. Payload remains stable through a
 // response stall, even if a later unrelated fault arises. No wire revocation.
 task automatic respond(input logic [7:0] status,input logic [255:0] data);
  begin
   resp_data<='0;resp_data[3:0]<=op;resp_data[15:8]<=status;resp_data[16]<=ctx;
   resp_data[63:32]<=session;resp_data[95:64]<=dc_next_lease;
   resp_data[111:96]<=dc_job_generation;resp_data[143:112]<=dc_next_epoch;
   resp_data[145:144]<=dc_loaded;resp_data[147:146]<=dc_idle;
   resp_data[149:148]<=busy;resp_data[151:150]<=canonical_ready;
   resp_data[152]<=fatal_now || status==8'd2;
   resp_data[191:160]<=32'(dc_applied);resp_data[223:192]<=accepted;
   resp_data[511:256]<=data;state<=RESPOND;
  end
 endtask
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   state<=IDLE;held<=0;resp_data<=0;sticky_error<=0;accepted<=0;wait_count<=0;cache_valid<=0;
   for(int c=0;c<2;c++)begin cache_owner[c]<=0;cache_lease[c]<=0;cache_session[c]<=0;end
  end else begin
   if(core_error || dc_error)sticky_error<=1;
   if(!link_ready)begin state<=IDLE;cache_valid<=0;accepted<=0;end
   else case(state)
    IDLE:if(cmd_valid && cmd_ready)begin held<=cmd_data;state<=EXECUTE;wait_count<=0;end
    EXECUTE:begin
     if(!reserved_good || op==ABORT_LINK)begin sticky_error<=1;respond(8'd2,256'b0);end
     else if(op==SNAPSHOT)respond(fatal_now ? 8'd2:8'd0,256'b0);
     else if(fatal_now || !current_token)begin
      sticky_error<=1;
      if(op==DATA)state<=IDLE;else respond(8'd2,256'b0);
     end else case(op)
      DATA:begin
       if(index>=32'(N+32))begin sticky_error<=1;state<=IDLE;end
       else if(dc_word_ready)begin accepted<=accepted+32'd1;state<=IDLE;end
      end
      BEGIN_LOAD:begin cache_valid[ctx]<=0;state<=WAIT_BEGIN;end
      COMMIT_LOAD:if(!cmd_empty)begin sticky_error<=1;respond(8'd2,256'b0);end else state<=WAIT_COMMIT;
      CANCEL_LOAD:begin cache_valid[ctx]<=0;state<=WAIT_CANCEL;end
      START_JOB:if(!start_good)begin sticky_error<=1;respond(8'd2,256'b0);end else state<=WAIT_START;
      READ_A:begin
       if(!read_good)begin sticky_error<=1;respond(8'd2,256'b0);end
       else if(dc_active || !dc_idle[ctx] || !canonical_ready[ctx])respond(8'd1,256'b0);
       else state<=WAIT_READ;
      end
      DESCRIPTOR:begin
       if(generation[31:8]!=0 || word_value[31:1]!=0)begin sticky_error<=1;respond(8'd2,256'b0);end
       else if(!busy[ctx])respond(8'd1,256'b0);
       else if(command_ready)begin
        if(command_accept)respond(8'd0,256'b0);
        else begin sticky_error<=1;respond(8'd2,256'b0);end
       end else state<=WAIT_DESCRIPTOR;
      end
      default:begin sticky_error<=1;respond(8'd2,256'b0);end
     endcase
    end
    WAIT_BEGIN:begin
     if(fatal_now)respond(8'd2,256'b0);
     else if(dc_active)begin
      cache_owner[ctx]<=owner;cache_lease[ctx]<=token_lease;cache_session[ctx]<=session;
      accepted<=0;respond(8'd0,256'b0);resp_data[223:192]<=0;
     end else begin sticky_error<=1;respond(8'd2,256'b0);end
    end
    WAIT_COMMIT:begin
     if(fatal_now)respond(8'd2,256'b0);
     else if(dc_loaded[ctx])begin cache_valid[ctx]<=1;respond(8'd0,256'b0);end
     else if(wait_count==7'd8)begin sticky_error<=1;respond(8'd2,256'b0);end
     else wait_count<=wait_count+7'd1;
    end
    WAIT_CANCEL:begin
     if(fatal_now)respond(8'd2,256'b0);
     else if(!dc_active && !dc_loaded[ctx])respond(8'd0,256'b0);
     else begin sticky_error<=1;respond(8'd2,256'b0);end
    end
    WAIT_START:begin
     if(fatal_now)respond(8'd2,256'b0);
     else if((busy & start_mask)==start_mask)respond(8'd0,256'b0);
     else begin sticky_error<=1;respond(8'd2,256'b0);end
    end
    WAIT_DESCRIPTOR:begin
     if(fatal_now)respond(8'd2,256'b0);
     else if(!busy[ctx])respond(8'd1,256'b0);
     else if(command_ready)begin
      if(command_accept)respond(8'd0,256'b0);
      else begin sticky_error<=1;respond(8'd2,256'b0);end
     end
    end
    WAIT_READ:begin
     if(fatal_now)respond(8'd2,256'b0);
     else if(read_valid)begin
      if(read_context!=ctx || read_owner!=owner)begin sticky_error<=1;respond(8'd2,256'b0);end
      else respond(8'd0,{read_data,index,8'b0,read_owner[55:32],read_owner[31:0],session,(32'h52314100|32'(ctx))});
     end else if(wait_count==7'd63)begin sticky_error<=1;respond(8'd2,256'b0);end
     else wait_count<=wait_count+7'd1;
    end
    RESPOND:if(resp_valid && resp_ready)state<=IDLE;
    default:begin sticky_error<=1;state<=IDLE;end
   endcase
  end
 end
 // synthesis translate_off
 initial if(P!=16 || AW<5 || AW>16)$fatal(1,"R15_CORE_TRANSPORT_GEOMETRY");
 // synthesis translate_on
endmodule
