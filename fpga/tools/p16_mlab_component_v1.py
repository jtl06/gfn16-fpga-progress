"""Matched P2-only physical leaf bank; no whole-P16 clock or savings claim."""
import argparse,hashlib,json
from pathlib import Path
from fpga.cloud import aws_fit_v6,plain_fit_v1
ROOT=Path(__file__).resolve().parents[1]
TOP='genefer_stream27_p16_mlab_sizing_v1'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def source():
    geometries=[(w,d) for d in (4,8,16,32) for w in (10,28,29) for _ in range(8)]
    bits=sum(w for w,d in geometries);count=len(geometries)
    text=f'''module {TOP} #(parameter int USE_MLAB=0)(input logic clk,rst_n,
input logic [{count-1}:0] advance,input logic [{bits-1}:0] write_data,output logic [{bits-1}:0] read_data);
'''
    offset=0
    for i,(width,depth) in enumerate(geometries):
        text+=f'''if(USE_MLAB)begin: candidate_{i}_w{width}_d{depth}
genefer_stream27_delay_mlab_v1 #(.WORD_W({width}),.DEPTH({depth})) fifo (
.clk,.rst_n,.advance(advance[{i}]),.write_word(write_data[{offset}+:{width}]),.head(read_data[{offset}+:{width}]));
end else begin: parent_{i}_w{width}_d{depth}
genefer_stream27_mdc_fifo_smallreg_v1 #(.WORD_W({width}),.DEPTH({depth})) fifo (
.clk,.rst_n,.advance(advance[{i}]),.write_word(write_data[{offset}+:{width}]),.head(read_data[{offset}+:{width}]));
end
'''
        offset+=width
    return text+'endmodule\n'

def prepare(out):
    assert not out.exists() and not (ROOT/'docs/briefs/PAUSE').exists() and not (ROOT/'queue/PAUSE').exists()
    frozen=ROOT/'results/throughput-20260929/trackS-p2-mlab-v1/normal-role-v2/source/fpga/rtl'
    outputs=[]
    for mode in (0,1):
        project=out/('mlab_candidate' if mode else 'register_parent');(project/'rtl').mkdir(parents=True)
        files={name:(frozen/name).read_text() for name in ('genefer_stream27_delay_mlab_v1.sv','genefer_stream27_mdc_fifo_smallreg_v1.sv','genefer_stream27_mdc_commutator_sync.sv')}
        files[TOP+'.sv']=source()
        for name,raw in files.items():
            with (project/'rtl'/name).open('x') as stream:stream.write(raw)
        qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE 10AX115N4F40E3SG',
             'set_global_assignment -name TOP_LEVEL_ENTITY '+TOP,'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
             'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4','set_global_assignment -name SEED 1',
             'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON','set_global_assignment -name SDC_FILE probe.sdc',
             'set_parameter -name USE_MLAB '+str(mode)]
        qsf+=['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in files]
        qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to {'+name+'}' for name in ('rst_n','advance[*]','write_data[*]','read_data[*]')]
        controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'QUARTUS_VERSION = "26.1"\nPROJECT_REVISION = "probe"\n',
            'probe.sdc':'create_clock -name kernel_clk -period 10 [get_ports {clk}]\nderive_clock_uncertainty\n# Virtual board IO/reset release excluded.\nset_false_path -from [get_ports {rst_n}]\n',
            'run.tcl':plain_fit_v1.FULL_TCL}
        for name,raw in controls.items():
            with (project/name).open('x') as stream:stream.write(raw)
        manifest=dict(schema='trackS-p2-mlab-component-v1',status='source_ready_normal_gate_required',top=TOP,edition='pro',
            device='10AX115N4F40E3SG',compile_processors=4,bitstream_generation=False,allowed_stages=['syn','fit','sta'],
            clock_period_ns=10,seed=1,core_parameters=dict(USE_MLAB=mode),intermediate_snapshots=True,
            source_sha256={name:sha(project/'rtl'/name) for name in files},control_sha256={name:sha(project/name) for name in controls},
            scope='Matched96independentFIFOleaves:8eachofWIDTH10/28/29 xDEPTH4/8/16/32. ActualMLABinference/needed+placedALMs/internal10nsSTA; virtualIO/resetexcluded. Sharedstage/wholeP16unmeasured.',
            native_prerequisite='s4-p2-mlab-normal-q1-v1',promotion_allowed=False)
        with (project/'manifest.json').open('x') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
        context=aws_fit_v6.verify_project(project)
        outputs.append(dict(path=str(project),manifest_sha256=context['manifest_sha256'],mode=mode))
    with (out/'source-handoff.json').open('x') as stream:json.dump(dict(projects=outputs),stream,indent=2);stream.write('\n')
    print(json.dumps(outputs))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);prepare(parser.parse_args().output.resolve())
