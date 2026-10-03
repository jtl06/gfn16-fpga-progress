// AUTHOR native fixture: core-clock endpoint and actual shadow RAM, not PCIe/CDC.
// The 32 correction words are fixture-owned small registers, not image staging.
module stream27_r15_direct_write_guard #(parameter int AW=5)(
 input logic clk,rst_n,link_drained,cancel,begin_valid,begin_context,
 input logic [55:0] begin_owner,expected_owner,
 input logic [31:0] session,lease,base,
 input logic core_idle,lease_safe,profile_ok,
 input logic word_valid,word_context,
 input logic [55:0] word_owner,
 input logic [31:0] word_session,word_lease,word_data,
 input logic [AW+1:0] word_index,
 input logic grant_enable,peer_port_busy,
 input logic commit_valid,transport_empty,commit_context,
 input logic [55:0] commit_owner,
 input logic [31:0] commit_session,commit_lease,
 input logic test_read,test_context,
 input logic [AW-1:0] test_address,
 input logic row_write_req,row_write_context,row_read_req,row_read_context,
 input logic [AW-5:0] row_address,
 input logic [511:0] row_data,
 input logic [55:0] row_owner,
 input logic [111:0] live_owner,
 input logic [1:0] owner_enabled,
 output logic word_ready,bank_write,active,error,publish,published_context,
 output logic [55:0] published_owner,
 output logic [255:0] published_profile,
 output logic [AW+2:0] applied_count,ack_count,
 output logic read_valid,read_context,host_write_ready,host_write_ack,row_write_ack,row_read_valid,rejected,
 output logic [95:0] read_data,
 output logic [55:0] read_owner,
 output logic [31:0] correction_read
);
 localparam int N=1<<AW;
 logic [255:0] profile;
 assign profile={192'b0,24'b0,begin_owner[7:0],base};
 logic [AW+1:0] bank_index;
 logic [31:0] bank_data;
 logic bank_context;
 logic [55:0] bank_owner;
 logic [31:0] correction[0:1][0:31];
 logic correction_ack;
 wire body=int'(word_index)<N;
 wire grant=grant_enable && (!body || host_write_ready);
 wire all_acked=ack_count==(AW+3)'(N+32);
 genefer_stream27_r15_direct_write_guard_v1 #(.AW(AW)) guard(
  .clk,.rst_n,.link_drained,.cancel,.begin_valid,.begin_context,.begin_owner,.expected_owner,
  .begin_session(session),.begin_lease(lease),.begin_profile(profile),.core_idle,.lease_safe,.profile_ok,
  .word_valid,.word_context,.word_owner,.word_session,.word_lease,.word_index,.word_data,
  .bank_grant(grant),.peer_port_busy,.word_ready,.bank_write,.bank_index,.bank_data,.bank_context,.bank_owner,
  .commit_valid,.transport_empty(transport_empty && all_acked),.commit_session,.commit_lease,.commit_owner,
  .commit_context,.active,.error,.publish,.published_context,.published_owner,.published_profile,.applied_count);
 genefer_stream27_r15_host_image_ack_v1 #(.AW(AW),.P(16)) image(
  .clk,.rst_n,.quarantine(1'b0),.owner_enabled,.live_owner,
  .host_access(test_read || (word_valid && body)),.load_we(bank_write && body),.read_en(test_read),
  .host_context(test_read?test_context:word_context),.host_addr(test_read?test_address:word_index[AW-1:0]),
  .write_data(bank_data),.row_read_req,.row_read_context,.row_read_address(row_address),.row_read_owner(row_owner),
  .commit_we(1'b0),.commit_context(1'b0),.commit_address({AW{1'b0}}),.commit_word(32'b0),.commit_owner(56'b0),
  .row_write_req,.row_write_context,.row_write_address(row_address),.row_write_data(row_data),.row_write_owner(row_owner),
  .read_valid,.read_context,.read_data,.read_owner,.row_read_valid,.row_response_context(),.row_read_data(),
  .row_response_owner(),.commit_ack(),.row_write_ack,.rejected,.host_write_ready,.host_write_ack);
 assign correction_read=correction[test_context][test_address[4:0]];
 always_ff @(posedge clk)begin
  if(rst_n && bank_write && !body)correction[bank_context][5'(bank_index- (AW+2)'(N))]<=bank_data;
 end
 // ACKs are deliberately counted after their registered observation, not used as grants.
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin ack_count<=0;correction_ack<=0;end
  else begin
   correction_ack<=bank_write && !body;
   if(cancel || !link_drained || begin_valid)ack_count<=0;
   else if(host_write_ack || correction_ack)ack_count<=ack_count+(AW+3)'(1);
  end
 end
endmodule
