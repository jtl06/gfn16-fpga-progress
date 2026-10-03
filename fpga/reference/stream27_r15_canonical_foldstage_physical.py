"""Matched canonical-only sizing; copied actual own full native source."""
import json
from pathlib import Path
from . import stream27_r15_canonical_foldstage_native as n
from . import stream27_r15_canonical_foldstage_bind as b

ROOT=b.ROOT;SELF='reference/stream27_r15_canonical_foldstage_physical.py'
GATE=n.identifier(16,'normal')

def prepare(output,variant='candidate'):
    from fpga.cloud.plain_fit_v5 import FULL_TCL
    from fpga.tools import fit_dispatch
    out=Path(output).resolve();b.need(out.is_relative_to(n.BASE) and not out.exists() and variant in ('parent','candidate'),'FRESH_PHYSICAL')
    capture=n.BASE/'full-normal';m=json.loads((capture/'manifest.json').read_bytes())
    top=b.OLD if variant=='parent' else b.NEW
    rtl=out/'rtl';rtl.mkdir(parents=True);pins={}
    for name in ('genefer_sdp_ram32',top):
        source='rtl/'+name+'.sv';raw=(capture/'source/fpga'/source).read_bytes()
        b.need(n.sha(raw)==m['sources'][source],'EXACT_OWN_NATIVE:'+source)
        with (rtl/(name+'.sv')).open('xb') as f:f.write(raw)
        pins[name+'.sv']=n.sha(raw)
    qsf=['set_global_assignment -name FAMILY "Arria 10"',
      'set_global_assignment -name DEVICE 10AX115N4F40E3SG',
      'set_global_assignment -name TOP_LEVEL_ENTITY '+top,
      'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
      'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4',
      'set_global_assignment -name SEED 1',
      'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON',
      'set_global_assignment -name SDC_FILE probe.sdc',
      'set_parameter -name AW 16','set_parameter -name P 16']
    qsf+=['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in pins]
    ports=('rst_n','load_valid','begin_canonical','read_req','load_row[*]','load_data[*]','c0[*]','c1[*]',
      'base[*]','read_address[*]','busy','done','error','image_valid','error_code[*]','cycles[*]',
      'read_valid','read_address_out[*]','read_data[*]')
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to {'+p+'}' for p in ports]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n',
      'probe.sdc':'create_clock -name kernel_clk -period 12.000 [get_ports {clk}]\nderive_clock_uncertainty\n','run.tcl':FULL_TCL}
    for name,text in controls.items():
        with (out/name).open('x') as f:f.write(text)
    n.dump(out/'manifest.json',dict(schema='r15-canonical-foldstage-component-v1',status='source_prepared',
      top=top,edition='pro',device='10AX115N4F40E3SG',compile_processors=4,seed=1,clock_period_ns=12,
      bitstream_generation=False,allowed_stages=['syn','fit','sta'],core_parameters=dict(AW=16,P=16),
      raw_multiplier_parameters=None,field_parameters=None,source_sha256=pins,
      control_sha256={name:n.sha(text.encode()) for name,text in controls.items()},
      preparation_source_sha256={SELF:n.sha((ROOT/SELF).read_bytes())},variant=variant,native_source_gate=GATE,
      captured_normal_manifest_sha256=n.sha((capture/'manifest.json').read_bytes()),
      scope='One natural-order canonical image leaf N65536/P16, own extra FOLD edge. Exact same virtual ports/device/12ns/seed/strategy; no whole controller, board, reset-release, I/O timing or aggregate clock qualification.',promotion_allowed=False))
    return fit_dispatch.snapshot(out)

def submit(project,variant):
    from fpga.tools import fit_submit
    return fit_submit.submit(ROOT/'queue/standing-fits','s4-p16-r15-canonical-foldstage-'+variant+'-12000-v1',
      Path(project).resolve(),'12',1,dict(azure4=list('abcd')),'component_probe',dict(exemption='component_sizing_probe'),
      workers=4,priority=45,track='S',purpose='sizing',native_source_gate=GATE)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--variant',choices=('parent','candidate'),required=True)
    p.add_argument('--submit',action='store_true');a=p.parse_args()
    print(json.dumps(submit(a.project,a.variant) if a.submit else prepare(a.project,a.variant),indent=2))
