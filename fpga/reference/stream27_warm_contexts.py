"""Two-context dependent arithmetic and full-width operation selection.

Actual shared-carry digits and corrections feed the next transform. Each
context has its own count/base/generation/descriptor ordinal. Final raw rows
are tagged for the separate waiting-final/host publication controller; warm
completion is never canonical readiness. Frozen one-context compilers stay
unchanged.
"""
import hashlib
from . import stream27_threefield_contexts as arithmetic

ROOT = arithmetic.ROOT
SELF = 'reference/stream27_warm_contexts.py'


def source(n, p, child, g):
    aw = n.bit_length()-1
    top = f'genefer_stream27_warm_contexts_aw{aw}_p{p}_v1'
    delay = g['feedback_delay']
    if delay not in (0, 4,18):
        raise ValueError('S4_CTX_FEEDBACK_DELAY0_4_18')
    if delay:
        feedback = '''logic [3:0] fifo_valid,fifo_start;
 logic [P*32-1:0] fifo_data[0:3];logic [24:0] fifo_owner[0:3];
 assign feedback_slot=fifo_valid[3] && !local_error;
 assign feedback_start=fifo_start[3];assign feedback_data=fifo_data[3];assign feedback_owner=fifo_owner[3];
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin fifo_valid<=0;fifo_start<=0;end
  else if(local_error)begin fifo_valid<=0;fifo_start<=0;end
  else begin
   fifo_valid<={fifo_valid[2:0],feedback_issue};fifo_start<={fifo_start[2:0],digit_start};
   if(feedback_issue)begin fifo_data[0]<=permuted_digit;fifo_owner[0]<={digit_context,digit_epoch+16'd1,digit_generation};end
   for(int d=1;d<4;d=d+1)if(fifo_valid[d-1])begin fifo_data[d]<=fifo_data[d-1];fifo_owner[d]<=fifo_owner[d-1];end
  end
 end
'''
        if delay!=4:
            feedback=feedback.replace('[3:0]',f'[{delay-1}:0]').replace('[0:3]',f'[0:{delay-1}]')
            feedback=feedback.replace('[3]',f'[{delay-1}]').replace('[2:0]',f'[{delay-2}:0]')
            feedback=feedback.replace('d<4;',f'd<{delay};')
    else:
        feedback = '''assign feedback_slot=feedback_issue;
 assign feedback_start=digit_start;assign feedback_data=permuted_digit;
 assign feedback_owner={digit_context,digit_epoch+16'd1,digit_generation};
'''
    return top, f'''// Arithmetic chain only. Host done/publication is a separate controller.
module {top} #(parameter int AW={aw},P={p},CONTEXTS=2) (
 input logic clk,rst_n,begin_setup,setup_context,in_slot_valid,frame_start,context_in,correction_context,double_in,
 input logic [1:0] context_enabled,input logic [15:0] live_generation,
 input logic [7:0] generation_in,correction_generation,input logic [31:0] base_in,
 input logic [15:0] epoch_in,correction_epoch,input logic correction_valid,
 input logic [P*32-1:0] data_in,c0_in,c1_in,
 input logic [31:0] square_count,double_mask,input logic feed_mode,
 input logic [1:0] command_valid,command_double,
 input logic [63:0] command_index,input logic [15:0] command_generation,
 output logic [1:0] command_accept,active,warm_done,warm_cancelled,
 output logic [63:0] completed_frames,started_frames,
 output logic [1:0] config_valid,output logic setup_done,setup_done_context,
 output logic out_error,fault_pending,frame_accept,correction_accept,
 output logic internal_frame_accept,internal_correction_accept,
 output logic coefficient_valid,coefficient_start,coefficient_context,
 output logic signed [P*96-1:0] coefficient_data,output logic [AW-$clog2(P)-1:0] coefficient_row,
 output logic digit_valid,digit_start,digit_eligible,digit_context,
 output logic [P*32-1:0] digit_data,output logic [AW-$clog2(P)-1:0] digit_row,
 output logic [15:0] digit_epoch,output logic [7:0] digit_generation,
 output logic [31:0] digit_sequence,boundary_sequence,
 output logic boundary_valid,boundary_eligible,boundary_context,
 output logic [P*32-1:0] next_c0,next_c1,output logic [15:0] next_epoch,output logic [7:0] next_generation,
 output logic frame_done,done_context,output logic [15:0] done_epoch,
 output logic final_load_valid,final_load_context,final_boundary_valid,
 output logic [55:0] final_load_owner);
 localparam int ROW_W=AW-$clog2(P),ROWS=1<<ROW_W;
 logic local_error;logic [1:0] initial_correction_seen,feedback_enabled,cancel_seen,latched_feed;
 logic [ROW_W:0] cold_remaining[0:1];
 logic [31:0] remaining[0:1],launched[0:1],completed[0:1],latched_count[0:1],latched_mask[0:1],result_sequence[0:1];
 logic [31:0] chain_base[0:1];logic [7:0] chain_generation[0:1];logic [1:0] current_double;
 wire cold_slot=in_slot_valid && (!active[context_in] || cold_remaining[context_in]!=0) && !local_error;
 wire cold_correction=correction_valid && !local_error;
 wire need_feedback=digit_start ? remaining[digit_context]!=0 : feedback_enabled[digit_context];
 wire feedback_issue=digit_valid && need_feedback && !local_error;
 wire auto_correction=boundary_valid && feedback_enabled[boundary_context] && !local_error;
 wire feedback_slot,feedback_start;wire [P*32-1:0] feedback_data,permuted_digit;wire [24:0] feedback_owner;
{feedback}
 function automatic integer reverse_lane(input integer value);
  integer result;
  begin result=0;for(integer bit_index=0;bit_index<$clog2(P);bit_index=bit_index+1)begin
   result=(result<<1)|(value&1);value=value>>1;
  end reverse_lane=result;end
 endfunction
 for(genvar lane=0;lane<P;lane=lane+1)begin: input_route
  localparam int NATURAL=reverse_lane(lane);
  assign permuted_digit[32*lane+:32]=digit_data[32*NATURAL+:32];
 end
 wire feedback_context=feedback_owner[24];
 wire command_needed=feedback_slot && feedback_start && latched_feed[feedback_context] && !local_error;
 wire command_bad=command_needed && (!command_valid[feedback_context] ||
  command_index[feedback_context*32+:32]!=launched[feedback_context] ||
  command_generation[feedback_context*8+:8]!=chain_generation[feedback_context]);
 wire collision=(cold_slot && feedback_slot) || (cold_correction && auto_correction);
 wire count_bad=cold_slot && frame_start && (square_count==0 || (!feed_mode && square_count>32'd32));
 wire cold_request_bad=in_slot_valid && active[context_in] && cold_remaining[context_in]==0;
 wire child_error,child_pending,child_frame_accept,child_correction_accept;
 wire arithmetic_digit_valid,arithmetic_digit_start,arithmetic_digit_eligible;
 wire arithmetic_boundary_valid,arithmetic_boundary_eligible,arithmetic_frame_done;
 wire child_slot=(cold_slot || feedback_slot) && !command_bad;
 wire child_start=(feedback_slot ? feedback_start : frame_start) && !command_bad;
 wire child_context=feedback_slot ? feedback_context : context_in;
 wire selected_double=feedback_start ? (latched_feed[feedback_context] ? command_double[feedback_context] :
  latched_mask[feedback_context][launched[feedback_context][4:0]]) : current_double[feedback_context];
 assign out_error=local_error || child_error;
 assign digit_valid=arithmetic_digit_valid && !local_error;assign digit_start=arithmetic_digit_start && digit_valid;
 assign digit_eligible=arithmetic_digit_eligible && !local_error;
 assign boundary_valid=arithmetic_boundary_valid && !local_error;assign boundary_eligible=arithmetic_boundary_eligible && !local_error;
 assign frame_done=arithmetic_frame_done && !local_error;
 assign frame_accept=cold_slot && frame_start && child_frame_accept;
 assign correction_accept=cold_correction && child_correction_accept;
 assign internal_frame_accept=feedback_slot && feedback_start && child_frame_accept;
 assign internal_correction_accept=auto_correction && child_correction_accept;
 assign command_accept[0]=internal_frame_accept && latched_feed[0] && !feedback_context && !command_bad;
 assign command_accept[1]=internal_frame_accept && latched_feed[1] && feedback_context && !command_bad;
 assign completed_frames={{completed[1],completed[0]}};assign started_frames={{launched[1],launched[0]}};
 assign digit_sequence=digit_start ? completed[digit_context] : result_sequence[digit_context];
 assign boundary_sequence=result_sequence[boundary_context];
 assign final_load_valid=digit_eligible && active[digit_context] && digit_sequence==latched_count[digit_context]-32'd1;
 assign final_load_context=digit_context;assign final_load_owner={{digit_sequence,digit_epoch,digit_generation}};
 assign final_boundary_valid=boundary_eligible && active[boundary_context] && boundary_sequence==latched_count[boundary_context]-32'd1;
 assign fault_pending=out_error || child_pending || collision || count_bad || command_bad || cold_request_bad;
 {child} #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) arithmetic (
  .clk,.rst_n,.begin_setup,.setup_context,.in_slot_valid(child_slot && !local_error),.frame_start(child_start),
  .context_in(child_context),.correction_context(auto_correction ? boundary_context : correction_context),.context_enabled,
  .double_in(feedback_slot ? selected_double : double_in),
  .generation_in(feedback_slot ? feedback_owner[7:0] : generation_in),.live_generation,
  .base_in(feedback_slot ? chain_base[feedback_context] : base_in),
  .epoch_in(feedback_slot ? feedback_owner[23:8] : epoch_in),
  .correction_epoch(auto_correction ? next_epoch : correction_epoch),
  .correction_generation(auto_correction ? next_generation : correction_generation),
  .correction_valid((cold_correction || auto_correction) && !local_error),
  .data_in(feedback_slot ? feedback_data : data_in),.c0_in(auto_correction ? next_c0 : c0_in),.c1_in(auto_correction ? next_c1 : c1_in),
  .config_valid,.setup_done,.setup_done_context,.out_error(child_error),.fault_pending(child_pending),
  .frame_accept(child_frame_accept),.correction_accept(child_correction_accept),
  .coefficient_valid,.coefficient_start,.coefficient_context,.coefficient_data,.coefficient_row,
  .digit_valid(arithmetic_digit_valid),.digit_start(arithmetic_digit_start),.digit_eligible(arithmetic_digit_eligible),.digit_context,
  .digit_data,.digit_row,.digit_epoch,.digit_generation,
  .boundary_valid(arithmetic_boundary_valid),.boundary_eligible(arithmetic_boundary_eligible),.boundary_context,
  .next_c0,.next_c1,.next_epoch,.next_generation,.frame_done(arithmetic_frame_done),.done_context,.done_epoch);
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   local_error<=0;active<=0;warm_done<=0;warm_cancelled<=0;initial_correction_seen<=0;
   feedback_enabled<=0;cancel_seen<=0;latched_feed<=0;current_double<=0;
   for(int ctx=0;ctx<2;ctx=ctx+1)begin
    cold_remaining[ctx]<=0;remaining[ctx]<=0;launched[ctx]<=0;completed[ctx]<=0;
    latched_count[ctx]<=0;latched_mask[ctx]<=0;result_sequence[ctx]<=0;chain_base[ctx]<=0;chain_generation[ctx]<=0;
   end
  end else begin
   warm_done<=0;
   if(child_error || collision || count_bad || command_bad || cold_request_bad)local_error<=1;
   for(int ctx=0;ctx<2;ctx=ctx+1)if(active[ctx] &&
    (!context_enabled[ctx] || chain_generation[ctx]!=live_generation[ctx*8+:8]))cancel_seen[ctx]<=1;
   if(frame_accept)begin
    active[context_in]<=1;remaining[context_in]<=square_count-32'd1;launched[context_in]<=1;completed[context_in]<=0;
    latched_count[context_in]<=square_count;latched_mask[context_in]<=double_mask;latched_feed[context_in]<=feed_mode;
    cold_remaining[context_in]<=(ROW_W+1)'(ROWS-1);chain_base[context_in]<=base_in;chain_generation[context_in]<=generation_in;
    warm_cancelled[context_in]<=0;cancel_seen[context_in]<=0;initial_correction_seen[context_in]<=0;result_sequence[context_in]<=0;
   end else if(cold_slot && cold_remaining[context_in]!=0)cold_remaining[context_in]<=cold_remaining[context_in]-(ROW_W+1)'(1);
   if(correction_accept)initial_correction_seen[correction_context]<=1;
   if(digit_valid && digit_start)begin
    feedback_enabled[digit_context]<=remaining[digit_context]!=0;result_sequence[digit_context]<=completed[digit_context];
   end
   if(internal_frame_accept)begin
    remaining[feedback_context]<=remaining[feedback_context]-32'd1;launched[feedback_context]<=launched[feedback_context]+32'd1;
    current_double[feedback_context]<=selected_double;
   end
   if(frame_done && active[done_context])begin
    completed[done_context]<=completed[done_context]+32'd1;
    if(completed[done_context]+32'd1==latched_count[done_context])begin
     active[done_context]<=0;warm_done[done_context]<=1;
     warm_cancelled[done_context]<=cancel_seen[done_context] || !context_enabled[done_context] ||
      chain_generation[done_context]!=live_generation[done_context*8+:8];
    end
   end
   if(local_error || child_error)begin active<=0;warm_done<=0;warm_cancelled<=2'b11;end
  end
 end
 // synthesis translate_off
 initial if(AW!={aw} || P!={p} || CONTEXTS!=2)$fatal(1,"S4_CTX_WARM_EXPLICIT_GEOMETRY");
 always @(posedge clk)if(rst_n && !out_error)begin
  if(final_load_valid && digit_sequence!=latched_count[digit_context]-32'd1)$fatal(1,"S4_CTX_FINAL_ORDINAL");
  if(internal_frame_accept && launched[feedback_context]>=latched_count[feedback_context])$fatal(1,"S4_CTX_TOO_MANY_FRAMES");
 end
 // synthesis translate_on
endmodule
'''


