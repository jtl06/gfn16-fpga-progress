"""One source-matched P16/corr2 field selector fit; not a whole clock claim."""
import argparse
from pathlib import Path
from . import stream27_term_select_native as native

ROOT=native.ROOT
ID='s4-p16-term-select-field1-c2-10000-v1'
GATE='s4-p16-term-select-aw16-f1-c2-normal-q1-v1'


def prepare(destination):
    from fpga.cloud.plain_fit_v5 import FULL_TCL
    from fpga.tools import fit_dispatch
    destination=Path(destination).resolve()
    native.need(destination.is_relative_to(ROOT) and not destination.exists(),'TERM_SELECT_FIT_FRESH')
    b=native.field_bundle(16,16,1,corr_serial_bfs=2);rtl=destination/'rtl';rtl.mkdir(parents=True)
    for name,text in b['files'].items():
        with (rtl/name).open('x') as stream:stream.write(text)
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE 10AX115N4F40E3SG',
         'set_global_assignment -name TOP_LEVEL_ENTITY '+b['top'],'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
         'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4','set_global_assignment -name SEED 1',
         'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on','set_global_assignment -name SDC_FILE probe.sdc']
    qsf+=['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in b['rtl_sources']]
    params={key:value for key,value in b['parameters'].items() if key!='FIELD'}
    qsf+=[f'set_parameter -name {key} {value}' for key,value in params.items()]
    ports=['rst_n','in_slot_valid','frame_start','context_enabled','generation_in[*]','live_generation[*]',
           'base_in[*]','epoch_in[*]','correction_epoch[*]','correction_valid','correction_generation[*]',
           'data_in[*]','c0_in[*]','c1_in[*]','out_slot_valid','out_frame_start','out_eligible','out_error',
           'fault_pending','generation_out[*]','data_out[*]','out_epoch[*]','commit_valid','commit_frame_start',
           'commit_generation[*]','commit_epoch[*]','commit_data[*]','owner_count[*]','frame_accept',
           'correction_accept','output_row[*]','cycle_count[*]','frame_count[*]']
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to {'+port+'}' for port in ports]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n',
              'probe.sdc':'create_clock -name kernel_clk -period 10.000 [get_ports {clk}]\nderive_clock_uncertainty\n',
              'run.tcl':FULL_TCL}
    for name,text in controls.items():
        with (destination/name).open('x') as stream:stream.write(text)
    m=dict(schema='s4-p16-corr2-term-select-field-probe-v1',status='source_prepared',top=b['top'],edition='pro',
        device='10AX115N4F40E3SG',compile_processors=4,seed=1,clock_period_ns=10,address_width=16,bitstream_generation=False,
        allowed_stages=['syn','fit','sta'],core_parameters=params,raw_multiplier_parameters=None,field_parameters=None,
        source_sha256=b['generated_sha256'],control_sha256={name:native.sha(text.encode()) for name,text in controls.items()},
        preparation_source_sha256=b['source_sha256'],geometry=b['geometry'],term_select=b['term_select'],native_source_gate=GATE,
        scope='Source-matched fullN P16 field1/corr2 selector-only physical measurement; no diet Mont/whole gain, false paths, reset/I/O sign-off or promotion.',
        promotion_allowed=False)
    native.dump(destination/'manifest.json',m)
    return fit_dispatch.snapshot(destination)


def submit(project):
    from fpga.tools import fit_submit
    return fit_submit.submit(ROOT/'queue/standing-fits',ID,Path(project).resolve(),'10',1,
        dict(azure4=list('abcd'),aws6=list('ab')),'component_probe',dict(exemption='component_sizing_probe'),
        priority=44,track='S',purpose='clock_push',native_source_gate=GATE)


if __name__=='__main__':
    import json
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--submit',action='store_true')
    a=p.parse_args();r=submit(a.project) if a.submit else prepare(a.project);print(json.dumps(r,indent=2))
