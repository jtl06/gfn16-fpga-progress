"""S4-b real three-field/CRT/carry intermediate, not canonical host completion.

The external dense row/correction API is intentional for the first arithmetic
gate. Feedback from actual output rows is exercised by the native harness;
the finite production recurrence/readback adapter is a subsequent integration
gate, not implied by represented-residue equality.
"""
import hashlib
from pathlib import Path
from .stream27_shared_field_v2 import ROOT,prepare as compile_field
from .stream27_shared_field_v2 import geometry

COMPONENTS=['rtl/kernel/genefer_crt3_27_mont_pipe.sv',
    'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv','rtl/kernel/genefer_track_a4_setup_v1.sv',
    'rtl/kernel/genefer_track_a4_blockcarry_lane_v1.sv','rtl/kernel/genefer_div_recip_precision.sv',
    'rtl/kernel/genefer_stream27_blockcarry_small_cell.sv']


def source(n,fields):
    aw=n.bit_length()-1;rw=aw-4;p=16;top=f'genefer_stream27_threefield_carry_aw{aw}_p16_v1'
    instances=[]
    for f,b in enumerate(fields):
        instances.append(f''' {b['top']} #(.AW(AW),.P(P),.CONTEXTS(CONTEXTS)) field{f} (
  .clk,.rst_n,.in_slot_valid(in_slot_valid && !out_error),.frame_start,
  .context_enabled(context_enabled && !out_error),.generation_in,.live_generation,.base_in,
  .epoch_in,.correction_epoch,.correction_valid(correction_valid && !out_error),.correction_generation,
  .data_in,.c0_in,.c1_in,.out_slot_valid(field_valid[{f}]),.out_frame_start(field_start[{f}]),
  .out_eligible(field_eligible[{f}]),.out_error(field_error[{f}]),.fault_pending(field_pending[{f}]),
  .generation_out(field_generation[{f}]),.data_out(field_data[{f}]),.out_epoch(field_epoch[{f}]),
  .commit_valid(),.commit_frame_start(),.commit_generation(),.commit_epoch(),.commit_data(),
  .owner_count(field_owners[{f}]),.frame_accept(field_frame_accept[{f}]),
  .correction_accept(field_correction_accept[{f}]),.output_row(field_row[{f}]),.cycle_count(),.frame_count());''')
    return top,f'''// Real S4-b arithmetic intermediate. Canonical host/readback gate is separate.
module {top} #(parameter int AW={aw},P=16,CONTEXTS=1) (
 input logic clk,rst_n,begin_setup,in_slot_valid,frame_start,context_enabled,double_in,
 input logic [7:0] generation_in,live_generation,
 input logic [31:0] base_in,
 input logic [15:0] epoch_in,correction_epoch,
 input logic correction_valid,input logic [7:0] correction_generation,
 input logic [P*32-1:0] data_in,c0_in,c1_in,
 output logic config_valid,setup_done,out_error,fault_pending,frame_accept,correction_accept,
 output logic coefficient_valid,coefficient_start,
 output logic signed [P*96-1:0] coefficient_data,
 output logic [AW-5:0] coefficient_row,
 output logic digit_valid,digit_start,digit_eligible,
 output logic [P*32-1:0] digit_data,
 output logic [AW-5:0] digit_row,
 output logic [15:0] digit_epoch,output logic [7:0] digit_generation,
 output logic boundary_valid,boundary_eligible,
 output logic [P*32-1:0] next_c0,next_c1,
 output logic [15:0] next_epoch,output logic [7:0] next_generation,
 output logic frame_done,output logic [15:0] done_epoch);
 localparam int ROW_W=AW-4,ROWS=1<<ROW_W,TAG_W=24+ROW_W;
 wire [2:0] field_valid,field_start,field_eligible,field_error,field_pending;
 wire [2:0] field_frame_accept,field_correction_accept;
 wire [P*27-1:0] field_data[0:2];wire [ROW_W-1:0] field_row[0:2];
 wire [15:0] field_epoch[0:2];wire [7:0] field_generation[0:2];wire [1:0] field_owners[0:2];
 logic [15:0] bank_epoch[0:1];logic [7:0] bank_generation[0:1];logic bank_double[0:1];
 logic [31:0] bank_base[0:1];
 wire setup_error,setup_busy;wire [31:0] qualified_base,qualified_generation;
 wire [95:0] reciprocal;wire [76:0] coefficient_limit;
 genefer_track_a4_setup_v1 #(.AW(AW)) shared_setup (
  .clk,.rst_n,.begin_setup,.cancel(out_error),.base(base_in),.generation({{24'd0,generation_in}}),
  .busy(setup_busy),.done(setup_done),.error(setup_error),.config_valid,
  .accepted_base(qualified_base),.out_generation(qualified_generation),.coefficient_limit,.reciprocal);
{chr(10).join(instances)}
 assign frame_accept=&field_frame_accept;assign correction_accept=&field_correction_accept;
 wire joined=&field_valid;
 wire join_start=&field_start;
 wire bank=field_epoch[0][0];
 wire begin_carry=joined && join_start && !out_error;
 wire [P-1:0] crt_valid,crt_ready,lane_busy,lane_done,lane_error,lane_digit_valid,lane_boundary_valid;
 wire [3:0] lane_error_code[0:P-1];wire signed [95:0] crt_coefficient[0:P-1];
 wire [31:0] lane_digit[0:P-1],lane_low[0:P-1];wire signed [31:0] lane_high[0:P-1];
 wire [AW-1:0] lane_offset[0:P-1];
 logic [TAG_W-1:0] crt_tag[0:15];logic crt_double[0:15];
 logic doubled_valid,doubled_start;logic [ROW_W-1:0] doubled_row;
 logic [P*96-1:0] doubled_data;
 logic [15:0] carry_epoch;logic [7:0] carry_generation;
 logic join_bad,carry_bad,admission_bad;
 assign coefficient_valid=doubled_valid && !out_error;assign coefficient_start=doubled_start && coefficient_valid;
 assign coefficient_data=$signed(doubled_data);assign coefficient_row=doubled_row;
 assign digit_valid=(&lane_digit_valid) && !out_error;assign digit_row=lane_offset[0][ROW_W-1:0];
 assign digit_start=digit_valid && lane_offset[0]==0;
 assign digit_epoch=carry_epoch;assign digit_generation=carry_generation;
 assign digit_eligible=digit_valid && context_enabled && carry_generation==live_generation;
 assign boundary_valid=(&lane_boundary_valid) && !out_error;
 assign boundary_eligible=boundary_valid && context_enabled && carry_generation==live_generation;
 assign next_epoch=carry_epoch+16'd1;assign next_generation=carry_generation;
 assign frame_done=(&lane_done) && !out_error;assign done_epoch=carry_epoch;
 assign fault_pending=out_error || setup_error || (|field_error) || (|field_pending) ||
  (|lane_error) || join_bad || carry_bad || admission_bad;
 always_comb begin
  join_bad=(|field_valid) && !joined;
  if(joined)begin
   for(int f=1;f<3;f=f+1)if(field_start[f]!=field_start[0] || field_row[f]!=field_row[0] ||
    field_epoch[f]!=field_epoch[0] || field_generation[f]!=field_generation[0] ||
    field_eligible[f]!=field_eligible[0])join_bad=1;
   if(!config_valid || bank_base[bank]!=qualified_base || bank_epoch[bank]!=field_epoch[0] ||
    bank_generation[bank]!=field_generation[0])join_bad=1;
  end
  carry_bad=((|crt_valid) && !(&crt_valid)) || ((|lane_digit_valid) && !(&lane_digit_valid)) ||
   ((|lane_boundary_valid) && !(&lane_boundary_valid)) || ((|lane_done) && !(&lane_done));
  if(begin_carry && (|lane_busy))carry_bad=1;
  for(int b=1;b<P;b=b+1)if(digit_valid && lane_offset[b]!=lane_offset[0])carry_bad=1;
  admission_bad=(in_slot_valid && frame_start && (!config_valid || base_in!=qualified_base)) ||
   (begin_setup && (in_slot_valid || correction_valid || (|lane_busy) || (|field_owners[0])));
 end
 for(genvar b=0;b<P;b=b+1)begin: arithmetic
  // Static inverse physical lane reverse(b,4) -> natural block b.
  localparam int PHYSICAL=((b&1)<<3)|((b&2)<<1)|((b&4)>>1)|((b&8)>>3);
  genefer_crt3_27_mont_pipe crt (
   .clk,.rst_n,.in_valid(joined && !out_error),
   .r1({{5'd0,field_data[0][27*PHYSICAL+:27]}}),
   .r2({{5'd0,field_data[1][27*PHYSICAL+:27]}}),
   .r3({{5'd0,field_data[2][27*PHYSICAL+:27]}}),
   .ready(crt_ready[b]),.out_valid(crt_valid[b]),.coefficient(crt_coefficient[b]));
  genefer_track_a4_blockcarry_lane_v1 #(.AW(AW)) carry (
   .clk,.rst_n,.begin_block(begin_carry),.in_valid(coefficient_valid),
   .block_start(doubled_start),.block_end(doubled_row==ROW_W'(ROWS-1)),
   .base(qualified_base),.reciprocal,.coefficient_limit,
   .coefficient($signed(doubled_data[96*b+:96])),.offset(AW'(doubled_row)),
   .busy(lane_busy[b]),.done(lane_done[b]),.error(lane_error[b]),.error_code(lane_error_code[b]),
   .digit_valid(lane_digit_valid[b]),.digit(lane_digit[b]),.digit_offset(lane_offset[b]),
   .boundary_valid(lane_boundary_valid[b]),.boundary_low(lane_low[b]),.boundary_high(lane_high[b]));
  assign digit_data[32*b+:32]=lane_digit[b];
  if(b==0)begin: signed_wrap
   wire signed [32:0] signed_low=$signed({{1'b0,lane_low[P-1]}});
   wire signed [32:0] signed_high=$signed({{lane_high[P-1][31],lane_high[P-1]}});
   assign next_c0[0+:32]=32'(-signed_low);assign next_c1[0+:32]=32'(-signed_high);
  end else begin: rotate
   assign next_c0[32*b+:32]=lane_low[b-1];assign next_c1[32*b+:32]=lane_high[b-1];
  end
 end
 always_ff @(posedge clk)begin
  if(joined)begin crt_tag[0]<={{field_epoch[0],field_generation[0],field_row[0]}};crt_double[0]<=bank_double[bank];end
  for(int d=1;d<16;d=d+1)begin crt_tag[d]<=crt_tag[d-1];crt_double[d]<=crt_double[d-1];end
  if(&crt_valid)begin
   for(int b=0;b<P;b=b+1)doubled_data[96*b+:96]<=crt_double[15] ? crt_coefficient[b]<<<1 : crt_coefficient[b];
   doubled_row<=crt_tag[15][ROW_W-1:0];doubled_start<=crt_tag[15][ROW_W-1:0]==0;
  end
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin out_error<=0;doubled_valid<=0;carry_epoch<=0;carry_generation<=0;end
  else begin
   if(fault_pending)out_error<=1;
   doubled_valid<=(&crt_valid) && !out_error;
   if(frame_accept && in_slot_valid && frame_start)begin
    bank_epoch[epoch_in[0]]<=epoch_in;bank_generation[epoch_in[0]]<=generation_in;
    bank_base[epoch_in[0]]<=base_in;bank_double[epoch_in[0]]<=double_in;
   end
   if(begin_carry)begin carry_epoch<=field_epoch[0];carry_generation<=field_generation[0];end
  end
 end
 // synthesis translate_off
 initial if(AW!={aw} || P!=16 || CONTEXTS!=1)$fatal(1,"S4_THREEFIELD_EXPLICIT_GEOMETRY");
 // synthesis translate_on
endmodule
'''


