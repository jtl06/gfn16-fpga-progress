"""Independent-input parent/split scalar packing probe, not field/whole area."""
import argparse
import json
from pathlib import Path
from . import stream27_product_split as s
from . import stream27_l3_factored_probe_v1 as donor
from fpga.cloud import plain_fit_v5 as fit

ROOT=s.ROOT
SELF='reference/stream27_product_split_probe.py'
TOP='genefer_stream27_product_split_probe_v1'

def wrapper():
    text=donor.TEXT.replace(donor.TOP,TOP)
    text=text.replace('genefer_stream27_montgomery_factored_v1 #','genefer_stream27_product_split_v1 #',1)
    text=text.replace('genefer_montgomery_mul27_sparse_pipe #','genefer_stream27_montgomery_factored_v1 #')
    text=text.replace('genefer_stream27_montgomery28x27_factored_v1 #','genefer_stream27_product_split_lazy_v1 #',1)
    text=text.replace('genefer_montgomery_mul28x27_sparse_pipe_v2 #','genefer_stream27_montgomery28x27_factored_v1 #')
    return text.replace('new_canonical','split_canonical').replace('new_lazy','split_lazy').replace('frozen_canonical','parent_canonical').replace('frozen_lazy','parent_lazy')

def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2);f.write('\n')

def prepare(destination):
    proof=s.verify_source();destination=Path(destination).resolve()
    s.need(destination.is_relative_to(ROOT) and not destination.exists(),'PROBE_FRESH')
    sources={TOP+'.sv':wrapper().encode(),Path(s.RTL).name:(ROOT/s.RTL).read_bytes(),Path(s.PARENT).name:(ROOT/s.PARENT).read_bytes()}
    (destination/'rtl').mkdir(parents=True)
    for name,raw in sources.items():
        with (destination/'rtl'/name).open('xb') as f:f.write(raw)
    qsf='''set_global_assignment -name FAMILY "Arria 10"
set_global_assignment -name DEVICE 10AX115N4F40E3SG
set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files
set_global_assignment -name NUM_PARALLEL_PROCESSORS 6
set_global_assignment -name SEED 1
set_global_assignment -name SDC_FILE probe.sdc
set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on
'''+f'set_global_assignment -name TOP_LEVEL_ENTITY {TOP}\n'
    qsf+=''.join(f'set_global_assignment -name SYSTEMVERILOG_FILE rtl/{name}\n' for name in sources)
    qsf+='set_parameter -name P 104857601\nset_parameter -name Q 4190109697\n'
    qsf+=''.join(f'set_instance_assignment -name VIRTUAL_PIN ON -to {{{name}}}\n' for name in ('rst_n','in_valid[*]','lhs[*]','rhs[*]','out_valid[*]','result[*]'))
    controls={'probe.qsf':qsf,'probe.qpf':'QUARTUS_VERSION = "26.1"\nPROJECT_REVISION = "probe"\n',
        'probe.sdc':'# Scalar virtual-I/O packing probe, not board/reset-release signoff.\ncreate_clock -name kernel_clk -period 10 [get_ports {clk}]\nderive_clock_uncertainty\nset_false_path -from [get_ports {rst_n}]\n',
        'run.tcl':fit.FULL_TCL}
    for name,text in controls.items():
        with (destination/name).open('x') as f:f.write(text)
    m=dict(schema='stream27-product-split-scalar-sizing-v1',status='prepared_native_normals_required',top=TOP,
        target='P16_factored_product_split_scalar',edition='pro',device='10AX115N4F40E3SG',compile_processors=6,
        bitstream_generation=False,allowed_stages=['syn','fit','sta'],clock_period_ns=10,seed=1,
        source_sha256={n:s.sha(raw) for n,raw in sources.items()},control_sha256={n:s.sha(t.encode()) for n,t in controls.items()},
        core_parameters=dict(P=104857601,Q=4190109697),intermediate_snapshots=True,leaf_latency=3,wrapper_input_delay=1,
        independent_input_sets=4,cell_comparison=['split_canonical','parent_canonical','split_lazy','parent_lazy'],
        proof=proof,source_preparation_sha256={SELF:s.sha((ROOT/SELF).read_bytes())},
        measured_fields_required=['per-entity needed/placed ALM','dedicated fabric logic registers','DSP output register packing','DSP count','LAB','internal setup/hold'],
        scope='Four independent operand/valid sources forbid shared products. Canonical control and lazy treatment within same layout; no scalar-times-cell field savings, whole resource or promoted clock.',promotion_allowed=False)
    dump(destination/'manifest.json',m);return dict(project=str(destination),status=m['status'])

def gates():
    refs=[]
    for field in range(3):
        qid=f's4-product-split-f{field}-normal-q1-v1';path=ROOT/'queue/evidence'/qid/'gate-receipt.json'
        v=json.loads(path.read_text());s.need(v['id']==qid and v['status']=='PASS_expected_contracts','ACTUAL_NATIVE_GATE')
        refs.append(dict(path=str(path),sha256=s.sha(path.read_bytes()),fields=dict(id=qid,status='PASS_expected_contracts')))
    return refs

def submit(project):
    from fpga.tools import fit_submit
    project=Path(project).resolve();m=json.loads((project/'manifest.json').read_text())
    s.need(m['top']==TOP and m['proof']==s.verify_source(),'IMMUTABLE_PROBE_SOURCE')
    return fit_submit.submit(ROOT/'queue/standing-fits','s4-product-split-scalar-packing-f0-v1',project,'10',1,
        dict(aws6=['a','b']),'component_probe',dict(exemption='component_sizing_probe'),workers=6,priority=15,
        requires=gates(),track='S',purpose='p16_diet')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True);p.add_argument('--submit',action='store_true')
    a=p.parse_args();print(json.dumps(submit(a.project) if a.submit else prepare(a.project),indent=2))
