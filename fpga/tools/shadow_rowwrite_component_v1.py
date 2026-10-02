"""Physical RAM inference and registered-output component probe for shadow leaf."""
import argparse,hashlib,json
from pathlib import Path
from fpga.cloud import aws_fit_v6,plain_fit_v1
ROOT=Path(__file__).resolve().parents[1]
TOP='genefer_stream27_shadow_rowwrite_sizing_v1'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
INPUTS=[('','quarantine'),('[1:0]','owner_enabled'),('[111:0]','live_owner'),
    ('','host_access'),('','load_we'),('','read_en'),('','host_context'),('[15:0]','host_addr'),('[31:0]','write_data'),
    ('','row_read_req'),('','row_read_context'),('[11:0]','row_read_address'),('[55:0]','row_read_owner'),
    ('','commit_we'),('','commit_context'),('[15:0]','commit_address'),('[31:0]','commit_word'),('[55:0]','commit_owner'),
    ('','row_write_req'),('','row_write_context'),('[11:0]','row_write_address'),('[511:0]','row_write_data'),('[55:0]','row_write_owner')]
OUTPUTS=[('','read_valid'),('','read_context'),('[95:0]','read_data'),('[55:0]','read_owner'),
    ('','row_read_valid'),('','row_response_context'),('[511:0]','row_read_data'),('[55:0]','row_response_owner'),
    ('','commit_ack'),('','row_write_ack'),('','rejected')]
def source():
    ports=['input logic clk,rst_n']+[f'input logic {width} {name}' for width,name in INPUTS]+[f'output logic {width} {name}' for width,name in OUTPUTS]
    text='// Physical sink FFs only: leaf native response stays E0; this probe adds one external output edge.\nmodule '+TOP+'(\n'+',\n'.join(ports)+');\n'
    text+='\n'.join(f'logic {width} {name}_q;' for width,name in OUTPUTS)+'\n'
    connections=['.clk','.rst_n']+['.'+name for width,name in INPUTS]+[f'.{name}({name}_q)' for width,name in OUTPUTS]
    text+='genefer_stream27_host_image_rowwrite_v1 #(.AW(16),.P(16),.CONTEXTS(2),.OWNER_W(56)) host_image (\n'+',\n'.join(connections)+');\n'
    text+='always_ff @(posedge clk)begin\n'+'\n'.join(f'{name}<={name}_q;' for width,name in OUTPUTS)+'\nend\nendmodule\n'
    return text
def prepare(out):
    assert not out.exists() and not (ROOT/'docs/briefs/PAUSE').exists() and not (ROOT/'queue/PAUSE').exists()
    (out/'rtl').mkdir(parents=True)
    frozen=ROOT/'results/throughput-20260929/trackS-shadow-rowwrite-v1/normal-role-v1/source/fpga'
    files={name:(frozen/'rtl/kernel'/name).read_text() for name in ('genefer_stream27_host_image_rowwrite_v1.sv','genefer_sdp_ram32.sv')}
    files[TOP+'.sv']=source()
    for name,raw in files.items():
        with (out/'rtl'/name).open('x') as stream:stream.write(raw)
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE 10AX115N4F40E3SG',
         'set_global_assignment -name TOP_LEVEL_ENTITY '+TOP,'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
         'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4','set_global_assignment -name SEED 1',
         'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON','set_global_assignment -name SDC_FILE probe.sdc']
    qsf+=['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in files]
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to {'+name+('[*]' if width else '')+'}' for width,name in INPUTS+OUTPUTS]
    qsf.append('set_instance_assignment -name VIRTUAL_PIN ON -to {rst_n}')
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'QUARTUS_VERSION = "26.1"\nPROJECT_REVISION = "probe"\n',
        'probe.sdc':'create_clock -name kernel_clk -period 10 [get_ports {clk}]\nderive_clock_uncertainty\n# Virtual controls/boardIO/resetrelease excluded.\nset_false_path -from [get_ports {rst_n}]\n',
        'run.tcl':plain_fit_v1.FULL_TCL}
    for name,raw in controls.items():
        with (out/name).open('x') as stream:stream.write(raw)
    manifest=dict(schema='trackS-shadow-rowwrite-component-v1',status='source_ready_normal_gate_required',top=TOP,edition='pro',
        device='10AX115N4F40E3SG',compile_processors=4,bitstream_generation=False,allowed_stages=['syn','fit','sta'],clock_period_ns=10,
        seed=1,core_parameters={},intermediate_snapshots=True,source_sha256={name:sha(out/'rtl'/name) for name in files},
        control_sha256={name:sha(out/name) for name in controls},native_prerequisite='s4-shadow-row-normal-q1-v1',promotion_allowed=False,
        scope='AW16/P16/CONTEXTS2 shadow RAM transport component. Output sink registers add one physical-only edge for q/context mux timing; native direct leaf remains E0. Virtual external controls, publication/canonical/arithmetic/resetrelease/whole clock unqualified.')
    with (out/'manifest.json').open('x') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
    print(json.dumps(aws_fit_v6.verify_project(out)))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);prepare(parser.parse_args().output.resolve())
