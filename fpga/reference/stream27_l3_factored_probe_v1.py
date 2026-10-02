"""Matched four independent-input scalar cells; no whole-P16 area credit."""
import argparse
import json
from pathlib import Path
from fpga.reference import stream27_l3_factored_native_v1 as n
from fpga.cloud import plain_fit_v5 as fit
from fpga.tools import fit_dispatch,fit_submit
s=n.s;ROOT=s.ROOT
TOP='genefer_stream27_l3_factored_probe_v1'
WRAPPER='rtl/kernel/'+TOP+'.sv'
TEXT='''// Sizing-only wrapper: independent operand/valid ports forbid product sharing.
// Input FF adds one wrapper edge, NOT a change to the k->k+3 leaf ABI.
module genefer_stream27_l3_factored_probe_v1 #(
 parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
)(input logic clk,rst_n,input logic [3:0] in_valid,
 input logic [127:0] lhs,rhs,
 output logic [3:0] out_valid,output logic [127:0] result);
 logic [127:0] lhs_q,rhs_q;
 logic [3:0] valid_q;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin lhs_q<=0;rhs_q<=0;valid_q<=0;end
  else begin lhs_q<=lhs;rhs_q<=rhs;valid_q<=in_valid;end
 end
 genefer_stream27_montgomery_factored_v1 #(.P(P),.Q(Q)) new_canonical(
  .clk,.rst_n,.in_valid(valid_q[0]),.lhs(lhs_q[0+:32]),.rhs(rhs_q[0+:32]),.out_valid(out_valid[0]),.result(result[0+:32]));
 genefer_montgomery_mul27_sparse_pipe #(.P(P),.Q(Q)) frozen_canonical(
  .clk,.rst_n,.in_valid(valid_q[1]),.lhs(lhs_q[32+:32]),.rhs(rhs_q[32+:32]),.out_valid(out_valid[1]),.result(result[32+:32]));
 genefer_stream27_montgomery28x27_factored_v1 #(.P(P),.Q(Q)) new_lazy(
  .clk,.rst_n,.in_valid(valid_q[2]),.lhs(lhs_q[64+:28]),.rhs(rhs_q[64+:27]),.out_valid(out_valid[2]),.result(result[64+:32]));
 genefer_montgomery_mul28x27_sparse_pipe_v2 #(.P(P),.Q(Q)) frozen_lazy(
  .clk,.rst_n,.in_valid(valid_q[3]),.lhs(lhs_q[96+:28]),.rhs(rhs_q[96+:27]),.out_valid(out_valid[3]),.result(result[96+:32]));
endmodule
'''
def gates():
    refs=[]
    for field in range(3):
        identifier=f'stream27-l3-factored-f{field}-normal-q1-v1'
        path=ROOT/'queue/evidence'/identifier/'gate-receipt.json'
        raw=path.read_bytes();value=json.loads(raw)
        s.need(value['id']==identifier and value['status']=='PASS_expected_contracts','L3_REAL_NATIVE_PREREQUISITE')
        v=value['steps'][0]['validation']
        s.need(v['latency']==3 and v['II']==1 and v['outputs']==4 and v['independent_result_checks']==67700,'L3_EXACT_NATIVE_CALENDAR')
        refs.append(dict(path=str(path),sha256=s.sha(raw),fields=dict(id=identifier,status='PASS_expected_contracts')))
    return refs