def prepare(n=32,p=16,*,contexts=1,allow_full_constants=False):
    if (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('brief PAUSE')
    if p!=16 or contexts!=1:raise ValueError('S4_THREEFIELD_NATIVE_CARRY_P16_CONTEXTS1_ONLY')
    fields=[compile_field(n,p,f,contexts=contexts,allow_full_constants=allow_full_constants) for f in range(3)]
    files={};deps=[]
    for b in fields:
        for name,text in b['files'].items():
            if name in files and files[name]!=text:raise ValueError('S4_SHARED_DEFINITION_COLLISION:'+name)
            files[name]=text
        deps+=b['source_dependencies']
    for path in COMPONENTS:
        name=Path(path).name;text=(ROOT/path).read_text()
        if name in files and files[name]!=text:raise ValueError('S4_COMPONENT_COLLISION:'+name)
        files[name]=text
    top,text=source(n,fields);files[top+'.sv']=text
    deps=list(dict.fromkeys(deps+COMPONENTS+['reference/stream27_threefield_carry_v1.py']))
    return dict(top=top,files=files,rtl_sources=[name for name in files if name.endswith('.sv')],
        source_dependencies=deps,source_sha256={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in deps},
        generated_sha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in files.items()},
        geometry=geometry(n,p),parameters=dict(AW=n.bit_length()-1,P=p,CONTEXTS=contexts),
        scope='S4-b represented-residue arithmetic intermediate; no canonical host/readback or actual warm controller qualification',
        setup_latency=97,full_N_numeric_NTT_performed=False,native_run_performed=False,RTL_qualified=False)
