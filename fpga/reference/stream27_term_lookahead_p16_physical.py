"""Exact matched full-geometry field pair; no wholefit or narrowed timing GO."""
import argparse,json,re
from pathlib import Path
from . import stream27_term_lookahead_p16_bind as binding
from . import stream27_term_select_native as base
ROOT=binding.ROOT
GATE='s4-p16-term-lookahead-aw16-f1-v2-normal-q1'
def prepare(destination,variant='candidate'):
    from fpga.cloud.plain_fit_v5 import FULL_TCL
    from fpga.tools import fit_dispatch
    destination=Path(destination).resolve();binding.need(destination.is_relative_to(ROOT) and not destination.exists() and variant in ('parent','candidate'),'TERM_LOOKAHEAD_FIT_FRESH')
    b=binding.prepare(65536,1);top=b['term_lookahead']['parent_top'] if variant=='parent' else b['top'];rtl=destination/'rtl';rtl.mkdir(parents=True)
    for name,text in b['files'].items():
        with (rtl/name).open('x') as stream:stream.write(text)
    declaration=b['files'][top+'.sv'].split(') (',1)[0];allowed=set(re.findall(r'\b([A-Z][A-Z0-9_]*)=',declaration));params={k:v for k,v in b['parameters'].items() if k in allowed}
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE 10AX115N4F40E3SG','set_global_assignment -name TOP_LEVEL_ENTITY '+top,
        'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files','set_global_assignment -name NUM_PARALLEL_PROCESSORS 4','set_global_assignment -name SEED 1',
        'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON','set_global_assignment -name SDC_FILE probe.sdc']
    qsf+=['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in b['rtl_sources']]
    qsf+=[f'set_parameter -name {name} {value}' for name,value in params.items()]
    ports=['rst_n','in_slot_valid','frame_start','context_enabled','generation_in[*]','live_generation[*]','base_in[*]','epoch_in[*]','correction_epoch[*]',
        'correction_valid','correction_generation[*]','data_in[*]','c0_in[*]','c1_in[*]','out_slot_valid','out_frame_start','out_eligible','out_error','fault_pending',
        'generation_out[*]','data_out[*]','out_epoch[*]','commit_valid','commit_frame_start','commit_generation[*]','commit_epoch[*]','commit_data[*]','owner_count[*]',
        'frame_accept','correction_accept','output_row[*]','cycle_count[*]','frame_count[*]']
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to {'+port+'}' for port in ports]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n','probe.sdc':'create_clock -name kernel_clk -period 10.000 [get_ports {clk}]\nderive_clock_uncertainty\n','run.tcl':FULL_TCL}
    for name,text in controls.items():
        with (destination/name).open('x') as stream:stream.write(text)
    base.dump(destination/'manifest.json',dict(schema='s4-p16-term-lookahead-matched-field-probe-v1',status='source_prepared',top=top,edition='pro',device='10AX115N4F40E3SG',
        compile_processors=4,seed=1,clock_period_ns=10,address_width=16,bitstream_generation=False,allowed_stages=['syn','fit','sta'],core_parameters=params,
        raw_multiplier_parameters=None,field_parameters=None,source_sha256=b['generated_sha256'],control_sha256={name:base.sha(text.encode()) for name,text in controls.items()},
        preparation_source_sha256=b['source_sha256'],geometry=b['geometry'],term_lookahead=b['term_lookahead'],variant=variant,native_source_gate=GATE,
        scope='Matched fullN currentP16 fourtimingflags+TERM_SELECT field1; identical source file set/parameters/IO/10ns/seed1, only selected root differs. No whole/reset/IO/promotion claim; all-corner global setup plus unrestricted protocol→term/DSP ingress required.',promotion_allowed=False))
    return fit_dispatch.snapshot(destination)
def submit(project,variant):
    from fpga.tools import fit_submit
    return fit_submit.submit(ROOT/'queue/standing-fits',f's4-p16-term-lookahead-field1-{variant}-10000-v1',Path(project).resolve(),'10',1,
        dict(azure4=list('abcd'),aws6=list('ab')),'component_probe',dict(exemption='component_sizing_probe'),priority=44,track='S',purpose='clock_push',native_source_gate=GATE)
if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--project',type=Path,required=True);q.add_argument('--variant',choices=('parent','candidate'),required=True);q.add_argument('--submit',action='store_true');a=q.parse_args();print(json.dumps(submit(a.project,a.variant) if a.submit else prepare(a.project,a.variant),indent=2))
