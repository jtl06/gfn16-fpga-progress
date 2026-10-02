// P1/P2 field-local vector commutator. Data/payload independent per pair;
// valid/owner/generation and registered fault authority shared by construction.
module genefer_stream27_mdc_commutator_tagcompact_v1 #(
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
 // Full owner dictionaries remain local; only delay transport is compressed.
 typedef struct packed {logic valid;logic color;} compact_tag_t;
 logic [GEN_W:0] owner_dictionary[0:1];
 logic next_color,frame_color;
 compact_tag_t compact_input,compact_upper_write,compact_upper_head,compact_lower_head;
 wire selected_color=frame_start ? next_color : frame_color;
 logic [COUNT_W-1:0] remaining,offset,output_offset;
 logic frame_owner,output_owner;
 logic [GEN_W-1:0] frame_generation,output_generation,expected_generation;
 logic malformed,phase,advance,owner_bad,eligible;
 tag_t input_tag,head_upper_tag,head_lower_tag,write_upper_tag,result_lower_tag;

 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin next_color<=0;frame_color<=0;end
  else if(advance && in_slot_valid && frame_start)begin
   next_color<=!next_color;frame_color<=selected_color;
  end
 end
 // Unreset payload: reset/fill valid bits prevent stale dictionary exposure.
 always_ff @(posedge clk)if(advance && in_slot_valid && frame_start)
  owner_dictionary[selected_color]<={context_in,generation_in};
 always_comb begin
  compact_input.valid=in_slot_valid;compact_input.color=selected_color;
  head_upper_tag.valid=compact_upper_head.valid;
  {head_upper_tag.owner,head_upper_tag.generation}=owner_dictionary[compact_upper_head.color];
  head_lower_tag.valid=compact_lower_head.valid;
  {head_lower_tag.owner,head_lower_tag.generation}=owner_dictionary[compact_lower_head.color];
  malformed=(frame_start && ((remaining!='0)||!in_slot_valid)) ||
   (in_slot_valid && !frame_start && remaining=='0) ||
   (!in_slot_valid && remaining!='0) ||
   (in_slot_valid && CONTEXTS==1 && context_in) ||
   (in_slot_valid && !frame_start && remaining!='0 &&
    ((context_in!=frame_owner)||(generation_in!=frame_generation)));
  phase=in_slot_valid && !frame_start && offset[SHIFT];
  compact_upper_write=phase?compact_lower_head:compact_input;
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
 genefer_stream27_delay_mlab_v1 #(.WORD_W(2),.DEPTH(DEPTH)) upper_tags
  (.clk,.rst_n,.advance,.write_word(compact_upper_write),.head(compact_upper_head));
 genefer_stream27_delay_mlab_v1 #(.WORD_W(2),.DEPTH(DEPTH)) lower_tags
  (.clk,.rst_n,.advance,.write_word(compact_input),.head(compact_lower_head));

 for(genvar lane=0;lane<PAIRS;lane=lane+1)begin: lanes
  wire [VALUE_W-1:0] x={upper_in[lane*DATA_W+:DATA_W],upper_payload[lane*PAYLOAD_W+:PAYLOAD_W]};
  wire [VALUE_W-1:0] y={lower_in[lane*DATA_W+:DATA_W],lower_payload[lane*PAYLOAD_W+:PAYLOAD_W]};
  wire [VALUE_W-1:0] head_upper,head_lower;
  wire [VALUE_W-1:0] write_upper=phase?head_lower:x;
  wire [VALUE_W-1:0] result_lower=phase?x:head_lower;
  genefer_stream27_delay_mlab_v1 #(.WORD_W(VALUE_W),.DEPTH(DEPTH)) upper_values
   (.clk,.rst_n,.advance,.write_word(write_upper),.head(head_upper));
  genefer_stream27_delay_mlab_v1 #(.WORD_W(VALUE_W),.DEPTH(DEPTH)) lower_values
   (.clk,.rst_n,.advance,.write_word(y),.head(head_lower));
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
