"""Synthesis-only whole P16 diet project from the exact frozen normal role.

No T5b oracle is synthesized. This prepares source, not a whole-fit GO. The
standing fit owner must use a genuinely synthesis-only bounded entrypoint;
the ordinary full-fit intake is intentionally not called here.
"""
import argparse
import hashlib
import json
from pathlib import Path
from .stream27_host_chain_physical_v1 import host_ports
from .stream27_field_physical_probe_v1 import DEVICE

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_p16_diet_whole_physical.py'
SYN_TCL='''# Actual whole-resource synthesis screen only; no fit, STA or assembler.
load_package project
load_package flow
cd [file dirname [file normalize [info script]]]
project_open probe
if {[catch {
    execute_module -tool syn
} failure]} {
    catch {project_close}
    error $failure
}
catch {project_close}
'''


def need(ok,why):
    if not ok:raise ValueError('S4_P16_DIET_WHOLE_SCREEN_'+why)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(manifest,source,destination,*,workers=6):
    manifest,source,destination=(Path(path).resolve() for path in (manifest,source,destination))
    need(all(path.is_relative_to(ROOT) for path in (manifest,source,destination)),'OWNED_PATHS')
    need(not destination.exists() and not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),'FRESH_PAUSE')
    need(type(workers) is int and workers in (4,6),'WORKERS')
    m=json.loads(manifest.read_text());meta=m['full_host'];top=meta['standalone_top']
    params=m['build']['parameters']
    need(params==dict(AW=16,P=16,CONTEXTS=1,EPOCH_SEED=65534,
        CORR_SERIAL_BFS=2,COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1,CANONICAL_PIPE_STAGES=1),'EXACT_COMPOSITION')
    pins=meta['standalone_generated_sha256']
    need(top+'.sv' in pins and len(pins)==58,'ACTUAL_STANDALONE')
    for name,pin in pins.items():
        path=source/'rtl'/name
        need(Path(name).name==name and not path.is_symlink() and path.resolve()==path and
            sha(path)==pin and m['sources']['rtl/'+name]==pin,'NATIVE_RTL_BINDING:'+name)
    need(pins[top+'.sv']==meta['candidate_root_sha256'],'NATIVE_ROOT')
    project=destination/'project';(project/'rtl').mkdir(parents=True)
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE '+DEVICE,
        'set_global_assignment -name TOP_LEVEL_ENTITY '+top,
        'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
        f'set_global_assignment -name NUM_PARALLEL_PROCESSORS {workers}',
        'set_global_assignment -name SEED 1','set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON',
        'set_global_assignment -name SDC_FILE probe.sdc']
    for name,pin in pins.items():
        (project/'rtl'/name).write_bytes((source/'rtl'/name).read_bytes())
        qsf.append('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name)
    qsf+=['set_parameter -name '+key+' '+str(value) for key,value in params.items()]
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to {'+port+'}' for port in host_ports((project/'rtl'/(top+'.sv')).read_text())]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n',
        'probe.sdc':'create_clock -name kernel_clk -period 10.000 [get_ports {clk}]\nderive_clock_uncertainty\n',
        'run.tcl':SYN_TCL}
    for name,text in controls.items():(project/name).write_text(text)
    pm=dict(status='source_prepared_synthesis_only_NOT_whole_fit_GO',scope='whole_core',top=top,
        edition='pro',device=DEVICE,compile_processors=workers,seed=1,clock_period_ns=10,
        address_width=16,bitstream_generation=False,allowed_stages=['syn'],core_parameters=params,
        raw_multiplier_parameters=None,field_parameters=None,source_sha256=pins,
        control_sha256={name:sha(project/name) for name in controls},
        preparation_source_sha256={SELF:sha(ROOT/SELF)},native_role_manifest_sha256=sha(manifest),
        native_normal_id='s4-aw16-p16-diet-whole-normal-q1-v1',
        geometry=meta['geometry'],host_contract=meta['host_contract'],cycle_contract=meta['cycle_contract'],
        diet_binding=meta['diet_binding'],intermediate_snapshots=True,
        whole_resource_measurement_required=True,whole_resource_go=False,fit_allowed=False,
        placement_performed=False,timing_qualified=False,promotion_allowed=False,
        notes=['Exact standalone58 subset of actual paired69 native source; original CRT Montgomery leaves retained.',
            'All three real fields plus original signed host/CRT/carry/final canonical register; no 3xF0 area estimate.',
            'Synthesis estimates are not final placed resources or timing. No fit/STA command in this project.',
            'Normal-first source artifact; actual normal outcome and resource screen are separately retained.'])
    (project/'manifest.json').write_text(json.dumps(pm,indent=2)+'\n')
    result=dict(status=pm['status'],project=str(project),manifest_sha256=sha(project/'manifest.json'),
        native_role_manifest_sha256=sha(manifest),rtl_members=len(pins),whole_resource_go=False,
        actual_vendor_executed=False,fit_allowed=False,promotion_allowed=False)
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','source','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--workers',type=int,choices=(4,6),default=6)
    args=parser.parse_args();print(json.dumps(prepare(args.manifest,args.source,args.output,workers=args.workers),indent=2))