def prepare(n=32, p=8, *, contexts=2, allow_full_constants=False,corr_serial_bfs=0,mont_factored=0):
    b = arithmetic.prepare(n, p, contexts=contexts, allow_full_constants=allow_full_constants,
                           corr_serial_bfs=corr_serial_bfs,mont_factored=mont_factored)
    top, text = source(n, p, b['top'], b['geometry'])
    top,text=arithmetic.diet_source(top,text,corr_serial_bfs,mont_factored)
    b['files'][top + '.sv'] = text
    b['top'] = top
    b['source_dependencies'] = list(dict.fromkeys(b['source_dependencies'] + [SELF]))
    b['source_sha256'][SELF] = hashlib.sha256((ROOT / SELF).read_bytes()).hexdigest()
    b['rtl_sources'] = [name for name in b['files'] if name.endswith('.sv')]
    b['generated_sha256'] = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in b['files'].items()}
    b['control_contract'] = dict(count='Per-context 1..UINT32_MAX with feed mode, legacy mask limited32.',
        descriptors='Caller supplies bounded FIFO heads independently per context; exact full32 next ordinal and gen8 at actual feedback FIRST.',
        final='Actual full32 result ordinal plus carried epoch16/gen8/context qualifies raw last rows and late boundaries; host canonical/copy required.',
        cold='Two profile setups then dense cold frames and independently scheduled cold correction tokens; caller obeys shared input/correction port calendar.',
        cancellation='Raw occupied tails remain carried; per-context eligibility revokes publication. Shared arithmetic fault quarantines both until reset.')
    b['scope'] = 'Real on-chip two-context dependent arithmetic source candidate; source only until native. No bounded FIFO host scheduler, canonical/publication/readback/physical qualification yet.'
    return b
