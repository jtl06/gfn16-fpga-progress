"""Connected lean28/S-M1/S-M2/r17 P16-c physical probe, source only.

Canonical consumers at pointwise and final GS are explicit. All other CT/GS
butterflies use reviewed lazy28 scalar source. Full-size work is embedded exact
root constants/geometry, never a numerical NTT. Native/cloud dispatch is absent.
"""
import argparse
import hashlib
import json
from math import ceil
from pathlib import Path
import tarfile

from . import merged_stream27_model_v1 as merged
from .merged_stream27_root_compile_v1 import compile_roots
from .stream_ntt_model import FIELDS
from .stream_ntt_schedule import m20k
from .stream27_field_physical_probe_v1 import DEVICE,RUN_TCL,SDC,PORTS,OMITTED

ROOT=Path(__file__).resolve().parents[1]
BRIEFS=('docs/briefs/2026-10-01-P16-field-probes.md','docs/briefs/2026-10-01-answers-B20260930-r17.md',
        'docs/briefs/2026-10-01-answers-B20260930-r21.md')
PINNED={
 'rtl/kernel/genefer_ntt_lazy28_butterfly_v1.sv':'ade6280dd1dac0fe3049ac2860dea7bbc7db292b634368e12f557b63865aa00d',
 'rtl/kernel/genefer_montgomery_mul28x27_sparse_pipe_v2.sv':'a93cb002eb08e585e62a847ef4b070175ae8108919da30ea5bf67dad3a597026',
 'rtl/kernel/genefer_stream27_merged_final_gs_pair_v1.sv':'c860243f74d445324e93d8d2bc202521249316f04364c4bb2e630d4328216d4b',
 'rtl/kernel/genefer_stream27_mdc_fifo_smallreg_v1.sv':'0ff1605c74d81670291f1bd0ee88afe6f5461d999d5ee65fc6f1cc722f4ec4be'}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def source_guard():
    for path,pin in PINNED.items():
        if sha((ROOT/path).read_bytes())!=pin:raise ValueError('P16C_SOURCE_DRIFT:'+path)
    if (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('brief PAUSE')


def transform_source(n,p,field,inverse,roots):
    plan=merged.topology(n,p,inverse=inverse);aw=plan['aw'];pairs=p//2;prime=FIELDS[field][0]
    name=f'genefer_stream28_merged_{"gs" if inverse else "ct"}_aw{aw}_p{p}_f{field}_v1'
    direction='GS' if inverse else 'CT';width=p*28
    out=[f'// Connected P16-c {direction}: physical occupied rows are never filtered by eligibility.',
         f'module {name} #(parameter int GEN_W=8) (',
         ' input logic clk,rst_n,in_slot_valid,frame_start,quarantine,context_enabled,',
         ' input logic [GEN_W-1:0] generation_in,live_generation,',
         f' input logic [{width-1}:0] data_in,',
         ' output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,',
         ' output logic [GEN_W-1:0] generation_out,',f' output logic [{width-1}:0] data_out);',
         f' localparam int STAGES={aw},FRAME_T={n//p},PAIRS={pairs};',
         ' logic [STAGES:0] slot,start; logic [GEN_W-1:0] generation[0:STAGES];',
         f' logic [{width-1}:0] data[0:STAGES];',
         ' logic [STAGES-1:0] stage_pending; logic aggregate_error;',
         ' wire stop=quarantine || aggregate_error;',
         ' assign slot[0]=in_slot_valid;assign start[0]=frame_start;',
         ' assign generation[0]=generation_in;assign data[0]=data_in;',
         ' assign out_error=aggregate_error;assign fault_pending=aggregate_error || (|stage_pending);',
         ' assign out_slot_valid=slot[STAGES] && !stop;',
         ' assign out_frame_start=start[STAGES] && out_slot_valid;',
         ' assign generation_out=generation[STAGES];',
         ' assign out_eligible=out_slot_valid && context_enabled && generation_out==live_generation;',
         ' always_ff @(posedge clk or negedge rst_n)',
         '   if(!rst_n)aggregate_error<=0;',
         '   else if(!stop && (|stage_pending))aggregate_error<=1;']
    for spec in plan['stages']:
        s=spec['stage'];entry=next(item for item in roots['modules'] if item['direction']==direction and item['stage']==s)
        final=inverse and s==aw-1
        out += [f' if(1)begin: stage{s}',
                '  logic row_slot,row_start,local_error,shuffle_pending;',
                '  logic [GEN_W-1:0] row_generation;',f'  logic [{width-1}:0] row_data,bf_data;',
                '  logic [5:0] slot_pipe,start_pipe;logic [GEN_W-1:0] generation_pipe[0:5];',
                '  logic [PAIRS-1:0] bf_valid,pair_error;',
                '  localparam int COUNT_W=$clog2(FRAME_T+1);',
                '  logic [COUNT_W-1:0] remaining;logic [GEN_W-1:0] owner_generation;',
                '  wire cadence_bad=(row_start && (!row_slot || remaining!=0)) ||',
                '   (row_slot && !row_start && remaining==0) || (!row_slot && remaining!=0) ||',
                '   (row_slot && !row_start && remaining!=0 && row_generation!=owner_generation);',
                '  wire accept=row_slot && !stop && !local_error;',
                f'  assign stage_pending[{s}]=local_error || shuffle_pending || (|pair_error) ||',
                '   (!stop && (cadence_bad || bf_valid!={PAIRS{slot_pipe[5]}}));']
        depth=spec['shuffle_depth_per_buffer']
        if depth:
            pos=spec['commutator_lane_position'];swaps=[(lane,lane^(1<<pos)) for lane in range(p) if not lane&(1<<pos)]
            out += ['  logic [PAIRS-1:0] sh_slot,sh_start,sh_error,sh_pending;',
                    '  logic [GEN_W-1:0] sh_generation[0:PAIRS-1];',
                    '  logic shuffle_alignment_bad;',
                    '  assign row_slot=sh_slot[0];assign row_start=sh_start[0];assign row_generation=sh_generation[0];',
                    '  always_comb begin',
                    '   shuffle_alignment_bad=(|sh_slot) && (!(&sh_slot) || sh_start!={PAIRS{sh_start[0]}});',
                    '   for(int k=1;k<PAIRS;k=k+1)',
                    '    if((|sh_slot) && sh_generation[k]!=sh_generation[0])shuffle_alignment_bad=1;',
                    '  end',
                    '  assign shuffle_pending=(|sh_error) || (|sh_pending) || shuffle_alignment_bad;']
            for k,(lo,hi) in enumerate(swaps):
                out += [f'  genefer_stream27_mdc_commutator_sm1_registered_v1 #(.DATA_W(28),.PAYLOAD_W(1),',
                        f'   .GEN_W(GEN_W),.DEPTH({depth}),.FRAME_T(FRAME_T),.CONTEXTS(1)) shuffle{k} (',
                        f'   .clk,.rst_n,.in_slot_valid(slot[{s}]),.frame_start(start[{s}]),.quarantine(stop),',
                        f'   .upper_in(data[{s}][{lo*28}+:28]),.lower_in(data[{s}][{hi*28}+:28]),',
                        "   .upper_payload(1'b0),.lower_payload(1'b0),.context_in(1'b0),",
                        f'   .generation_in(generation[{s}]),.context_enabled,.live_generations(live_generation),',
                        f'   .out_slot_valid(sh_slot[{k}]),.out_frame_start(sh_start[{k}]),.out_eligible(),',
                        f'   .out_error(sh_error[{k}]),.fault_pending(sh_pending[{k}]),',
                        f'   .upper_out(row_data[{lo*28}+:28]),.lower_out(row_data[{hi*28}+:28]),',
                        '   .upper_payload_out(),.lower_payload_out(),.context_out(),',
                        f'   .generation_out(sh_generation[{k}]));']
        else:
            out += [f'  assign row_slot=slot[{s}];assign row_start=start[{s}];',
                    f'  assign row_generation=generation[{s}];assign row_data=data[{s}];',
                    "  assign shuffle_pending=1'b0;"]
        out += [f'  wire [{entry["width"]-1}:0] packed_roots;',
                f'  {entry["module"]} roots (.clk,.rst_n,.in_slot_valid(accept),.frame_start(row_start),.root(packed_roots));']
        for k,(lo,hi) in enumerate(spec['pairs']):
            root_offset=27*spec['root_stream_for_pair'][k]
            if final:
                # Boundaries preserve residue/domain but do not invent wide
                # finalGS support. One correction per [0,2P) operand suffices.
                out += [f'  wire [27:0] raw_u{k}=row_data[{lo*28}+:28],raw_v{k}=row_data[{hi*28}+:28];',
                        f"  wire [26:0] canonical_u{k}=27'(raw_u{k}>=28'd{prime} ? raw_u{k}-28'd{prime} : raw_u{k});",
                        f"  wire [26:0] canonical_v{k}=27'(raw_v{k}>=28'd{prime} ? raw_v{k}-28'd{prime} : raw_v{k});",
                        f'  wire [31:0] y0_{k},y1_{k};',
                        f'  genefer_stream27_merged_final_gs_pair_v1 #(.P(32\'d{prime}),.Q(32\'d{(2-prime)%(1<<32)}),',
                        f'   .UPPER_SCALE(32\'d{roots["final_upper_scale"]})) final_pair{k} (',
                        f"   .clk,.rst_n,.in_valid(accept),.u({{5'b0,canonical_u{k}}}),.v({{5'b0,canonical_v{k}}}),",
                        f"   .normalized_lower_root({{5'b0,packed_roots[{root_offset}+:27]}}),",
                        f'   .out_valid(bf_valid[{k}]),.out_error(pair_error[{k}]),.y0(y0_{k}),.y1(y1_{k}));',
                        f"  assign bf_data[{lo*28}+:28]={{1'b0,y0_{k}[26:0]}};",
                        f"  assign bf_data[{hi*28}+:28]={{1'b0,y1_{k}[26:0]}};"]
            else:
                out += [f'  genefer_ntt_lazy28_butterfly_v1 #(.P(32\'d{prime}),.Q(32\'d{(2-prime)%(1<<32)}),.TAG_W(1)) bf{k} (',
                        f"   .clk,.rst_n,.in_valid(accept),.gs(1'b{int(inverse)}),",
                        f'   .u(row_data[{lo*28}+:28]),.v(row_data[{hi*28}+:28]),.w(packed_roots[{root_offset}+:27]),',
                        "   .in_tag(1'b0),.out_tag(),",
                        f'   .out_valid(bf_valid[{k}]),.y0(bf_data[{lo*28}+:28]),.y1(bf_data[{hi*28}+:28]));',
                        f"  assign pair_error[{k}]=1'b0;"]
        out += [f'  assign slot[{s+1}]=slot_pipe[5] && (&bf_valid) && !stop;',
                f'  assign start[{s+1}]=start_pipe[5];assign generation[{s+1}]=generation_pipe[5];',
                f'  assign data[{s+1}]=bf_data;',
                '  always_ff @(posedge clk or negedge rst_n)begin',
                "   if(!rst_n)begin slot_pipe<=0;start_pipe<=0;local_error<=0;remaining<=0;end",
                '   else begin',
                '    if(!stop && (cadence_bad || shuffle_pending || (|pair_error) || bf_valid!={PAIRS{slot_pipe[5]}}))local_error<=1;',
                '    if(stop)begin slot_pipe<=0;start_pipe<=0;end',
                '    else begin',
                '     slot_pipe<={slot_pipe[4:0],accept};start_pipe<={start_pipe[4:0],accept && row_start};',
                '     generation_pipe[0]<=row_generation;',
                '     for(int k=1;k<6;k=k+1)generation_pipe[k]<=generation_pipe[k-1];',
                '     if(accept)begin',
                "      if(row_start)begin remaining<=COUNT_W'(FRAME_T-1);owner_generation<=row_generation;end",
                "      else remaining<=remaining-COUNT_W'(1);",
                '     end', '    end', '   end', '  end', ' end']
    for lane,wire in enumerate(plan['terminal_wire']):
        out.append(f' assign data_out[{28*lane}+:28]=data[STAGES][{28*wire}+:28];')
    out.append('endmodule\n')
    return name,'\n'.join(out),plan


def square_source(p,field):
    prime=FIELDS[field][0];name=f'genefer_stream27_square_p{p}_f{field}_v1';w=p*27
    return name,f'''// Canonical 27x27 pointwise square only, accepted k -> output k+3.
module {name} (
 input logic clk,rst_n,in_slot_valid,frame_start,quarantine,
 input logic [7:0] generation_in,input logic [{w-1}:0] data_in,
 output logic out_slot_valid,out_frame_start,out_error,fault_pending,
 output logic [7:0] generation_out,output logic [{w-1}:0] data_out);
 logic [{p-1}:0] lane_valid;logic [3:0] slot_pipe,start_pipe;
 logic [7:0] generation_pipe[0:3];
 wire mismatch=lane_valid!={{{p}{{slot_pipe[3]}}}};
 assign fault_pending=out_error || (!quarantine && mismatch);
 assign out_slot_valid=slot_pipe[3] && (&lane_valid) && !quarantine && !out_error;
 assign out_frame_start=start_pipe[3] && out_slot_valid;assign generation_out=generation_pipe[3];
 for(genvar lane=0;lane<{p};lane=lane+1)begin: square_lane
  wire [31:0] result;
  genefer_montgomery_mul27_sparse_pipe #(.P(32'd{prime}),.Q(32'd{(2-prime)%(1<<32)})) multiplier (
   .clk,.rst_n,.in_valid(in_slot_valid && !quarantine),
   .lhs({{5'b0,data_in[lane*27+:27]}}),.rhs({{5'b0,data_in[lane*27+:27]}}),
   .out_valid(lane_valid[lane]),.result(result));
  assign data_out[lane*27+:27]=result[26:0];
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin slot_pipe<=0;start_pipe<=0;out_error<=0;end
  else begin
   if(!quarantine && mismatch)out_error<=1;
   if(quarantine || out_error)begin slot_pipe<=0;start_pipe<=0;end
   else begin
    slot_pipe<={{slot_pipe[2:0],in_slot_valid}};start_pipe<={{start_pipe[2:0],in_slot_valid && frame_start}};
    generation_pipe[0]<=generation_in;
    for(int k=1;k<4;k=k+1)generation_pipe[k]<=generation_pipe[k-1];
   end
  end
 end
endmodule
'''


def top_source(n,p,field,forward,inverse,square):
    aw=n.bit_length()-1;tw=aw-(p.bit_length()-1);rows=n//p;prime=FIELDS[field][0]
    name=f'genefer_stream27_p16c_physical_aw{aw}_p{p}_f{field}_v1'
    return name,f'''// Provisional cold/nonoverlap component physical probe, not whole streaming qualification.
module {name} #(parameter int AW={aw},CONTEXTS=1) (
 input logic clk,rst_n,start,context_enabled,
 input logic [7:0] generation_in,live_generation,input logic [{p*27-1}:0] data_in,
 output logic ready,busy,done,error,fault_pending,out_slot_valid,out_frame_start,out_eligible,
 output logic [7:0] generation_out,output logic [{p*27-1}:0] data_out,
 output logic [{max(1,tw)-1}:0] output_row,output logic [31:0] cycles);
 localparam int T={rows},ROW_W={max(1,tw)},COUNT_W=$clog2(T+1);
 logic [COUNT_W-1:0] remaining_input;logic [7:0] active_generation;logic controller_error;
 logic [2:0] child_error,child_pending;logic [{p-1}:0] range_lanes;
 wire stop=controller_error;
 wire request_slot=(ready && start) || (busy && remaining_input!=0);
 wire range_bad=request_slot && (|range_lanes);
 wire accepted=rst_n && request_slot && !stop;
 wire accepted_start=accepted && !busy;
 wire [7:0] accepted_generation=accepted_start ? generation_in : active_generation;
 wire [{p*28-1}:0] input_wide,fwd_data,square_wide,inv_data;
 wire [{p*27-1}:0] canonical_spectrum,square_data;
 wire fwd_slot,fwd_start,square_slot,square_start,inv_slot,inv_start;
 wire [7:0] fwd_generation,square_generation,inv_generation;
 assign ready=rst_n && !busy && !stop;assign error=controller_error;
 assign fault_pending=controller_error || range_bad || (|child_pending);
 for(genvar lane=0;lane<{p};lane=lane+1)begin: canonical_boundaries
  wire [27:0] raw_spectrum=fwd_data[lane*28+:28];
  assign range_lanes[lane]={{5'b0,data_in[lane*27+:27]}}>=32'd{prime};
  assign input_wide[lane*28+:28]={{1'b0,data_in[lane*27+:27]}};
  assign canonical_spectrum[lane*27+:27]=27'(raw_spectrum>=28'd{prime} ? raw_spectrum-28'd{prime} : raw_spectrum);
  assign square_wide[lane*28+:28]={{1'b0,square_data[lane*27+:27]}};
  assign data_out[lane*27+:27]=inv_data[lane*28+:27];
  // synthesis translate_off
  always @(posedge clk)if(rst_n && fwd_slot && raw_spectrum>=28'd{2*prime})$fatal(1,"P16C_SPECTRUM_RANGE");
  always @(posedge clk)if(rst_n && inv_slot && inv_data[lane*28+:28]>=28'd{prime})$fatal(1,"P16C_FINAL_CANONICAL_RANGE");
  // synthesis translate_on
 end
 {forward} forward_transform (
  .clk,.rst_n,.in_slot_valid(accepted),.frame_start(accepted_start),.quarantine(stop),
  .context_enabled,.generation_in(accepted_generation),.live_generation,.data_in(input_wide),
  .out_slot_valid(fwd_slot),.out_frame_start(fwd_start),.out_eligible(),
  .out_error(child_error[0]),.fault_pending(child_pending[0]),.generation_out(fwd_generation),.data_out(fwd_data));
 {square} pointwise_square (
  .clk,.rst_n,.in_slot_valid(fwd_slot),.frame_start(fwd_start),.quarantine(stop),
  .generation_in(fwd_generation),.data_in(canonical_spectrum),
  .out_slot_valid(square_slot),.out_frame_start(square_start),.out_error(child_error[1]),
  .fault_pending(child_pending[1]),.generation_out(square_generation),.data_out(square_data));
 {inverse} inverse_transform (
  .clk,.rst_n,.in_slot_valid(square_slot),.frame_start(square_start),.quarantine(stop),
  .context_enabled,.generation_in(square_generation),.live_generation,.data_in(square_wide),
  .out_slot_valid(inv_slot),.out_frame_start(inv_start),.out_eligible(),
  .out_error(child_error[2]),.fault_pending(child_pending[2]),.generation_out(inv_generation),.data_out(inv_data));
 assign out_slot_valid=inv_slot && !stop;assign out_frame_start=inv_start && out_slot_valid;
 assign generation_out=inv_generation;
 assign out_eligible=out_slot_valid && context_enabled && inv_generation==live_generation && inv_generation==active_generation;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin busy<=0;done<=0;controller_error<=0;remaining_input<=0;output_row<=0;cycles<=0;end
  else begin
   done<=0;
   if(!stop && (range_bad || (|child_pending) || (|child_error) ||
      (inv_slot && inv_generation!=active_generation)))controller_error<=1;
   if(busy)cycles<=cycles+32'd1;
   if(accepted)begin
    if(accepted_start)begin busy<=1;remaining_input<=COUNT_W'(T-1);active_generation<=generation_in;output_row<=0;cycles<=0;end
    else remaining_input<=remaining_input-COUNT_W'(1);
   end
   if(inv_slot && !stop)begin
    if(output_row==ROW_W'(T-1))begin busy<=0;done<=1;end
    else output_row<=output_row+ROW_W'(1);
   end
  end
 end
 // synthesis translate_off
 initial if(AW!={aw} || CONTEXTS!=1)$fatal(1,"P16C_GENERATED_AW_CONTEXT_FIXED");
 // synthesis translate_on
endmodule
'''


def compile_probe(n=64,p=16,field=0,*,allow_full_constants=False):
    source_guard()
    roots=compile_roots(n,p,field,allow_full_constants=allow_full_constants,embed_roms=True)
    transforms=[transform_source(n,p,field,inverse,roots) for inverse in (False,True)]
    square,square_sv=square_source(p,field)
    top,top_sv=top_source(n,p,field,transforms[0][0],transforms[1][0],square)
    generated={**{name:roots['files'][name] for name in roots['compiled_sv_files']},
        **{name+'.sv':text for name,text,_ in transforms},square+'.sv':square_sv,top+'.sv':top_sv}
    deps=list(PINNED)+['rtl/kernel/genefer_stream27_mdc_commutator_sm1_registered_v1.sv',
        'rtl/kernel/genefer_stream27_mdc_commutator_sync.sv','rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv',
        'rtl/kernel/genefer_ntt_banked27_engine.sv']
    compiled={Path(path).name:(ROOT/path).read_text() for path in deps};compiled.update(generated)
    stages=[s for _,_,plan in transforms for s in plan['stages']]
    short=[s['shuffle_depth_per_buffer'] for s in stages if 0<s['shuffle_depth_per_buffer']<=32]
    deep=[s['shuffle_depth_per_buffer'] for s in stages if s['shuffle_depth_per_buffer']>32]
    word_bits=28+1+8+1+1;register_bits=p*sum(short)*word_bits
    delay_ram=p*sum(m20k(depth,word_bits) for depth in deep)
    aw=n.bit_length()-1;interior=(2*aw-1)*(p//2);final=p//2
    parts={
        'lazy_interior_pairs':dict(units=interior,ALM_per_unit_proxy=281.25,basis='advisor estimated25% reduction from375 canonical proxy, UNMEASURED'),
        'canonical_final_GS_pairs':dict(units=final,ALM_per_unit_proxy=375,basis='no lazy credit at final canonical boundary'),
        'canonical_pointwise_square':dict(units=p,ALM_per_unit_proxy=375,basis='27x27 only'),
        'extra_upper_normalizers':dict(units=final,ALM_per_unit_proxy=375,basis='real additional parallel sparse pipe'),
        'canonicalizers':dict(units=2*p,ALM_per_unit_proxy=25,basis='planning assumption for one P subtract/select, UNMEASURED'),
        'short_delay_registers':dict(units=register_bits,ALM_per_unit_proxy=.25,basis='optimistic4FF/ALM packing proxy;2FF/ALM doubles this term; no MLAB credit')}
    for part in parts.values():part['ALM_planning_proxy']=ceil(part['units']*part['ALM_per_unit_proxy'])
    first_ct=transforms[0][2]['first_output_edge'];first_gs=transforms[1][2]['first_output_edge']
    # CT accepted0 -> physical first_ct. Square next-edge accept +1, k+3;
    # inverse accepts next edge again, giving +5 before its first output.
    physical=first_ct+5+first_gs
    return dict(top=top,files=compiled,generated_files=generated,root_data_files=roots['root_data_files'],
        root_data_sha256={name:sha(roots['files'][name].encode()) for name in roots['root_data_files']},
        source_dependencies=deps,geometry=dict(n=n,p=p,aw=aw,rows=n//p,field_index=field,
            prime=FIELDS[field][0],contexts=1,data_internal_bits=28,canonical_boundary_bits=27,
            payload_bits=1,generation_bits=8,token_total_bits=word_bits),
        resource_basis=dict(components=parts,included_noncontrol_ALM_proxy=sum(x['ALM_planning_proxy'] for x in parts.values()),
            included_ALM_proxy_with2FF_per_ALM=sum(x['ALM_planning_proxy'] for x in parts.values())+ceil(register_bits/4),
            control_reserve_allocation='unallocated; minimal sequencing/control and filled counters must be measured',
            DSP_proxy=interior+final+p+final,lazyBF_DSP_mapping_unmeasured=True,
            root_M20K_proxy=roots['root_M20K_tiling_proxy'],delay_M20K_proxy=delay_ram,
            IO_root_M20K=0,M20K_proxy=roots['root_M20K_tiling_proxy']+delay_ram,
            short_FIFO_count=p*len(short),short_FIFO_storage_bits=register_bits,short_FIFO_depths=short,
            deep_FIFO_count=p*len(deep),deep_FIFO_depths=deep,physical_inference_qualified=False),
        root_ledger=roots['modules'],calendar=dict(first_input_accept=0,first_forward_physical=first_ct,
            first_square_accept=first_ct+1,first_inverse_accept=first_ct+5,first_physical_output=physical,
            first_terminal_sample=physical+1,last_terminal_sample=physical+n//p,next_nonoverlap_start=physical+n//p+1,
            production_warm_interval_claim=False),
        exact_changes=dict(interior_lazy_BF=interior,canonical_final_GS_pairs=final,pointwise_canonicalizers=p,
            final_operand_canonicalizers=p,upper_normalizers=final,IO_twist_multipliers_removed=2*p,
            net_standalone_multiplier_removal=2*p-final,IO_root_tables_removed=2,
            CT_reduction_change='one u pre-correction; both canonical output corrections removed; output<2P',
            GS_reduction_change='fold sum and difference modulo2P using29-bit temporaries; no arbitrary GS subtraction removal credited',
            small_FIFO_mapping='DEPTH<=32 explicit register chain; deeper frozen synchronous FIFO',
            fault_policy='current pending is diagnostic; origin edge may advance; registered aggregate/controller faults stop next sampling edge'),
        omitted=list(OMITTED),full_N_numeric_NTT_performed=False,warm_control_qualified=False,physical_fit_qualified=False)


def small_numeric_square(values,p=16,field=0):
    """Literal lazy physical stage replay, local numeric N<=256 ONLY.

    Uses scalar cell oracle and emitted root-address contract; direct
    schoolbook convolution remains the independent test/oracle below.
    """
    from .lazy28_butterfly_v1 import butterfly
    n=len(values)
    if n>256:raise ValueError('P16C_LOCAL_NUMERIC_N256_LIMIT')
    prime=FIELDS[field][0]
    if not all(type(value) is int and 0<=value<prime for value in values):raise ValueError('P16C_CANONICAL_INPUT')
    def run(inputs,inverse):
        plan=merged.topology(n,p,inverse=inverse);schedule=merged.schedule
        lanes=list(range(plan['pw'])) if inverse else list(range(plan['aw']-1,plan['aw']-plan['pw']-1,-1))
        times=list(range(plan['pw'],plan['aw'])) if inverse else list(range(plan['aw']-plan['pw']))
        frames=[[schedule.Token(schedule.index_of(row,lane,lanes,times),inputs[schedule.index_of(row,lane,lanes,times)])
                 for lane in range(p)] for row in range(n//p)]
        for spec in plan['stages']:
            if spec['shuffle_depth_per_buffer']:
                frames=schedule.commutator(frames,spec['commutator_lane_position'],spec['shuffle_depth_per_buffer'])
            final=inverse and spec['stage']==plan['aw']-1
            for row,frame in enumerate(frames):
                address=merged.root_address(plan,spec['stage'],row)
                for k,(lo,hi) in enumerate(spec['pairs']):
                    a,b=frame[lo],frame[hi]
                    root=merged.root_word(plan,spec['stage'],spec['root_stream_for_pair'][k],address,field,
                                          normalized_final=final)
                    if final:
                        u,v=a.value%prime,b.value%prime
                        scale=merged.math.normalization_constant(n,merged.math.FIELDS[field])
                        y0=(u+v)%prime*scale*pow(1<<32,-1,prime)%prime
                        y1=(u-v)%prime*root*pow(1<<32,-1,prime)%prime
                    else:y0,y1=butterfly(a.value,b.value,root,prime,inverse)
                    if not (0<=y0<2*prime and 0<=y1<2*prime):raise AssertionError('P16C_LAZY_RANGE')
                    frame[lo],frame[hi]=schedule.Token(a.index,y0),schedule.Token(b.index,y1)
        frames=[[frame[wire] for wire in plan['terminal_wire']] for frame in frames]
        result=[0]*n
        for frame in frames:
            for token in frame:result[token.index]=token.value
        return result
    forward=run(values,False)
    squared=[(value%prime)**2*pow(1<<32,-1,prime)%prime for value in forward]
    return run(squared,True)


def prepare(destination,*,n=65536,p=16,field=0,allow_full_constants=False):
    source_guard();destination=Path(destination).resolve()
    if destination.exists():raise ValueError('P16C_FRESH_OUTPUT')
    b=compile_probe(n,p,field,allow_full_constants=allow_full_constants)
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE '+DEVICE,
         'set_global_assignment -name TOP_LEVEL_ENTITY '+b['top'],
         'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
         'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4','set_global_assignment -name SEED 1',
         'set_global_assignment -name SDC_FILE probe.sdc']
    qsf+=['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in b['files']]
    qsf+=['set_parameter -name AW '+str(b['geometry']['aw']),'set_parameter -name CONTEXTS 1']
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to {'+pin+'}' for pin in PORTS]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n','probe.sdc':SDC,'run.tcl':RUN_TCL}
    prepdeps=b['source_dependencies']+['reference/stream27_p16c_physical_probe_v1.py',
        'reference/merged_stream27_root_compile_v1.py','reference/merged_stream27_model_v1.py',
        'reference/merged_negacyclic27_model.py','reference/stream_ntt_schedule.py',
        'reference/stream_ntt_model.py','reference/stream27_field_physical_probe_v1.py',
        'reference/lazy28_butterfly_v1.py','tests/test_stream27_p16c_physical_probe_v1.py']+list(BRIEFS)
    manifest=dict(status='prepared_provisional_P16C_not_executed',target='stream27_p16c_aw'+str(b['geometry']['aw'])+'_p'+str(p)+'_f'+str(field)+'_v1',
        top=b['top'],edition='pro',device=DEVICE,compile_processors=4,seed=1,clock_period_ns=10,
        address_width=b['geometry']['aw'],bitstream_generation=False,allowed_stages=['syn','fit','sta'],
        core_parameters=None,raw_multiplier_parameters=None,field_parameters=None,
        source_sha256={name:sha(text.encode()) for name,text in b['files'].items()},
        control_sha256={name:sha(text.encode()) for name,text in controls.items()},
        preparation_source_sha256={name:sha((ROOT/name).read_bytes()) for name in prepdeps},
        provisional_physical_probe=True,probe_geometry=b['geometry'],resource_basis=b['resource_basis'],
        rom_ledger=b['root_ledger'],calendar=b['calendar'],exact_changes=b['exact_changes'],omitted=b['omitted'],
        full_N_numeric_NTT_performed=False,warm_control_qualified=False,physical_fit_qualified=False,
        promotion='Datapath-only source exploration. LeanBF/finalGS cell composition, correctness, omitted blocks and audited clock remain gated.')
    payload={**{'rtl/'+name:text for name,text in b['files'].items()},**controls,'manifest.json':json.dumps(manifest,indent=2)+'\n'}
    project=destination/'project';project.mkdir(parents=True)
    for name,text in payload.items():
        path=project/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    closure={name:sha((project/name).read_bytes()) for name in payload}
    receipt=dict(status='prepared_not_dispatched',project_manifest_sha256=closure['manifest.json'],
        project_input_sha256=closure,content_addressed_snapshot_sha256=sha(json.dumps(closure,sort_keys=True,separators=(',',':')).encode()),
        geometry=b['geometry'],resource_basis=b['resource_basis'],calendar=b['calendar'],exact_changes=b['exact_changes'],
        full_N_numeric_NTT_performed=False,provisional_physical_probe=True,requested_vendor_sequence=['syn','fit','sta'],
        period_ns=10,seed=1,omitted=b['omitted'],dispatch_owner='Main only; preparer never dispatches',
        required_native_gate='Warning-fatal verilator --lint-only -Wall exact sources; boundedAW6/P16 reset/cancel/dense square gate; no fullN local numeric NTT')
    (destination/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    with tarfile.open(destination/'source.tar.gz','x:gz') as archive:
        for name in sorted(payload):archive.add(project/name,arcname='project/'+name,recursive=False)
        archive.add(destination/'preparation.json',arcname='preparation.json',recursive=False)
    verify_project(project);return receipt


def prepare_small_gate(destination):
    """Portable exact-source lint-first AW6 field gate; NEVER execute HDL."""
    receipt=prepare(destination,n=64,p=16,field=0)
    destination=Path(destination).resolve();project=destination/'project'
    bench='rtl/tb/stream27_p16c_aw6_v1.cpp';bench_text=(ROOT/bench).read_text()
    (destination/'stream27_p16c_aw6_v1.cpp').write_text(bench_text)
    manifest=json.loads((project/'manifest.json').read_text())
    sources=['project/rtl/'+name for name in manifest['source_sha256']]
    # Explicit argv arrays are data for main's native dispatcher, not shell
    # dispatch commands. Both stages are warning-fatal and share source flags.
    flags=['--top-module',manifest['top'],'-Wall']
    lint=['verilator','--lint-only',*flags,*sources]
    build=['verilator','--cc','--exe','--build',*flags,'-j','2','--Mdir','obj_dir',
           '-CFLAGS','-std=c++17 -O2',*sources,'stream27_p16c_aw6_v1.cpp']
    gate=dict(status='prepared_source_only_not_executed',top=manifest['top'],n=64,p=16,field=0,
        stages=[dict(kind='lint',argv=lint,warning_fatal=True),dict(kind='build',argv=build,warning_fatal=True),
                dict(kind='probe',argv=['obj_dir/V'+manifest['top']],expected_prefix='P16C_AW6_PASS')],
        maximum_probe_edges=30000,planned_probe_edges=28583,timeout_seconds=600,
        benchmark_sha256=sha(bench_text.encode()),project_manifest_sha256=receipt['project_manifest_sha256'],
        evidence_class='source-only bounded native preparation; no dispatch/native result',
        coverage=['direct schoolbook all physical rows','dense frames','generation cancel each edge0..90',
                  'disable each edge0..90','reset each edge0..90 including heldstart','registered range faults row0..3',
                  'busy start ignored, latched generation, physical done even canceled'],
        source_dependency_sha256={bench:sha(bench_text.encode())},
        dispatch_owner='Main only; finite queue admission/host policy still required')
    (destination/'native-gate.json').write_text(json.dumps(gate,indent=2)+'\n')
    with tarfile.open(destination/'native-source.tar.gz','x:gz') as archive:
        for path in sorted(project.rglob('*')):
            if path.is_file():archive.add(path,arcname=str(path.relative_to(destination)),recursive=False)
        for name in ('native-gate.json','stream27_p16c_aw6_v1.cpp','preparation.json'):
            archive.add(destination/name,arcname=name,recursive=False)
    return gate


def verify_project(project):
    project=Path(project).resolve();m=json.loads((project/'manifest.json').read_text())
    expected={'manifest.json',*m['control_sha256'],*('rtl/'+name for name in m['source_sha256'])}
    if expected!={str(p.relative_to(project)) for p in project.rglob('*') if p.is_file()}:
        raise ValueError('P16C_PROJECT_CLOSURE')
    for path,pin in {**m['control_sha256'],**{'rtl/'+k:v for k,v in m['source_sha256'].items()}}.items():
        if sha((project/path).read_bytes())!=pin:raise ValueError('P16C_PROJECT_DRIFT:'+path)
    for name in m['source_sha256']:
        if '$readmem' in (project/'rtl'/name).read_text():raise ValueError('P16C_EXTERNAL_ROM_ASSET')
    if m['warm_control_qualified'] or m['physical_fit_qualified'] or not m['provisional_physical_probe']:
        raise ValueError('P16C_EVIDENCE_CLASS')
    return dict(status='passed_source_closure_only',sources=len(m['source_sha256']),top=m['top'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    parser.add_argument('--n',type=int,default=65536);parser.add_argument('--p',type=int,choices=(8,16),default=16)
    parser.add_argument('--field',type=int,choices=(0,1,2),default=0);parser.add_argument('--full-constant-roms',action='store_true')
    args=parser.parse_args();print(json.dumps(prepare(args.destination,n=args.n,p=args.p,field=args.field,allow_full_constants=args.full_constant_roms),indent=2))
