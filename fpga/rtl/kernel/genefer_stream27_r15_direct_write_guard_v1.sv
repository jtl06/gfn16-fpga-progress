// Private R15 core-clock endpoint. NO image RAM and NO PCIe/CDC implementation.
// bank_grant is produced by the actual physical port arbiter, never ctx-idle.
// Input is after a reset-fenced CDC FIFO. A successful word consumes the actual
// destination RAM write port on this same edge. External queues must drain
// before commit; reset/cancel must invalidate both domains before token reuse.
module genefer_stream27_r15_direct_write_guard_v1 #(
 parameter int AW=8
) (
 input logic clk,rst_n,link_drained,cancel,
 input logic begin_valid,begin_context,
 input logic [55:0] begin_owner,expected_owner,
 input logic [31:0] begin_session,begin_lease,
 input logic [255:0] begin_profile,
 input logic core_idle,lease_safe,profile_ok,
 input logic word_valid,word_context,
 input logic [55:0] word_owner,
 input logic [31:0] word_session,word_lease,
 input logic [AW+1:0] word_index,
 input logic [31:0] word_data,
 input logic bank_grant,peer_port_busy,
 output logic word_ready,bank_write,
 output logic [AW+1:0] bank_index,
 output logic [31:0] bank_data,
 output logic bank_context,
 output logic [55:0] bank_owner,
 input logic commit_valid,transport_empty,
 input logic [31:0] commit_session,commit_lease,
 input logic [55:0] commit_owner,
 input logic commit_context,
 output logic active,error,publish,
 output logic published_context,
 output logic [55:0] published_owner,
 output logic [255:0] published_profile,
 output logic [AW+2:0] applied_count
);
 localparam int N=1<<AW,WORDS=N+32,K=2*N+384;
 logic held_context;
 logic [55:0] held_owner;
 logic [31:0] held_session,held_lease;
 logic [255:0] held_profile;
 logic [32:0] magnitude;
 logic numeric_good;
 logic word_good,begin_good,commit_good,exclusive_command;
 always_comb begin
  magnitude=word_data[31] ? ({1'b0,~word_data}+33'd1) : {1'b0,word_data};
  if(int'(word_index)<N)
   numeric_good=word_data==32'hffffffff || (!word_data[31] && word_data<held_profile[31:0]);
  else if(int'(word_index)<N+16)
   numeric_good=magnitude<={1'b0,held_profile[31:0]}-33'd1;
  else numeric_good=magnitude<=33'(K);
  exclusive_command=!(begin_valid && (word_valid || commit_valid)) &&
                    !(word_valid && commit_valid);
  begin_good=!active && core_idle && lease_safe && profile_ok &&
             begin_owner==expected_owner && begin_profile[63:40]==0 &&
             begin_profile[39:32]==begin_owner[7:0];
  word_good=active && held_owner==expected_owner && word_context==held_context && word_owner==held_owner &&
            word_session==held_session && word_lease==held_lease &&
            int'(word_index)<WORDS && (AW+3)'(word_index)==applied_count && numeric_good;
  commit_good=active && held_owner==expected_owner && commit_context==held_context && commit_owner==held_owner &&
              commit_session==held_session && commit_lease==held_lease &&
              applied_count==(AW+3)'(WORDS) && transport_empty && core_idle && profile_ok;
  // Invalid words are consumed as typed faults, never held forever by MMIO.
  // Valid words remain held unchanged until the physical port is available.
  word_ready=rst_n && link_drained && !cancel && !error && exclusive_command &&
             (!word_good || !core_idle || (bank_grant && !peer_port_busy));
  bank_write=word_valid && word_ready && word_good && core_idle;
  bank_index=word_index;bank_data=word_data;
  bank_context=held_context;bank_owner=held_owner;
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   active<=0;error<=0;publish<=0;applied_count<=0;
   held_context<=0;held_owner<=0;held_session<=0;held_lease<=0;held_profile<=0;
   published_context<=0;published_owner<=0;published_profile<=0;
  end else begin
   publish<=0;
   if(cancel || !link_drained)begin active<=0;applied_count<=0;end
   else if(!error)begin
    if(!exclusive_command)begin error<=1;active<=0;end
    else if(active && (!core_idle || held_owner!=expected_owner))begin error<=1;active<=0;end
    else if(begin_valid)begin
     if(!begin_good)begin error<=1;active<=0;end
     else begin
      active<=1;applied_count<=0;held_context<=begin_context;
      held_owner<=begin_owner;held_session<=begin_session;held_lease<=begin_lease;
      held_profile<=begin_profile;
     end
    end else if(word_valid && word_ready)begin
     if(!word_good)begin error<=1;active<=0;end
     else applied_count<=applied_count+(AW+3)'(1);
    end else if(commit_valid)begin
     if(!commit_good)begin error<=1;active<=0;end
     else begin
      active<=0;publish<=1;published_context<=held_context;
      published_owner<=held_owner;published_profile<=held_profile;
     end
    end
   end
  end
 end
endmodule