def prepare(destination,p=104857601):
    n.verify_pins();s.need(p in n.HIGH,'L3_PROBE_FIELD');gates()
    s.need((ROOT/WRAPPER).read_text()==TEXT,'L3_PROBE_LITERAL')
    destination=Path(destination).resolve();s.need(destination.is_relative_to(ROOT) and not destination.exists(),'L3_PROBE_FRESH')
    rtl=destination/'rtl';rtl.mkdir(parents=True)
    names=(WRAPPER,s.RTL,'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv','rtl/kernel/genefer_montgomery_mul28x27_sparse_pipe_v2.sv')
    sources={Path(name).name:(ROOT/name).read_bytes() for name in names}
    for name,raw in sources.items():
        with (rtl/name).open('xb') as f:f.write(raw)
    qsf='''set_global_assignment -name FAMILY "Arria 10"
set_global_assignment -name DEVICE 10AX115N4F40E3SG
set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files
set_global_assignment -name NUM_PARALLEL_PROCESSORS 4
set_global_assignment -name SEED 1
set_global_assignment -name SDC_FILE probe.sdc
set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on
'''+f'set_global_assignment -name TOP_LEVEL_ENTITY {TOP}\n'
    qsf+=''.join(f'set_global_assignment -name SYSTEMVERILOG_FILE rtl/{name}\n' for name in sources)
    qsf+=f'set_parameter -name P {p}\nset_parameter -name Q {(2-p)%(1<<32)}\n'
    qsf+=''.join(f'set_instance_assignment -name VIRTUAL_PIN ON -to {{{name}}}\n' for name in ('rst_n','in_valid[*]','lhs[*]','rhs[*]','out_valid[*]','result[*]'))
    controls={'probe.qsf':qsf,'probe.qpf':'QUARTUS_VERSION = "26.1"\nPROJECT_REVISION = "probe"\n',
      'probe.sdc':'# Virtual-I/O scalar sizing only; reset release not signed off.\ncreate_clock -name kernel_clk -period 10 [get_ports {clk}]\nderive_clock_uncertainty\nset_false_path -from [get_ports {rst_n}]\n',
      'run.tcl':fit.FULL_TCL}
    for name,text in controls.items():
        with (destination/name).open('x') as f:f.write(text)
    manifest=dict(schema='stream27-L3-matched-scalar-sizing-v1',status='prepared_not_fitted',top=TOP,
      target='stream27_L3_four_independent_cells_f0',edition='pro',device='10AX115N4F40E3SG',compile_processors=4,
      bitstream_generation=False,allowed_stages=['syn','fit','sta'],clock_period_ns=10,seed=1,
      core_parameters=dict(P=p,Q=(2-p)%(1<<32)),source_sha256={name:s.sha(raw) for name,raw in sources.items()},
      control_sha256={name:s.sha(text.encode()) for name,text in controls.items()},intermediate_snapshots=True,
      cell_comparison=['new_canonical','frozen_canonical','new_lazy','frozen_lazy'],independent_input_sets=4,
      expected_variable_products_by_source=4,additional_DSP_by_source=0,leaf_latency=3,wrapper_input_delay=1,
      source_reduction=s.ledger(),native_prerequisites=gates(),
      scope='One canonical and one lazy cell versus both frozen leaves under matched physical context; no shared products. Read per-entity needed/final resources and internal setup/hold. No wholeP16 clock, area saving or mapping assumption.',promotion_allowed=False)
    n.dump(destination/'manifest.json',manifest)
    return fit_dispatch.snapshot(destination)
def submit(project):
    return fit_submit.submit(ROOT/'queue/standing-fits','stream27-l3-factored-cell-f0-v1',Path(project).resolve(),
      '10',1,dict(azure4=list('abcd'),aws6=list('ab')),'component_probe',dict(exemption='component_sizing_probe'),
      priority=50,requires=gates(),track='S',purpose='p16_diet')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write-wrapper',action='store_true');p.add_argument('--project',type=Path)
    p.add_argument('--submit',action='store_true');a=p.parse_args()
    if a.write_wrapper:
        s.need(not (ROOT/WRAPPER).exists(),'L3_PROBE_WRAPPER_FRESH')
        with (ROOT/WRAPPER).open('x') as f:f.write(TEXT)
    elif a.submit:print(json.dumps(submit(a.project),indent=2))
    else:print(json.dumps(prepare(a.project),indent=2))
