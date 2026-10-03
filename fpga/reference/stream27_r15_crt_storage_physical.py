"""Matched one-CRT source-bound sizing projects; no whole resource forecast."""
import argparse
import json
from pathlib import Path
from fpga.reference import stream27_r15_storage_ram_bind as binder
from fpga.reference import stream27_r15_crt_numeric_pair_native as native

ROOT=binder.ROOT
SELF='reference/stream27_r15_crt_storage_physical.py'
GATE=native.IDS['normal']
BASE=ROOT/'results/throughput-20261003/trackS-r15-storage-ram-v1'


def prepare(output,variant='candidate'):
    from fpga.cloud.plain_fit_v5 import FULL_TCL
    from fpga.tools import fit_dispatch
    out=Path(output).resolve()
    binder.need(out.is_relative_to(BASE) and not out.exists() and variant in ('parent','candidate'),
                'FRESH_MATCHED_COMPONENT_PROJECT')
    # Freeze from the emitted actual paired role, never reemit its RTL.
    capture=BASE/'crt-pair-normal'
    m=json.loads((capture/'manifest.json').read_text())
    selected=['rtl/'+native.PARENT+'.sv','rtl/genefer_montgomery_mul27_sparse_pipe.sv'] if variant=='parent' else [
        'rtl/'+binder.CRT,'rtl/'+binder.NUMERIC_LEAF,'rtl/genefer_montgomery_mul27_sparse_pipe.sv']
    top=native.PARENT if variant=='parent' else 'genefer_crt3_27_mont_pipe'
    rtl=out/'rtl';rtl.mkdir(parents=True)
    pins={}
    for source in selected:
        raw=(capture/'source/fpga'/source).read_bytes()
        binder.need(binder.sha(raw)==m['sources'][source],'ACTUAL_NATIVE_SOURCE_SNAPSHOT:'+source)
        name=Path(source).name
        with (rtl/name).open('xb') as stream:stream.write(raw)
        pins[name]=binder.sha(raw)
    qsf=['set_global_assignment -name FAMILY "Arria 10"',
         'set_global_assignment -name DEVICE 10AX115N4F40E3SG',
         'set_global_assignment -name TOP_LEVEL_ENTITY '+top,
         'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
         'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4',
         'set_global_assignment -name SEED 1',
         'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON',
         'set_global_assignment -name SDC_FILE probe.sdc']
    qsf += ['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+n for n in pins]
    ports=['rst_n','in_valid','r1[*]','r2[*]','r3[*]','ready','out_valid','coefficient[*]']
    qsf += ['set_instance_assignment -name VIRTUAL_PIN ON -to {'+p+'}' for p in ports]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n',
              'probe.sdc':'create_clock -name kernel_clk -period 10.000 [get_ports {clk}]\nderive_clock_uncertainty\n',
              'run.tcl':FULL_TCL}
    for name,text in controls.items():
        with (out/name).open('x') as stream:stream.write(text)
    manifest=dict(schema='r15-crt-storage-matched-component-probe-v1',status='source_prepared',
        top=top,edition='pro',device='10AX115N4F40E3SG',compile_processors=4,seed=1,
        clock_period_ns=10,bitstream_generation=False,allowed_stages=['syn','fit','sta'],
        core_parameters={},raw_multiplier_parameters=None,field_parameters=None,
        source_sha256=pins,control_sha256={n:binder.sha(t) for n,t in controls.items()},
        preparation_source_sha256={SELF:binder.sha((ROOT/SELF).read_bytes())},
        variant=variant,native_source_gate=GATE,
        captured_normal_manifest_sha256=binder.sha((capture/'manifest.json').read_bytes()),
        scope='One CRT16/E16 II1; source-identical old/new modules from own actual paired normal. Same device/clock/IO/seed/strategy. Actual placed ALM/LAB/FF/RAM mapping and unrestricted internal global STA only; no whole-P16 extrapolation/reset-release/board/promotion claim.',
        promotion_allowed=False)
    native.normal.dump(out/'manifest.json',manifest)
    return fit_dispatch.snapshot(out)


def submit(project,variant):
    from fpga.tools import fit_submit
    return fit_submit.submit(ROOT/'queue/standing-fits',
        's4-p16-r15-crt-storage-'+variant+'-10000-v1',Path(project).resolve(),'10',1,
        dict(azure4=list('abcd')),'component_probe',dict(exemption='component_sizing_probe'),
        workers=4,priority=45,track='S',purpose='sizing',native_source_gate=GATE)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True)
    p.add_argument('--variant',choices=('parent','candidate'),required=True)
    p.add_argument('--submit',action='store_true');a=p.parse_args()
    print(json.dumps(submit(a.project,a.variant) if a.submit else prepare(a.project,a.variant),indent=2))
