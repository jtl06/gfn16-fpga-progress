"""Matched 8ns registered F3 field packet; fail closed before actual native gates."""
import argparse
import hashlib
import json
from pathlib import Path
from fpga.reference import a10_writeback_launch_prepare_v1 as candidate
from fpga.reference import a10_writeback_native_replay_v1 as native
from fpga.reference import a10_upper_sum_field_probe_v2 as parent

ROOT=candidate.ROOT; base=parent.base
TOP='genefer_a10_registered_field_probe_writeback_v1'


def source_inputs():
    candidate.verify();files,_=parent.source_inputs()
    files.pop(parent.TOP+'.sv');files.pop(Path(candidate.gen.PARENT).name)
    files[Path(candidate.gen.TARGET).name]=(ROOT/candidate.gen.TARGET).read_bytes()
    recipe=base.load_exact(base.RECIPE,base.RECIPE_SHA,'_f3_registered_recipe')
    recipe.CHILDREN=dict(recipe.CHILDREN,**{base.CHILD:base.CHILD_SHA})
    wrapper,receipt=recipe.generate(files[base.CHILD+'.sv'],TOP);files[TOP+'.sv']=wrapper.encode()
    return files,receipt


def actual_native():
    # Source-bound typed normal math/counters/cancel+recovery and rc1negative;
    # no raw exit0 shortcut and no manufactured pending-gate PASS.
    return {f'aw{aw}-f{field}':native.replay(aw,field) for aw in (5,8,16) for field in (0,1,2)}


def prepare(output, workers=6):
    candidate.gen.upper.need(type(workers) is int and workers in (4,6), 'A10_F3_FIT_WORKERS')
    candidate.gen.upper.need(not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')), 'A10_F3_FIT_PAUSE')
    output=Path(output).resolve();candidate.gen.upper.need(not output.exists(), 'A10_F3_FRESH_PROJECT')
    gates=actual_native();files,wrapper=source_inputs()
    plain=base.load_exact(base.PLAIN,base.PLAIN_SHA,'_f3_plain')
    controls={'probe.qpf':'QUARTUS_VERSION = "26.1"\nPROJECT_REVISION = "probe"\n','probe.sdc':base.SDC,'run.tcl':plain.FULL_TCL}
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE '+base.DEVICE,
         'set_global_assignment -name TOP_LEVEL_ENTITY '+TOP,'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
         'set_global_assignment -name NUM_PARALLEL_PROCESSORS '+str(workers),'set_global_assignment -name SEED 1',
         'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON','set_global_assignment -name SDC_FILE probe.sdc']
    qsf+=['set_parameter -name '+name+' '+str(value) for name,value in base.PARAMETERS.items()]
    qsf+=['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in files]
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to "'+p['name']+('[*]' if p['width'] else '')+'"'
          for p in wrapper['ports'] if p['name']!='clk']
    controls['probe.qsf']='\n'.join(qsf)+'\n';output.mkdir(parents=True);(output/'rtl').mkdir()
    for name,raw in files.items():
        with (output/'rtl'/name).open('xb') as stream:stream.write(raw)
    for name,text in controls.items():
        with (output/name).open('x') as stream:stream.write(text)
    manifest=dict(schema='a10-writeback-field-sizing-project-v1',target='A10_F3_registered_AW16_L64_F0',
        top=TOP,device=base.DEVICE,address_width=16,core_parameters=base.PARAMETERS,field=0,
        arithmetic_lanes=64,host_lanes=16,root_profile_format=3,seed=1,clock_period_ns=8.0,compile_processors=workers,
        edition='pro',required_quartus_version='26.1.0 Build 110 Pro Edition',bitstream_generation=False,
        allowed_stages=['syn','fit','sta'],source_sha256={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()},
        control_sha256={name:base.sha(output/name) for name in controls},status='actual_native_child_pass_source_only_sizing',
        exemption='component_sizing_probe',ancestry='F3 isolated writebundle/drain from exact native-qualified upper03f3; not currentwholefitting source.',
        matched_parent_manifest_sha256='711fd3a733e90bf5ab1a9c12175ac9d757e76bfe75e854a86184fcd36cf95787',
        measured_parent_receipt_sha256=candidate.gen.RECEIPT_SHA,measured_parent_path_ledger_sha256=candidate.gen.MEASURED_SHA,
        native_connected_reports={name:value['report_sha256'] for name,value in gates.items()},
        native_gate_sha256={name:value['gate_sha256'] for name,value in gates.items()},native_full_N_child_verified=True,
        source_only_ledger=candidate.gen.ledger(16),isolated_delta='Internal selectedword/row/enable bankFF and physicalcompletion token; +1/stage andpoint; exactarithmetic/root/profile/idlehost retained.',
        registered_boundary_recipe_sha256=base.RECIPE_SHA,registered_boundary_receipt=wrapper,
        wrapper_native_gate_pending=True,wrapper_request_added_edges=1,wrapper_response_added_edges=1,
        requested_intermediate_snapshots=True,hold_repair_claim=False,promotion_allowed=False,
        physical_timing_proven=False,vendor_executed=False,numeric_full_N_NTT_locally_performed=False,
        timing_scope='Matched onefield8ns/seed1/K6recipe, virtualI/O/resetreleaseexcluded. Parenthold−.140retained; no expectedholdrepair orwholeclock.')
    with (output/'manifest.json').open('x') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
    return dict(project=str(output),manifest_sha256=base.sha(output/'manifest.json'),sources=len(files),
                status='prepared_matched_F3_not_dispatched',promotion_allowed=False)


if __name__=='__main__':
    args=argparse.ArgumentParser(description=__doc__);args.add_argument('--output',type=Path,required=True)
    args.add_argument('--workers',type=int,choices=(4,6),default=6);parsed=args.parse_args()
    print(json.dumps(prepare(parsed.output,parsed.workers),indent=2))
