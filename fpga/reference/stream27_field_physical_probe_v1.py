"""B20261001P/P2 source-only physical probe; NEVER dispatch or execute HDL.

Full-size modular-power ROM constants are allowed explicitly. No full-N
numeric NTT is performed here. The probe omits warm ownership and corrections;
it cannot qualify the complete stream27-blockcarry field or its16660 interval.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

from .stream27_field_compile import compile_transform
from .stream27_field_plan import resource_plan
from .stream_ntt_model import FIELDS,bit_reverse

DEVICE='10AX115N4F40E3SG'
BRIEF='docs/briefs/2026-10-01-fit-plan.md'
OMITTED=(
    'Digit and signed c0/c1 reducers: input is already a canonical field residue.',
    'Both correction transforms, correction additions, four-context term producer and seed/factor ROMs.',
    'Warm two-owner/epoch controller, late correction admission, cache ownership and overlap.',
    'Shared CRT, double, block carry, digit readback and host/base-change canonicalization.',
    'Production warm throughput and full-size numerical correctness qualification.')
PORTS=('rst_n','start','generation_in[*]','live_generation[*]','context_enabled',
       'data_in[*]','ready','busy','done','error','fault_pending','out_slot_valid',
       'out_frame_start','out_eligible','generation_out[*]','data_out[*]',
       'output_row[*]','cycles[*]')
RUN_TCL='''# Provisional physical probe only; no assembler/programmer.
load_package project
load_package flow
if {[llength $quartus(args)] != 1 || [lindex $quartus(args) 0] ni {syn fit}} {
    error "Usage: quartus_sh -t run.tcl syn|fit"
}
set stage [lindex $quartus(args) 0]
cd [file dirname [file normalize [info script]]]
project_open probe
if {[catch {
    execute_module -tool syn
    if {$stage eq "fit"} {
        execute_module -tool fit
        execute_module -tool sta
    }
} failure]} {
    project_close
    error $failure
}
project_close
'''
SDC='''# Exploratory virtual-I/O component probe, not a board clock constraint.
create_clock -name kernel_clk -period 10 [get_ports {clk}]
derive_clock_uncertainty
# Reset release and virtual external I/O timing are outside this probe.
set_false_path -from [get_ports {rst_n}]
'''


def sha(raw):return hashlib.sha256(raw).hexdigest()


def embedded_rom(module,words,width):
    """Exact initialized memory with the frozen root helper's read calendar.

    The constants live in compiled SV, not an unpinned external HEX_FILE. The
    initialized array and its read register have no reset. Only row counters
    reset; row0 uses its static bypass. Actual RAM inference remains measured.
    """
    period=len(words)
    if period<2 or period&(period-1):raise ValueError('P2_ROM_PERIOD')
    digits=(width+3)//4
    lines=[f'module {module} (',
           '  input logic clk,rst_n,in_slot_valid,frame_start,',
           f'  output logic [{width-1}:0] root);',
           f'  localparam int ADDR_W={period.bit_length()-1};',
           f'  (* ramstyle = "M20K" *) logic [{width-1}:0] roots[0:{period-1}];',
           '  logic [ADDR_W-1:0] current_row,following_row;',
           f'  logic [{width-1}:0] prefetched;',
           "  assign following_row=frame_start ? ADDR_W'(1) : current_row+ADDR_W'(1);",
           f"  assign root=frame_start ? {width}'h{words[0]:0{digits}x} : prefetched;",
           '  initial begin']
    lines += [f"    roots[{i}]={width}'h{word:0{digits}x};" for i,word in enumerate(words)]
    lines += ['  end','  always_ff @(posedge clk)',
              '    if(rst_n && in_slot_valid)prefetched<=roots[following_row];',
              '  always_ff @(posedge clk or negedge rst_n)begin',
              "    if(!rst_n)current_row<='0;",
              '    else if(in_slot_valid)current_row<=following_row;',
              '  end','endmodule\n']
    return '\n'.join(lines)


def _top(aw,field,forward,inverse,twist_rom,untwist_rom):
    rows=1<<(aw-3);p=FIELDS[field][0];q=(2-p)%(1<<32)
    name=f'genefer_stream27_field_physical_probe_aw{aw}_p8_f{field}_v1'
    source=f'''// B20261001P/P2 PROVISIONAL physical datapath probe, not warm-field RTL.
// Start supplies row0, followed by exactly T-1 dense canonical residue rows.
// One frame drains completely before another starts; busy starts are ignored.
// Done means physical drain, including canceled rows; not a PRP/carry result.
module {name} #(parameter int AW={aw}) (
  input logic clk,rst_n,start,context_enabled,
  input logic [7:0] generation_in,live_generation,
  input logic [215:0] data_in,
  output logic ready,busy,done,error,fault_pending,
  output logic out_slot_valid,out_frame_start,out_eligible,
  output logic [7:0] generation_out,
  output logic [215:0] data_out,
  output logic [{aw-4}:0] output_row,
  output logic [31:0] cycles);
  localparam int T={rows},ROW_W={aw-3},COUNT_W={aw-2};
  logic [COUNT_W-1:0] remaining_input;
  logic [7:0] active_generation;
  logic controller_error;
  logic [4:0] child_error,child_pending;
  logic [7:0] range_lanes;
  wire stop=controller_error || (|child_error);
  wire request_slot=(ready && start) || (busy && remaining_input!=0);
  wire range_bad=request_slot && (|range_lanes);
  wire accepted=rst_n && request_slot && !stop && !range_bad;
  wire accepted_start=accepted && !busy;
  wire [7:0] accepted_generation=accepted_start ? generation_in : active_generation;
  wire [215:0] twist_roots,untwist_roots,twisted,fwd_data,squared,inv_data,final_data;
  wire twist_slot,twist_start,fwd_slot,fwd_start,square_slot,square_start;
  wire inv_slot,inv_start,final_slot,final_start;
  wire [7:0] twist_generation,fwd_generation,square_generation,inv_generation,final_generation;
  assign ready=rst_n && !busy && !stop;
  assign error=stop;
  assign fault_pending=stop || (|child_pending) || range_bad;
  for(genvar lane=0;lane<8;lane=lane+1)begin : input_range
    assign range_lanes[lane]={{5'b0,data_in[lane*27+:27]}}>=32'd{p};
  end
  {twist_rom} twist_roots_source (
    .clk,.rst_n,.in_slot_valid(accepted),.frame_start(accepted_start),.root(twist_roots));
  genefer_stream27_mul8_v2 #(.P(32'd{p}),.Q(32'd{q})) twist (
    .clk,.rst_n,.in_slot_valid(accepted),.frame_start(accepted_start),.quarantine(stop),
    .generation_in(accepted_generation),.lhs(data_in),.rhs(twist_roots),
    .out_slot_valid(twist_slot),.out_frame_start(twist_start),.out_error(child_error[0]),
    .fault_pending(child_pending[0]),.generation_out(twist_generation),.result(twisted));
  {forward} forward_transform (
    .clk,.rst_n,.in_slot_valid(twist_slot),.frame_start(twist_start),.quarantine(stop),
    .context_enabled,.generation_in(twist_generation),.live_generation,.data_in(twisted),
    .out_slot_valid(fwd_slot),.out_frame_start(fwd_start),.out_eligible(),.out_error(child_error[1]),
    .fault_pending(child_pending[1]),.generation_out(fwd_generation),.data_out(fwd_data));
  genefer_stream27_mul8_v2 #(.P(32'd{p}),.Q(32'd{q})) pointwise_square (
    .clk,.rst_n,.in_slot_valid(fwd_slot),.frame_start(fwd_start),.quarantine(stop),
    .generation_in(fwd_generation),.lhs(fwd_data),.rhs(fwd_data),
    .out_slot_valid(square_slot),.out_frame_start(square_start),.out_error(child_error[2]),
    .fault_pending(child_pending[2]),.generation_out(square_generation),.result(squared));
  {inverse} inverse_transform (
    .clk,.rst_n,.in_slot_valid(square_slot),.frame_start(square_start),.quarantine(stop),
    .context_enabled,.generation_in(square_generation),.live_generation,.data_in(squared),
    .out_slot_valid(inv_slot),.out_frame_start(inv_start),.out_eligible(),.out_error(child_error[3]),
    .fault_pending(child_pending[3]),.generation_out(inv_generation),.data_out(inv_data));
  {untwist_rom} untwist_roots_source (
    .clk,.rst_n,.in_slot_valid(inv_slot),.frame_start(inv_start),.root(untwist_roots));
  genefer_stream27_mul8_v2 #(.P(32'd{p}),.Q(32'd{q})) fused_untwist_normalize (
    .clk,.rst_n,.in_slot_valid(inv_slot),.frame_start(inv_start),.quarantine(stop),
    .generation_in(inv_generation),.lhs(inv_data),.rhs(untwist_roots),
    .out_slot_valid(final_slot),.out_frame_start(final_start),.out_error(child_error[4]),
    .fault_pending(child_pending[4]),.generation_out(final_generation),.result(final_data));
  assign out_slot_valid=final_slot && !stop;
  assign out_frame_start=final_start && out_slot_valid;
  assign out_eligible=out_slot_valid && context_enabled && final_generation==live_generation && !fault_pending;
  assign generation_out=final_generation;assign data_out=final_data;
  always_ff @(posedge clk or negedge rst_n)begin
    if(!rst_n)begin
      busy<=0;done<=0;controller_error<=0;remaining_input<=0;output_row<=0;cycles<=0;
    end else begin
      done<=0;
      if(range_bad || (|child_pending))controller_error<=1;
      if(busy)cycles<=cycles+32'd1;
      if(accepted)begin
        if(accepted_start)begin
          busy<=1;remaining_input<=COUNT_W'(T-1);active_generation<=generation_in;
          output_row<=0;cycles<=0;
        end else remaining_input<=remaining_input-COUNT_W'(1);
      end
      if(final_slot && !stop && !fault_pending)begin
        if(output_row==ROW_W'(T-1))begin busy<=0;done<=1;end
        else output_row<=output_row+ROW_W'(1);
      end
    end
  end
  // synthesis translate_off
  initial if(AW!={aw})$fatal(1,"P2_GENERATED_AW_FIXED");
  // synthesis translate_on
endmodule
'''
    return name,source


def compile_probe(n=32,field=0,*,allow_full_constants=False):
    if n>256 and not allow_full_constants:raise ValueError('P2_FULL_ROM_CONSTANTS_REQUIRE_EXPLICIT_AUTHORITY')
    aw=n.bit_length()-1
    if n!=(1<<aw) or not 5<=aw<=16 or field not in (0,1,2):raise ValueError('P2_GEOMETRY')
    files={};rom_sources=[];rom_ledger=[];deps=set()
    transforms=[]
    for inverse in (False,True):
        result=compile_transform(n,field,inverse=inverse,emit_numeric_roms=True,
                                 allow_large_root_tables=allow_full_constants)
        source=result['source'];transforms.append(result);deps.update(result['source_dependencies'])
        for item in result['rom_ledger']:
            if not item['file']:continue
            words=tuple(int(x,16) for x in result['rom_files'][item['file']].splitlines())
            module=item['file'].removesuffix('.hex')+'_embedded_p2_v1'
            rom_sources.append(embedded_rom(module,words,27))
            pattern=r'genefer_stream27_root_rom_prefetch #\(\.PERIOD\('+str(item['period'])+r'\),\s*'+r"\.FIRST_ROOT\(27'd"+str(item['first_R_root'])+r'\),\.HEX_FILE\("'+re.escape(item['file'])+r'"\)\)'
            source,count=re.subn(pattern,module,source)
            if count!=1:raise ValueError('P2_ROOT_SOURCE_ANCHOR')
            rom_ledger.append(dict(module=module,period=len(words),width=27,words_sha256=sha(result['rom_files'][item['file']].encode()),
                                   parent_hex=item['file'],direction='inverse' if inverse else 'forward'))
        files[result['module']+'.sv']=source
    prime,generator=FIELDS[field];psi=pow(generator,(prime-1)//(2*n),prime);rows=n//8
    rootnames=[]
    for inverse in (False,True):
        name=f'genefer_stream27_p2_{"untwist" if inverse else "twist"}_aw{aw}_f{field}_rom_v1'
        words=[]
        for row in range(rows):
            values=[]
            for lane in range(8):
                index=bit_reverse(lane,3)*rows+row
                value=(pow(psi,-index,prime)*pow(n,-1,prime)*(1<<64) if inverse else
                       pow(psi,index,prime)*(1<<32))%prime
                values.append(value)
            words.append(sum(value<<(lane*27) for lane,value in enumerate(values)))
        rom_sources.append(embedded_rom(name,words,216));rootnames.append(name)
        rom_ledger.append(dict(module=name,period=rows,width=216,
            words_sha256=sha(''.join(f'{word:054x}\n' for word in words).encode()),
            direction='fused_untwist_normalize' if inverse else 'twist'))
    rom_file=f'genefer_stream27_p2_initialized_roms_aw{aw}_f{field}_v1.sv'
    files[rom_file]='// Exact modular-power ROM constants; no numeric NTT performed.\n'+'\n'.join(rom_sources)
    top,source=_top(aw,field,transforms[0]['module'],transforms[1]['module'],*rootnames)
    files[top+'.sv']=source
    deps.add('rtl/kernel/genefer_stream27_row_arithmetic_v2.sv')
    root=Path(__file__).resolve().parents[1]
    compiled={Path(path).name:(root/path).read_text() for path in sorted(deps)}
    if len(compiled)!=len(deps):raise ValueError('P2_SOURCE_BASENAME_COLLISION')
    compiled.update(files)
    plan=resource_plan(n);included=('forward_inverse_butterflies','twist_square_fused_untwist_multipliers','shallow_FIFO_MLAB_source_shape')
    proxy=sum(plan['components'][key]['ALM_planning_proxy'] for key in included)
    first=transforms[0]['topology']['first_output_edge']
    # Each transform reports its last registered BF output, not its next
    # consumer edge. Preserve that extra edge at both transform boundaries.
    physical=14+first+transforms[1]['topology']['first_output_edge']
    return dict(top=top,files=compiled,source_dependencies=sorted(deps),rom_ledger=rom_ledger,
        geometry=dict(n=n,aw=aw,p=8,rows=rows,field_index=field,prime=prime,generation_bits=8,payload_bits=1,contexts=1),
        resource_basis=dict(included_components={key:plan['components'][key] for key in included},
            included_noncontrol_ALM_proxy=proxy,comparison_110_percent_proxy=(proxy*110+99)//100,
            full_field_noncontrol_ALM_proxy=plan['per_field_ALM_planning_proxy'],
            control_reserve_allocation='unallocated; minimal probe controller is measured, not a complete-field allowance',
            M20K_proxy=plan['memory']['literal_tagged_per_FIFO_delay_M20K']+plan['memory']['roots_M20K']+plan['memory']['twist_untwist_M20K'],
            delay_M20K_proxy=plan['memory']['literal_tagged_per_FIFO_delay_M20K'],
            root_M20K_proxy=plan['memory']['roots_M20K'],IO_root_M20K_proxy=plan['memory']['twist_untwist_M20K'],
            DSP_proxy=2*aw*4+24,measured=False,
            caution='Constant PAYLOAD/owner bits and equal root streams may optimize; fitted/inferred memories determine real shapes.'),
        calendar=dict(first_input_accept=0,first_physical_output=physical-1,first_terminal_sample=physical,
            last_terminal_sample=physical+rows-1,next_nonoverlap_start=physical+rows,
            production_warm_interval_claim=False),omitted=list(OMITTED),
        full_N_numeric_NTT_performed=False,warm_control_qualified=False,physical_fit_qualified=False)


def prepare(destination,*,n=65536,field=0,allow_full_constants=False):
    root=Path(__file__).resolve().parents[1]
    if (root/'docs/briefs/PAUSE').exists():raise ValueError('brief PAUSE')
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('P2_FRESH_OUTPUT')
    bundle=compile_probe(n,field,allow_full_constants=allow_full_constants)
    source_pins={name:sha(content.encode()) for name,content in bundle['files'].items()}
    qsf=['set_global_assignment -name FAMILY "Arria 10"',
         'set_global_assignment -name DEVICE '+DEVICE,
         'set_global_assignment -name TOP_LEVEL_ENTITY '+bundle['top'],
         'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
         'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4',
         'set_global_assignment -name SEED 1','set_global_assignment -name SDC_FILE probe.sdc']
    qsf+=['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in bundle['files']]
    qsf+=['set_parameter -name AW '+str(bundle['geometry']['aw'])]
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to {'+pin+'}' for pin in PORTS]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n',
              'probe.sdc':SDC,'run.tcl':RUN_TCL}
    preparation_deps=bundle['source_dependencies']+[
        'reference/stream27_field_physical_probe_v1.py','reference/stream27_field_compile.py',
        'reference/stream27_field_plan.py','reference/stream_ntt_model.py','reference/stream_ntt_schedule.py',
        'tests/test_stream27_field_physical_probe_v1.py',BRIEF]
    provenance={name:sha((root/name).read_bytes()) for name in preparation_deps}
    manifest=dict(status='prepared_provisional_physical_probe_not_executed',
        target='stream27_field_physical_probe_aw'+str(bundle['geometry']['aw'])+'_p8_f'+str(field)+'_v1',
        top=bundle['top'],edition='pro',device=DEVICE,compile_processors=4,seed=1,clock_period_ns=10,
        address_width=bundle['geometry']['aw'],bitstream_generation=False,allowed_stages=['syn','fit','sta'],
        core_parameters=None,raw_multiplier_parameters=None,field_parameters=None,
        source_sha256=source_pins,control_sha256={name:sha(text.encode()) for name,text in controls.items()},
        preparation_source_sha256=provenance,provisional_physical_probe=True,
        probe_geometry=bundle['geometry'],resource_basis=bundle['resource_basis'],rom_ledger=bundle['rom_ledger'],
        calendar=bundle['calendar'],omitted=bundle['omitted'],full_N_numeric_NTT_performed=False,
        warm_control_qualified=False,physical_fit_qualified=False,
        promotion='Not complete S3 qualification: provisional datapath-only area/clock; correctness, omitted resources and control remain separate gates.')
    files={**{'rtl/'+name:text for name,text in bundle['files'].items()},**controls,
           'manifest.json':json.dumps(manifest,indent=2)+'\n'}
    project=destination/'project';project.mkdir(parents=True)
    for name,text in files.items():
        path=project/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    closure={name:sha((project/name).read_bytes()) for name in files}
    snapshot_sha=sha(json.dumps(closure,sort_keys=True,separators=(',',':')).encode())
    admission=dict(status='passed',evidence_class='bounded_source_preparation_only_provisional_physical',
        provisional_physical_probe=True,warm_control_qualified=False,source_hashes_rechecked=True,
        source_sha256={'rtl/kernel/'+name:digest for name,digest in source_pins.items()},
        geometry=bundle['geometry'],brief_sha256=provenance[BRIEF],
        limits=['No HDL/native/cloud action.','Only initialized modular-power constants, no full-N numeric NTT.',
                'Probe omits correction/control/shared-core blocks; no correctness, clock or throughput promotion.'])
    (destination/'source-admission.json').write_text(json.dumps(admission,indent=2)+'\n')
    receipt=dict(status='prepared_not_dispatched',project_manifest_sha256=closure['manifest.json'],
        project_input_sha256=closure,content_addressed_snapshot_sha256=snapshot_sha,
        source_admission_sha256=sha((destination/'source-admission.json').read_bytes()),
        geometry=bundle['geometry'],resource_basis=bundle['resource_basis'],calendar=bundle['calendar'],
        full_N_numeric_NTT_performed=False,provisional_physical_probe=True,
        requested_vendor_sequence=['syn','fit','sta'],period_ns=10,seed=1,omitted=bundle['omitted'],
        dispatch_owner='Main only; no dispatch by source preparer.',
        per_block_collection=['forward_transform: BF/root/delay memories','inverse_transform: BF/root/delay memories',
            'twist and twist_roots_source','pointwise_square','fused_untwist_normalize and untwist_roots_source',
            'minimal single-frame sequencing and physical metadata'],
        caution='The110% proxy is a matched included-datapath diagnostic, not the complete-field acceptance threshold.')
    (destination/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    with tarfile.open(destination/'source.tar.gz','x:gz') as archive:
        for name in sorted(files):archive.add(project/name,arcname='project/'+name,recursive=False)
        for name in ('source-admission.json','preparation.json'):archive.add(destination/name,arcname=name,recursive=False)
    verify_project(project)
    return receipt


def verify_project(project):
    project=Path(project).resolve();m=json.loads((project/'manifest.json').read_text())
    expected={'manifest.json',*m['control_sha256'],*('rtl/'+name for name in m['source_sha256'])}
    actual={str(path.relative_to(project)) for path in project.rglob('*') if path.is_file()}
    if expected!=actual:raise ValueError('P2_PROJECT_CLOSURE')
    for name,digest in m['control_sha256'].items():
        if sha((project/name).read_bytes())!=digest:raise ValueError('P2_CONTROL_DRIFT: '+name)
    for name,digest in m['source_sha256'].items():
        if sha((project/'rtl'/name).read_bytes())!=digest:raise ValueError('P2_SOURCE_DRIFT: '+name)
    if not m['provisional_physical_probe'] or m['warm_control_qualified'] or m['physical_fit_qualified']:
        raise ValueError('P2_EVIDENCE_CLASS')
    if re.search(r'\$readmem[hb]',(project/'rtl'/next(name for name in m['source_sha256'] if 'initialized_roms' in name)).read_text()):
        raise ValueError('P2_EXTERNAL_ROM_ASSET')
    return dict(status='passed_source_closure_only',sources=len(m['source_sha256']),top=m['top'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    parser.add_argument('--full-constant-roms',action='store_true');args=parser.parse_args()
    receipt=prepare(args.destination,allow_full_constants=args.full_constant_roms)
    print(json.dumps({key:receipt[key] for key in ('status','project_manifest_sha256','geometry','calendar')},indent=2))
