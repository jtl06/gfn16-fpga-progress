// Private R14-F cold packet staging on literal FIELD100. Canonical ordinary residues, never trim32.
// Loaded means complete body, NOT setup-qualified. Parent validates the exact
// reciprocal/limit with its retained setup unit before releasing any cold row.
module genefer_stream27_host_offload_ingress_field100_v1 #(
 parameter int AW=8,P=16
) (
 input logic clk,rst_n,quarantine,begin_packet,write_valid,commit_packet,context_in,
 input logic [1:0] context_busy,
 input logic [AW+1:0] word_index,input logic [31:0] word_data,
 input logic [31:0] profile_base,profile_generation,
 input logic [95:0] profile_reciprocal,profile_limit,
 input logic [15:0] profile_epoch,
 output logic [1:0] loaded,output logic error,
 output logic [63:0] saved_base,output logic [15:0] saved_generation,
 output logic [31:0] saved_epoch,output logic [191:0] saved_reciprocal,saved_limit,
 input logic row_request,row_context,
 input logic [55:0] row_owner,input logic [111:0] expected_owners,
 input logic [AW-$clog2(P)-1:0] row_address,
 output logic row_valid,row_response_context,
 output logic [55:0] row_response_owner,
 output logic [3*P*32-1:0] row_data,
 input logic correction_context,
 output logic [3*P*32-1:0] correction_low,correction_high
);
 localparam int N=1<<AW,T=N/P,RW=AW-$clog2(P),WORDS=3*N+6*P;
 localparam int K=2*N+24*P,MIN_A=2*N+5,MIN_B=(2*K+2)/3+1;
 localparam int MIN_BASE=MIN_A>MIN_B ? MIN_A:MIN_B;
 // Explicit independent 1R1W banks; no dynamically indexed outer memory dimensions.
 logic [26:0] lows[0:1][0:2][0:P-1],highs[0:1][0:2][0:P-1];
 logic [AW+2:0] count[0:1];logic [1:0] staging;
 integer field_index,lane_index,row_index;logic numeric_ok;
 logic [31:0] selected_prime;
 wire stop=quarantine || error;
 wire row_owned=loaded[row_context] && row_owner==expected_owners[row_context*56+:56] &&
  row_owner[7:0]==saved_generation[row_context*8+:8];
 always_comb begin
  if(int'(word_index)<3*N)begin
   field_index=int'(word_index)/N;lane_index=int'(word_index)%P;
   row_index=(int'(word_index)%N)/P;
  end else begin
   field_index=((int'(word_index)-3*N)/P)%3;
   lane_index=(int'(word_index)-3*N)%P;row_index=0;
  end
  case(field_index)
   0:selected_prime=32'd104857601;
   1:selected_prime=32'd69206017;
   2:selected_prime=32'd67239937;
   default:selected_prime=0;
  endcase
  numeric_ok=word_data<selected_prime;
 end
 for(genvar f=0;f<3;f++)for(genvar lane=0;lane<P;lane++)begin: correction_wire
  assign correction_low[(f*P+lane)*32+:32]={5'd0,lows[correction_context][f][lane]};
  assign correction_high[(f*P+lane)*32+:32]={5'd0,highs[correction_context][f][lane]};
 end
 wire import_write=rst_n && !stop && write_valid && !begin_packet && !commit_packet &&
  !context_busy[context_in] && staging[context_in] &&
  count[context_in]==(AW+3)'(word_index) && int'(word_index)<WORDS && numeric_ok;
 // Each field/lane bank has one addressed write and one synchronous read.
 // Context is an address bit, not a variable outer-array selector.
 for(genvar f=0;f<3;f++)begin: field_bank
  for(genvar lane=0;lane<P;lane++)begin: lane_bank
   (* ramstyle="M20K" *) logic [26:0] image[0:2*T-1];
   logic [26:0] read_q;
   always_ff @(posedge clk)begin
    if(import_write && int'(word_index)<3*N && field_index==f && lane_index==lane)
     image[{context_in,RW'(row_index)}]<=word_data[26:0];
    if(rst_n && row_request && !stop && row_owned)
     read_q<=image[{row_context,row_address}];
   end
   assign row_data[(f*P+lane)*32+:32]={5'd0,read_q};
  end
 end
 always_ff @(posedge clk)begin
  if(import_write)begin
   if(int'(word_index)>=3*N && int'(word_index)<3*N+3*P)
    lows[context_in][field_index][lane_index]<=word_data[26:0];
   else if(int'(word_index)>=3*N+3*P)
    highs[context_in][field_index][lane_index]<=word_data[26:0];
  end
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   loaded<=0;staging<=0;error<=0;row_valid<=0;row_response_context<=0;row_response_owner<=0;
   count[0]<=0;count[1]<=0;saved_base<=0;saved_generation<=0;saved_epoch<=0;
   saved_reciprocal<=0;saved_limit<=0;
  end else begin
   row_valid<=row_request && !stop && row_owned;
   if(row_request)begin row_response_context<=row_context;row_response_owner<=row_owner;end
   if(!stop)begin
    if(row_request && !row_owned)error<=1;
    if((begin_packet && (write_valid || commit_packet)) || (write_valid && commit_packet) ||
       ((begin_packet || write_valid || commit_packet) && context_busy[context_in]))error<=1;
    else if(begin_packet)begin
     loaded[context_in]<=0;staging[context_in]<=0;count[context_in]<=0;
     if(profile_base<32'(MIN_BASE) || profile_base>32'd1000000000 ||
        profile_generation[31:8]!=0 || profile_reciprocal==0 || profile_limit==0 ||
        profile_limit[95:77]!=0)error<=1;
     else begin
      staging[context_in]<=1;saved_base[context_in*32+:32]<=profile_base;
      saved_generation[context_in*8+:8]<=profile_generation[7:0];
      saved_epoch[context_in*16+:16]<=profile_epoch;
      saved_reciprocal[context_in*96+:96]<=profile_reciprocal;
      saved_limit[context_in*96+:96]<=profile_limit;
     end
    end else if(write_valid)begin
     if(!staging[context_in] || count[context_in]!=(AW+3)'(word_index) ||
        int'(word_index)>=WORDS || !numeric_ok)error<=1;
     else count[context_in]<=count[context_in]+(AW+3)'(1);
    end else if(commit_packet)begin
     if(!staging[context_in] || count[context_in]!=(AW+3)'(WORDS))error<=1;
     else begin loaded[context_in]<=1;staging[context_in]<=0;end
    end
   end
  end
 end
endmodule
