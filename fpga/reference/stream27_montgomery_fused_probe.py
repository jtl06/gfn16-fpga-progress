"""Matched independent frozen, normalized-factored and fused CT/GS butterflies."""
import argparse
import json
from pathlib import Path
from fpga.reference import stream27_montgomery_fused_native as n
from fpga.cloud import plain_fit_v5 as fit
from fpga.tools import fit_dispatch,fit_submit
ROOT=n.ROOT;need=n.need;sha=n.sha
OLD='rtl/kernel/genefer_ntt_lazy28_butterfly_v1.sv'
OLD_PIN='ade6280dd1dac0fe3049ac2860dea7bbc7db292b634368e12f557b63865aa00d'
NORMALIZED='rtl/kernel/genefer_stream27_factored_lazy28_butterfly_v1.sv'
TOP='genefer_stream27_l3_fused_probe_v1';WRAPPER='rtl/kernel/'+TOP+'.sv'
TOP2='genefer_stream27_l3_fused_sign_probe_v1';WRAPPER2='rtl/kernel/'+TOP2+'.sv'
TEXT='''// Independent input FF sets prevent sharing variable products between cells.
// Sizing-only E0 input register adds one edge; each butterfly still has E0->E5.
module genefer_stream27_l3_fused_probe_v1 #(
 parameter logic [31:0] P=32'd104857601,Q=32'd4190109697
)(input logic clk,rst_n,input logic [2:0] in_valid,gs,
 input logic [83:0] u,v,input logic [80:0] w,input logic [95:0] in_tag,
 output logic [2:0] out_valid,output logic [83:0] y0,y1,output logic [95:0] out_tag);
 logic [2:0] valid_q,gs_q;logic [83:0] u_q,v_q;logic [80:0] w_q;logic [95:0] tag_q;
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin valid_q<=0;gs_q<=0;u_q<=0;v_q<=0;w_q<=0;tag_q<=0;end
  else begin valid_q<=in_valid;gs_q<=gs;u_q<=u;v_q<=v;w_q<=w;tag_q<=in_tag;end
 end
 genefer_ntt_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(32)) frozen_butterfly(
  .clk,.rst_n,.in_valid(valid_q[0]),.gs(gs_q[0]),.u(u_q[0+:28]),.v(v_q[0+:28]),.w(w_q[0+:27]),
  .in_tag(tag_q[0+:32]),.out_valid(out_valid[0]),.y0(y0[0+:28]),.y1(y1[0+:28]),.out_tag(out_tag[0+:32]));
 genefer_stream27_factored_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(32)) factored_butterfly(
  .clk,.rst_n,.in_valid(valid_q[1]),.gs(gs_q[1]),.u(u_q[28+:28]),.v(v_q[28+:28]),.w(w_q[27+:27]),
  .in_tag(tag_q[32+:32]),.out_valid(out_valid[1]),.y0(y0[28+:28]),.y1(y1[28+:28]),.out_tag(out_tag[32+:32]));
 genefer_stream27_fused_lazy28_butterfly_v1 #(.P(P),.Q(Q),.TAG_W(32)) fused_butterfly(
  .clk,.rst_n,.in_valid(valid_q[2]),.gs(gs_q[2]),.u(u_q[56+:28]),.v(v_q[56+:28]),.w(w_q[54+:27]),
  .in_tag(tag_q[64+:32]),.out_valid(out_valid[2]),.y0(y0[56+:28]),.y1(y1[56+:28]),.out_tag(out_tag[64+:32]));
endmodule
'''
def normalized_source():
    old=(ROOT/OLD).read_text();need(sha(old.encode())==OLD_PIN,'P5_FROZEN_BFLY_PIN')
    changes=[('genefer_ntt_lazy28_butterfly_v1','genefer_stream27_factored_lazy28_butterfly_v1'),
      ('genefer_montgomery_mul28x27_sparse_pipe_v2','genefer_stream27_montgomery28x27_factored_v1')]
    result=old
    for before,after in changes:
        need(result.count(before)==1,'P5_NORMALIZED_UNIQUE_SITE');result=result.replace(before,after,1)
    reverse=result
    for before,after in reversed(changes):reverse=reverse.replace(after,before,1)
    need(reverse==old,'P5_NORMALIZED_BYTE_REVERSE')
    return result
def probe_text(variant=1):
    need(variant in (1,2),'P5_PROBE_VARIANT')
    return TEXT if variant==1 else TEXT.replace(TOP,TOP2).replace(n.TOP,n.TOP2)
def gates(variant=1):
    refs=[]
    for family in ('stream27-l3-factored','stream27-l3-fused' if variant==1 else 'stream27-l3-fused-sign'):
        for field in range(3):
            identifier=f'{family}-f{field}-normal-q1-v1';path=ROOT/'queue/evidence'/identifier/'gate-receipt.json'
            raw=path.read_bytes();value=json.loads(raw);v=value['steps'][0]['validation']
            need(value['id']==identifier and value['status']=='PASS_expected_contracts','P5_ACTUAL_NORMAL_GATE')
            need(v['latency']==(3 if family=='stream27-l3-factored' else 5) and v['II']==1,'P5_NATIVE_CALENDAR')
            refs.append(dict(path=str(path),sha256=sha(raw),fields=dict(id=identifier,status='PASS_expected_contracts')))
    return refs
