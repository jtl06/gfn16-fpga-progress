"""Explicit shared warm-field source template, frozen components underneath."""
from .stream_ntt_model import FIELDS,bit_reverse


def source(n,p,field,g,small,roots,term):
    aw=n.bit_length()-1;pw=p.bit_length()-1;rw=aw-pw;rows=n//p
    prime,generator=FIELDS[field];q=(2-prime)%(1<<32);psi=pow(generator,(prime-1)//(2*n),prime)
    width=p*27;name=f'genefer_stream27_shared_warm_aw{aw}_p{p}_f{field}_v1'
    minimum=max(2*n+5,(2*(2*n+24*p)+2)//3+1);bound=2*n+24*p
    forward=f'genefer_stream28_merged_ct_aw{aw}_p{p}_f{field}_v1'
    inverse=f'genefer_stream28_merged_gs_aw{aw}_p{p}_f{field}_v1'
    square=f'genefer_stream27_square_p{p}_f{field}_v1'
    # Physical CT spectral frequency is reverse(lane+P*row,AW). With T>=P,
    # frequency modP depends on row high bits. Correction tables use natural k.
    def index(signal):
        return '{'+','.join(f'{signal}[{rw-pw+i}]' for i in range(pw))+'}'
    aidx=index('pw_row');sidx=index('seed_target');nidx=index('term_target')
    # The same physical DIF generator takes bit-reversed contiguous blocks.
    # Its N=P specialization therefore needs correction input lane l <-
    # natural block reverse(l,PW), including that block's twist constant.
    smallpacked=sum(pow(psi,bit_reverse(k,pw)*rows,prime)*(1<<32)%prime<<(27*k) for k in range(p))
    capture='\n'.join(
        f'     if(small_capture)B_table[small_owner[8]][{k}]<=small_data[{27*bit_reverse(k,pw)}+:27];\n'
        f'     else A_table[small_owner[8]][{k}]<=small_data[{27*bit_reverse(k,pw)}+:27];' for k in range(p))
    wiring=[]
    for lane in range(p):
        wiring += [f'  assign input_wide[{28*lane}+:28]={{1\'b0,digit_data[{27*lane}+:27]}};',
            f'  assign ordered_c0[{32*lane}+:32]=c0_in[{32*bit_reverse(lane,pw)}+:32];',
            f'  assign ordered_high[{32*lane}+:32]=high_correction[{32*bit_reverse(lane,pw)}+:32];',
            f'  wire [27:0] raw_spectrum{lane}=fwd_data[{28*lane}+:28];',
            f"  assign canonical_spectrum[{27*lane}+:27]=27'(raw_spectrum{lane}>=28'd{prime} ? raw_spectrum{lane}-28'd{prime} : raw_spectrum{lane});",
            f"  assign square_wide[{28*lane}+:28]={{1'b0,squared[{27*lane}+:27]}};",
            f'  assign data_out[{27*lane}+:27]=inv_data[{28*lane}+:27];',
            f'  assign addA_rhs[{27*lane}+:27]=A_table[protocol_pw_epoch[0]][{aidx}];',
            f'  assign term_seed_coeff[{27*lane}+:27]=B_table[seed_owner[8]][{sidx}];',
            f'  assign term_next_coeff[{27*lane}+:27]=B_table[protocol_pw_epoch[0]][{nidx}];']
    return name,f'''// S4 shared one-field warm composition; source/native/clock gates separate.
// P is explicit and shared with probes. CONTEXTS=2 remains a rejected hook.
module {name} #(parameter int AW={aw},P={p},CONTEXTS=1) (
 input logic clk,rst_n,in_slot_valid,frame_start,context_enabled,
 input logic [7:0] generation_in,live_generation,
 input logic [31:0] base_in,
 input logic [15:0] epoch_in,correction_epoch,
 input logic correction_valid,input logic [7:0] correction_generation,
 input logic [{p*32-1}:0] data_in,c0_in,c1_in,
 output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,
 output logic [7:0] generation_out,output logic [{width-1}:0] data_out,
 output logic [15:0] out_epoch,
 output logic commit_valid,commit_frame_start,
 output logic [7:0] commit_generation,output logic [15:0] commit_epoch,
 output logic [{width-1}:0] commit_data,
 output logic [1:0] owner_count,output logic frame_accept,correction_accept,
 output logic [{rw-1}:0] output_row,
 output logic [31:0] cycle_count,frame_count);
 localparam int ROW_W={rw},ROWS={rows},LANES={p};
 logic controller_error;
 wire stop=controller_error;
 logic [ROW_W:0] input_remaining;
 logic [ROW_W-1:0] input_row;
 logic [7:0] active_generation;
 logic [31:0] active_base,high_base;
 logic [15:0] active_epoch;
 logic [{p*32-1}:0] high_correction;
 wire [{p*32-1}:0] ordered_c0,ordered_high;
 logic c1_pending,small_capture,seed_running;
 logic [1:0] seed_row;
 logic [23:0] high_owner,small_first_owner,seed_owner;
 logic [15:0] table_epoch[0:1];logic [7:0] table_generation[0:1];
 logic [1:0] tables_ready;
 logic [26:0] A_table[0:1][0:LANES-1],B_table[0:1][0:LANES-1];
 logic [8:0] child_error,child_pending;
 logic admission_bad,join_bad;
 wire raw_begin=rst_n && in_slot_valid && frame_start && !stop;
 wire [31:0] digit_base=frame_start ? base_in : active_base;
 wire [7:0] digit_generation=frame_start ? generation_in : active_generation;
 wire [ROW_W-1:0] digit_row=frame_start ? ROW_W'(0) : input_row;
 wire accepted=rst_n && in_slot_valid && !stop && (!frame_start || frame_accept);
 wire accepted_correction=rst_n && correction_valid && correction_accept && !stop;
 wire boundary_slot=(accepted_correction || c1_pending) && !stop;
 wire [31:0] boundary_base=accepted_correction ? protocol_correction_base : high_base;
 wire [23:0] boundary_owner=accepted_correction ? {{correction_epoch,correction_generation}} : high_owner;
 wire [31:0] protocol_correction_base;
 wire protocol_frame_accept,protocol_correction_accept,protocol_commit,protocol_pw_accept;
 wire [15:0] protocol_pw_epoch,protocol_sink_epoch;
 wire [ROW_W-1:0] protocol_pw_row,protocol_sink_row;
 wire protocol_error,protocol_pending;
 assign frame_accept=protocol_frame_accept;assign correction_accept=protocol_correction_accept;
 assign out_error=controller_error;
 assign fault_pending=controller_error || (|child_pending) || protocol_pending || (!stop && (admission_bad || join_bad));
 function automatic logic correction_ok(input logic [31:0] word,input logic [31:0] limit);
  logic signed [32:0] wide_value;logic [32:0] magnitude;
  begin wide_value=$signed({{word[31],word}});magnitude=word[31] ? 33'(-wide_value) : 33'(wide_value);
   correction_ok=magnitude<={{1'b0,limit}};end
 endfunction
 always_comb begin
  admission_bad=(frame_start && (!in_slot_valid || input_remaining!=0)) ||
   (in_slot_valid && !frame_start && input_remaining==0) || (!in_slot_valid && input_remaining!=0) ||
   (in_slot_valid && !frame_start && (generation_in!=active_generation || epoch_in!=active_epoch));
  if(in_slot_valid)begin
   if(digit_base<32'd{minimum} || digit_base>32'd1000000000)admission_bad=1;
   for(int lane=0;lane<LANES;lane=lane+1)if(data_in[lane*32+:32]>=digit_base)admission_bad=1;
  end
  if(correction_valid)begin
   if(c1_pending || seed_running)admission_bad=1;
   for(int lane=0;lane<LANES;lane=lane+1)
    if(!correction_ok(c0_in[lane*32+:32],protocol_correction_base-32'd1) ||
       !correction_ok(c1_in[lane*32+:32],32'd{bound}))admission_bad=1;
  end
 end
 logic [LANES-1:0] digit_valid,digit_error,boundary_valid,boundary_error;
 logic [ROW_W+8:0] digit_tag[0:LANES-1];logic [23:0] boundary_tag[0:LANES-1];
 wire [{width-1}:0] digit_data,boundary_data;
 wire digit_slot=&digit_valid,boundary_out_slot=&boundary_valid;
 assign child_error[0]=|digit_error;assign child_error[1]=|boundary_error;
 always_comb begin
  child_pending[0]=(|digit_error) || ((|digit_valid) && !(&digit_valid));
  child_pending[1]=(|boundary_error) || ((|boundary_valid) && !(&boundary_valid));
  for(int lane=1;lane<LANES;lane=lane+1)begin
   if(digit_slot && digit_tag[lane]!=digit_tag[0])child_pending[0]=1;
   if(boundary_out_slot && boundary_tag[lane]!=boundary_tag[0])child_pending[1]=1;
  end
 end
 for(genvar lane=0;lane<LANES;lane=lane+1)begin: reducers
  wire [31:0] digit_residue,boundary_residue;
  genefer_digit_reduce27_pipe #(.P(32'd{prime}),.PAYLOAD_W(ROW_W+9)) digits (
   .clk,.rst_n,.in_valid(accepted),.digit(data_in[lane*32+:32]),
   .payload_in({{digit_generation,frame_start,digit_row}}),
   .out_valid(digit_valid[lane]),.out_error(digit_error[lane]),.residue(digit_residue),.payload_out(digit_tag[lane]));
  genefer_stream27_signed_boundary_reduce27_pipe #(.P(32'd{prime}),.AW({aw}),.BLOCKS(LANES),.PAYLOAD_W(24)) boundary (
   .clk,.rst_n,.in_valid(boundary_slot),.boundary_high(c1_pending && !accepted_correction),
   .correction(accepted_correction ? ordered_c0[lane*32+:32] : ordered_high[lane*32+:32]),.base(boundary_base),
   .payload_in(boundary_owner),.out_valid(boundary_valid[lane]),.out_error(boundary_error[lane]),
   .residue(boundary_residue),.payload_out(boundary_tag[lane]));
  assign digit_data[lane*27+:27]=digit_residue[26:0];
  assign boundary_data[lane*27+:27]=boundary_residue[26:0];
 end
 wire small_twist_slot,small_twist_start,small_slot,small_start;
 wire [23:0] small_twist_owner,small_owner;
 wire [{width-1}:0] small_twisted,small_data;
 genefer_stream27_mul_param_v1 #(.LANES(LANES),.GEN_W(24),.P(32'd{prime}),.Q(32'd{q})) small_twist (
  .clk,.rst_n,.in_slot_valid(boundary_out_slot),.frame_start(1'b1),.quarantine(stop),
  .generation_in(boundary_tag[0]),.lhs(boundary_data),.rhs({width}'h{smallpacked:0{(width+3)//4}x}),
  .out_slot_valid(small_twist_slot),.out_frame_start(small_twist_start),.out_error(child_error[2]),
  .fault_pending(child_pending[2]),.generation_out(small_twist_owner),.result(small_twisted));
 {small} #(.GEN_W(24)) correction_transform (
  .clk,.rst_n,.in_slot_valid(small_twist_slot),.frame_start(small_twist_start),.quarantine(stop),
  .context_enabled(1'b1),.generation_in(small_twist_owner),.live_generation(small_twist_owner),.data_in(small_twisted),
  .out_slot_valid(small_slot),.out_frame_start(small_start),.out_eligible(),.out_error(child_error[3]),
  .fault_pending(child_pending[3]),.generation_out(small_owner),.data_out(small_data));
 wire [{p*28-1}:0] input_wide,fwd_data,square_wide,inv_data;
 wire [{width-1}:0] canonical_spectrum,addA_rhs,addA_data,addB_data,squared;
 wire fwd_slot,fwd_start,addA_slot,addA_start,addB_slot,addB_start,square_slot,square_start,inv_slot,inv_start;
 wire [7:0] fwd_generation,addA_generation,addB_generation,square_generation,inv_generation;
 wire [ROW_W-1:0] pw_row=protocol_pw_row;
 logic [ROW_W-1:0] addA_row;logic addA_bank;
 wire [ROW_W-1:0] seed_target=ROW_W'(seed_row);
 wire [ROW_W-1:0] term_target=pw_row+ROW_W'(4);
 wire [{width-1}:0] term_seed_coeff,term_seed_roots,term_next_coeff,term_next_roots,term_data;
 wire [26:0] term_factor;wire term_slot,term_start,term_cache_ready;
 wire [23:0] term_owner,term_cache_owner;wire [ROW_W-1:0] term_row;
{chr(10).join(wiring)}
 {forward} forward_transform (
  .clk,.rst_n,.in_slot_valid(digit_slot),.frame_start(digit_tag[0][ROW_W]),.quarantine(stop),
  .context_enabled,.generation_in(digit_tag[0][ROW_W+8:ROW_W+1]),.live_generation,.data_in(input_wide),
  .out_slot_valid(fwd_slot),.out_frame_start(fwd_start),.out_eligible(),.out_error(child_error[4]),
  .fault_pending(child_pending[4]),.generation_out(fwd_generation),.data_out(fwd_data));
 {roots} term_roots (
  .clk,.rst_n,.seed_slot(seed_running),.seed_start(seed_running && seed_row==0),.seed_row,
  .pw_slot(fwd_slot),.pw_start(fwd_start),.pw_row,
  .seed_R_roots(term_seed_roots),.next_seed_R_roots(term_next_roots),.update_R_factor(term_factor));
 {term} #(.AW({aw}),.LANES(LANES),.P(32'd{prime}),.Q(32'd{q})) term_producer (
  .clk,.rst_n,.quarantine(stop),.seed_slot(seed_running),.seed_start(seed_running && seed_row==0),
  .seed_owner,.seed_row,.seed_coeff(term_seed_coeff),.seed_R_roots(term_seed_roots),
  .pointwise_slot(fwd_slot),.pointwise_start(fwd_start),.pointwise_owner({{protocol_pw_epoch,fwd_generation}}),
  .pointwise_row(pw_row),.next_coeff(term_next_coeff),.next_seed_R_roots(term_next_roots),.update_R_factor(term_factor),
  .term_slot,.term_start,.term_owner,.term_row,.term_data,
  .cache_ready(term_cache_ready),.cache_owner(term_cache_owner),.out_error(child_error[5]),.fault_pending(child_pending[5]));
 genefer_stream27_add_param_v1 #(.LANES(LANES),.P(32'd{prime})) add_A (
  .clk,.rst_n,.in_slot_valid(fwd_slot),.frame_start(fwd_start),.quarantine(stop),
  .generation_in(fwd_generation),.lhs(canonical_spectrum),.rhs(addA_rhs),
  .out_slot_valid(addA_slot),.out_frame_start(addA_start),.out_error(child_error[6]),
  .fault_pending(child_pending[6]),.generation_out(addA_generation),.result(addA_data));
 wire term_join_valid=term_slot && term_row==addA_row &&
  term_owner=={{table_epoch[addA_bank],addA_generation}};
 genefer_stream27_add_param_v1 #(.LANES(LANES),.P(32'd{prime})) add_B (
  .clk,.rst_n,.in_slot_valid(addA_slot && term_join_valid),.frame_start(addA_start),.quarantine(stop),
  .generation_in(addA_generation),.lhs(addA_data),.rhs(term_data),
  .out_slot_valid(addB_slot),.out_frame_start(addB_start),.out_error(child_error[7]),
  .fault_pending(child_pending[7]),.generation_out(addB_generation),.result(addB_data));
 {square} pointwise_square (
  .clk,.rst_n,.in_slot_valid(addB_slot),.frame_start(addB_start),.quarantine(stop),
  .generation_in(addB_generation),.data_in(addB_data),.out_slot_valid(square_slot),.out_frame_start(square_start),
  .out_error(child_error[8]),.fault_pending(child_pending[8]),.generation_out(square_generation),.data_out(squared));
 wire inverse_error,inverse_pending;
 {inverse} inverse_transform (
  .clk,.rst_n,.in_slot_valid(square_slot),.frame_start(square_start),.quarantine(stop),
  .context_enabled,.generation_in(square_generation),.live_generation,.data_in(square_wide),
  .out_slot_valid(inv_slot),.out_frame_start(inv_start),.out_eligible(),.out_error(inverse_error),
  .fault_pending(inverse_pending),.generation_out(inv_generation),.data_out(inv_data));
 assign out_slot_valid=inv_slot && !stop;assign out_frame_start=inv_start && out_slot_valid;
 assign generation_out=inv_generation;assign out_epoch=protocol_sink_epoch;assign output_row=protocol_sink_row;
 assign out_eligible=protocol_commit;
 always_comb begin
  join_bad=(fwd_slot && (!protocol_pw_accept || !tables_ready[protocol_pw_epoch[0]] ||
   table_epoch[protocol_pw_epoch[0]]!=protocol_pw_epoch || table_generation[protocol_pw_epoch[0]]!=fwd_generation)) ||
   (small_slot && small_capture && small_owner!=small_first_owner) ||
   (addA_slot && !term_join_valid);
 end
 genefer_stream27_epoch_protocol_v5 #(.ROWS(ROWS),.POINTWISE_FIRST({g['pointwise_accept']}),
  .SINK_FIRST({g['sink_accept']}),.EPOCH_W(16)) epoch_protocol (
  .clk,.rst_n,.quarantine(stop),.external_fault_pending(admission_bad || join_bad || (|child_pending) || inverse_pending),
  .frame_begin(raw_begin),.frame_epoch(epoch_in),.frame_generation(generation_in),.frame_base(base_in),
  .correction_valid,.correction_epoch,.correction_generation,
  .cache_ready(term_cache_ready),.cache_epoch(term_cache_owner[23:8]),.cache_generation(term_cache_owner[7:0]),
  .pointwise_slot(fwd_slot),.pointwise_frame_start(fwd_start),.pointwise_generation(fwd_generation),
  .sink_slot(out_slot_valid),.sink_frame_start(out_frame_start),.sink_generation(generation_out),
  .context_enabled,.live_generation,.frame_accept(protocol_frame_accept),.correction_accept(protocol_correction_accept),
  .correction_base(protocol_correction_base),.pointwise_accept(protocol_pw_accept),.commit_enable(protocol_commit),
  .pointwise_epoch(protocol_pw_epoch),.sink_epoch(protocol_sink_epoch),
  .pointwise_row(protocol_pw_row),.sink_row(protocol_sink_row),.owner_count,.out_error(protocol_error),.fault_pending(protocol_pending));
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   input_remaining<=0;input_row<=0;c1_pending<=0;small_capture<=0;seed_running<=0;seed_row<=0;
   tables_ready<=0;controller_error<=0;commit_valid<=0;commit_frame_start<=0;cycle_count<=0;frame_count<=0;
  end else begin
   cycle_count<=cycle_count+32'd1;commit_valid<=0;commit_frame_start<=0;
   if(!stop && (admission_bad || join_bad || (|child_pending) || (|child_error) || inverse_pending || inverse_error || protocol_pending || protocol_error))
    controller_error<=1;
   if(!stop)begin
    c1_pending<=accepted_correction;
    if(accepted)begin
     if(frame_start)begin
      input_remaining<=(ROW_W+1)'(ROWS-1);input_row<=ROW_W'(1);
      active_base<=base_in;active_generation<=generation_in;active_epoch<=epoch_in;
      tables_ready[epoch_in[0]]<=0;frame_count<=frame_count+32'd1;
     end else begin input_remaining<=input_remaining-(ROW_W+1)'(1);input_row<=input_row+ROW_W'(1);end
    end
    if(accepted_correction)begin high_correction<=c1_in;high_base<=protocol_correction_base;
     high_owner<={{correction_epoch,correction_generation}};end
    if(seed_running)begin seed_row<=seed_row+2'd1;if(seed_row==3)seed_running<=0;end
    if(small_slot)begin
{capture}
     small_capture<=!small_capture;
     if(small_capture)begin seed_running<=1;seed_row<=0;seed_owner<=small_owner;
      table_epoch[small_owner[8]]<=small_owner[23:8];table_generation[small_owner[8]]<=small_owner[7:0];
     end else small_first_owner<=small_owner;
    end
    if(fwd_slot)begin addA_row<=pw_row;addA_bank<=protocol_pw_epoch[0];end
    if(term_cache_ready && table_epoch[term_cache_owner[8]]==term_cache_owner[23:8] &&
       table_generation[term_cache_owner[8]]==term_cache_owner[7:0])tables_ready[term_cache_owner[8]]<=1;
    if(protocol_commit)begin commit_valid<=1;commit_frame_start<=out_frame_start;
     commit_generation<=generation_out;commit_epoch<=protocol_sink_epoch;commit_data<=data_out;end
   end
  end
 end
 // synthesis translate_off
 initial if(AW!={aw} || P!=LANES || CONTEXTS!=1)$fatal(1,"S4_SHARED_GENERATED_PARAMETERS");
 // synthesis translate_on
endmodule
'''
