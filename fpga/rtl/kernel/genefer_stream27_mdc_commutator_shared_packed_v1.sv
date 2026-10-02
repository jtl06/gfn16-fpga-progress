// Incremental P1/P2 candidate: two wide lockstep delay words, not per-lane
// memories. Controller, fault authority, raw tails and output edges are exact.
module genefer_stream27_mdc_commutator_shared_packed_v1 #(
 parameter int unsigned PAIRS=8, DATA_W=28, PAYLOAD_W=1, GEN_W=8,
 parameter int unsigned DEPTH=4, FRAME_T=8, CONTEXTS=1
) (
 input logic clk,rst_n,in_slot_valid,frame_start,
 input logic [PAIRS*DATA_W-1:0] upper_in,lower_in,
 input logic [PAIRS*PAYLOAD_W-1:0] upper_payload,lower_payload,
 input logic context_in,
 input logic [GEN_W-1:0] generation_in,
 input logic [CONTEXTS-1:0] context_enabled,
 input logic [CONTEXTS*GEN_W-1:0] live_generations,
 input logic quarantine,
 output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,
 output logic [PAIRS*DATA_W-1:0] upper_out,lower_out,
 output logic [PAIRS*PAYLOAD_W-1:0] upper_payload_out,lower_payload_out,
 output logic context_out,
 output logic [GEN_W-1:0] generation_out
);
 localparam int unsigned COUNT_W=$clog2(FRAME_T+1),SHIFT=$clog2(DEPTH);
 localparam int unsigned VALUE_W=DATA_W+PAYLOAD_W;
 typedef struct packed {logic valid;logic owner;logic [GEN_W-1:0] generation;} tag_t;
 localparam int unsigned TAG_W=$bits(tag_t);
 logic [COUNT_W-1:0] remaining,offset,output_offset;
 logic frame_owner,output_owner;
 logic [GEN_W-1:0] frame_generation,output_generation,expected_generation;
 logic malformed,phase,advance,owner_bad,eligible;
 tag_t input_tag,head_upper_tag,head_lower_tag,write_upper_tag,result_lower_tag;

 always_comb begin
  malformed=(frame_start && ((remaining!='0)||!in_slot_valid)) ||
   (in_slot_valid && !frame_start && remaining=='0) ||
   (!in_slot_valid && remaining!='0) ||
   (in_slot_valid && CONTEXTS==1 && context_in) ||
   (in_slot_valid && !frame_start && remaining!='0 &&
    ((context_in!=frame_owner)||(generation_in!=frame_generation)));
  phase=in_slot_valid && !frame_start && offset[SHIFT];
  input_tag.valid=in_slot_valid;input_tag.owner=context_in;input_tag.generation=generation_in;
  write_upper_tag=phase?head_lower_tag:input_tag;
  result_lower_tag=phase?input_tag:head_lower_tag;
  owner_bad=(head_upper_tag.valid!=result_lower_tag.valid) ||
   (head_upper_tag.valid && ((head_upper_tag.owner!=result_lower_tag.owner) ||
    (head_upper_tag.generation!=result_lower_tag.generation))) ||
   (head_upper_tag.valid && output_offset!='0 &&
    ((head_upper_tag.owner!=output_owner)||(head_upper_tag.generation!=output_generation)));
  expected_generation=live_generations[GEN_W-1:0];
  if(CONTEXTS==2)expected_generation=head_upper_tag.owner?
    GEN_W'(live_generations>>GEN_W):live_generations[GEN_W-1:0];
  eligible=head_upper_tag.valid && !owner_bad && head_upper_tag.generation==expected_generation &&
   (head_upper_tag.owner?((CONTEXTS==2)&&context_enabled[CONTEXTS-1]):context_enabled[0]);
  fault_pending=out_error || (!quarantine && (malformed||owner_bad));
  // Preserve registered fault transport: detection does not inhibit this edge.
  advance=rst_n && !quarantine && !out_error;
 end
 localparam int unsigned PACKED_W=PAIRS*VALUE_W+TAG_W;
 wire [PAIRS*VALUE_W-1:0] input_upper_values,input_lower_values;
 wire [PACKED_W-1:0] head_upper_word,head_lower_word;
 wire [PACKED_W-1:0] input_upper_word={input_tag,input_upper_values};
 wire [PACKED_W-1:0] input_lower_word={input_tag,input_lower_values};
 wire [PACKED_W-1:0] write_upper_word=phase?head_lower_word:input_upper_word;
 wire [PACKED_W-1:0] result_lower_word=phase?input_upper_word:head_lower_word;
 assign head_upper_tag=head_upper_word[PAIRS*VALUE_W+:TAG_W];
 assign head_lower_tag=head_lower_word[PAIRS*VALUE_W+:TAG_W];
 genefer_stream27_delay_mlab_v1 #(.WORD_W(PACKED_W),.DEPTH(DEPTH)) upper_packed
  (.clk,.rst_n,.advance,.write_word(write_upper_word),.head(head_upper_word));
 genefer_stream27_delay_mlab_v1 #(.WORD_W(PACKED_W),.DEPTH(DEPTH)) lower_packed
  (.clk,.rst_n,.advance,.write_word(input_lower_word),.head(head_lower_word));

 for(genvar lane=0;lane<PAIRS;lane=lane+1)begin: lanes
  assign input_upper_values[lane*VALUE_W+:VALUE_W]=
   {upper_in[lane*DATA_W+:DATA_W],upper_payload[lane*PAYLOAD_W+:PAYLOAD_W]};
  assign input_lower_values[lane*VALUE_W+:VALUE_W]=
   {lower_in[lane*DATA_W+:DATA_W],lower_payload[lane*PAYLOAD_W+:PAYLOAD_W]};
  wire [VALUE_W-1:0] head_upper=head_upper_word[lane*VALUE_W+:VALUE_W];
  wire [VALUE_W-1:0] result_lower=result_lower_word[lane*VALUE_W+:VALUE_W];
  // Like the parent, raw occupied canceled rows update data; reset/idle holds.
  always_ff @(posedge clk)if(advance && head_upper_tag.valid)begin
   upper_out[lane*DATA_W+:DATA_W]<=head_upper[PAYLOAD_W+:DATA_W];
   lower_out[lane*DATA_W+:DATA_W]<=result_lower[PAYLOAD_W+:DATA_W];
   upper_payload_out[lane*PAYLOAD_W+:PAYLOAD_W]<=head_upper[0+:PAYLOAD_W];
   lower_payload_out[lane*PAYLOAD_W+:PAYLOAD_W]<=result_lower[0+:PAYLOAD_W];
  end
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   out_slot_valid<=0;out_frame_start<=0;out_eligible<=0;out_error<=0;
   remaining<='0;offset<='0;output_offset<='0;
  end else begin
   out_slot_valid<=0;out_frame_start<=0;out_eligible<=0;
   if(!quarantine && (malformed||owner_bad))out_error<=1;
   if(advance)begin
    if(in_slot_valid)begin
     if(frame_start)begin
      remaining<=COUNT_W'(FRAME_T-1);offset<=COUNT_W'(1);
      frame_owner<=context_in;frame_generation<=generation_in;
     end else begin remaining<=remaining-COUNT_W'(1);offset<=offset+COUNT_W'(1);end
    end
    if(head_upper_tag.valid)begin
     out_slot_valid<=1;out_frame_start<=output_offset=='0;out_eligible<=eligible;
     output_offset<=output_offset==COUNT_W'(FRAME_T-1)?'0:output_offset+COUNT_W'(1);
     if(output_offset=='0)begin output_owner<=head_upper_tag.owner;output_generation<=head_upper_tag.generation;end
     context_out<=head_upper_tag.owner;generation_out<=head_upper_tag.generation;
    end
   end
  end
 end
 // synthesis translate_off
 initial if(PAIRS<1 || DEPTH<1 || (DEPTH&(DEPTH-1))!=0 || FRAME_T<2*DEPTH ||
  FRAME_T%(2*DEPTH)!=0 || DATA_W<1 || PAYLOAD_W<1 || GEN_W<1 ||
  (CONTEXTS!=1 && CONTEXTS!=2))$fatal(1,"SHARED_COMM_PARAMETERS");
 // synthesis translate_on
endmodule