def verify(variant=1):
    n.verify(variant);wrapper=WRAPPER if variant==1 else WRAPPER2
    need((ROOT/NORMALIZED).read_text()==normalized_source() and (ROOT/wrapper).read_text()==probe_text(variant),'P5_PROBE_EXACT_SOURCES')
def write_source(variant=1):
    wrapper=WRAPPER if variant==1 else WRAPPER2
    for name,text in ((NORMALIZED,normalized_source()),(wrapper,probe_text(variant))):
        if (ROOT/name).exists():
            need((ROOT/name).read_text()==text,'P5_FROZEN_PROBE_SOURCE');continue
        with (ROOT/name).open('x') as f:f.write(text)
    verify(variant)
def prepare(destination,p=104857601,variant=1):
    verify(variant);gates(variant);need(p in n.model.FIELDS,'P5_SIZING_FIELD')
    wrapper,leaf,top=(WRAPPER,n.RTL,TOP) if variant==1 else (WRAPPER2,n.RTL2,TOP2)
    destination=Path(destination).resolve();need(destination.is_relative_to(ROOT) and not destination.exists(),'P5_FRESH_PROBE')
    rtl=destination/'rtl';rtl.mkdir(parents=True)
    names=(wrapper,NORMALIZED,leaf,n.package_helper.s.RTL,OLD,'rtl/kernel/genefer_montgomery_mul28x27_sparse_pipe_v2.sv')
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
'''+f'set_global_assignment -name TOP_LEVEL_ENTITY {top}\n'
    qsf+=''.join(f'set_global_assignment -name SYSTEMVERILOG_FILE rtl/{name}\n' for name in sources)
    qsf+=f'set_parameter -name P {p}\nset_parameter -name Q {(2-p)%(1<<32)}\n'
    ports=('rst_n','in_valid[*]','gs[*]','u[*]','v[*]','w[*]','in_tag[*]','out_valid[*]','y0[*]','y1[*]','out_tag[*]')
    qsf+=''.join(f'set_instance_assignment -name VIRTUAL_PIN ON -to {{{port}}}\n' for port in ports)
    controls={'probe.qsf':qsf,'probe.qpf':'QUARTUS_VERSION = "26.1"\nPROJECT_REVISION = "probe"\n',
      'probe.sdc':'# Virtual-I/O scalar sizing; reset release not signed off.\ncreate_clock -name kernel_clk -period 10 [get_ports {clk}]\nderive_clock_uncertainty\nset_false_path -from [get_ports {rst_n}]\n',
      'run.tcl':fit.FULL_TCL}
    for name,text in controls.items():
        with (destination/name).open('x') as f:f.write(text)
    n.package_helper.dump(destination/'manifest.json',dict(schema='stream27-P5-matched-butterfly-sizing-v1',status='prepared_not_fitted',
      top=top,target='stream27_P5_three_independent_butterflies_f0',variant=variant,edition='pro',device='10AX115N4F40E3SG',compile_processors=4,
      bitstream_generation=False,allowed_stages=['syn','fit','sta'],clock_period_ns=10,seed=1,intermediate_snapshots=True,
      core_parameters=dict(P=p,Q=(2-p)%(1<<32)),source_sha256={name:sha(raw) for name,raw in sources.items()},
      control_sha256={name:sha(text.encode()) for name,text in controls.items()},native_prerequisites=gates(variant),
      cell_comparison=['frozen_butterfly','factored_butterfly','fused_butterfly'],independent_input_sets=3,
      expected_variable_products_by_source=3,butterfly_latency=5,wrapper_input_delay=1,R=1<<32,
      normalized_baseline='exact frozen BF except module name and normalized factored Montgomery leaf binding; byte-reversal checked',
      comparison_domain='modP identical; public unsigned28<2P. Representatives may differ byP.',
      scope='Matched scalar sizing separates factorization from fusion. No standalone-to-field area credit, wholeP16 fit or selected clock claim.',
      promotion_allowed=False))
    return fit_dispatch.snapshot(destination)
def submit(project,variant=1):
    identifier='stream27-l3-fused-butterfly-f0-v1' if variant==1 else 'stream27-l3-fused-sign-butterfly-f0-v1'
    return fit_submit.submit(ROOT/'queue/standing-fits',identifier,Path(project).resolve(),
      '10',1,dict(azure4=list('abcd'),aws6=list('ab')),'component_probe',dict(exemption='component_sizing_probe'),
      priority=50,requires=gates(variant),track='S',purpose='p16_diet')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write-source',action='store_true');parser.add_argument('--project',type=Path)
    parser.add_argument('--submit',action='store_true');parser.add_argument('--variant',type=int,choices=(1,2),default=1);args=parser.parse_args()
    if args.write_source:write_source(args.variant);print('P5 sizing source ready')
    elif args.submit:print(json.dumps(submit(args.project,args.variant),indent=2))
    else:print(json.dumps(prepare(args.project,variant=args.variant),indent=2))
