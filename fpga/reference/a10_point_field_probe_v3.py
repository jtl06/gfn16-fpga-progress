"""Source-only matched A10 point-launch one-field sizing successor."""
import argparse
import hashlib
import json
from pathlib import Path
from fpga.reference import a10_field_physical_probe_v1 as parent
from fpga.reference import a10_point_launch_prepare_v3 as candidate

ROOT=parent.ROOT;TOP='genefer_a10_registered_field_probe_pointlaunch_v3'
SELF='reference/a10_point_field_probe_v3.py'
PARENT_HELPER_SHA='c6f0309c24b083af9b1860a948a27fd5123c214d6d6fd3725783c5f29ce1d8a5'
NATIVE={(5,0):'b03f12c316e9d06ffc845ac19da8d0c8fadb702da146d71d08f1255d1a955d5c',
        (5,1):'b76d5c80f982b1113a91c0499953f8470ced37d1c1ce95c79abe51597b7e793a',
        (5,2):'5669c7b64c03168d308a2126ad35aebd02ae17b55b76ad47201fac84fc86aa4c',
        (8,0):'82385607e7470068eabff0fff891f28a36b641675a52b18f20342e6033ed4e5e'}


def source_inputs():
    parent.need(parent.sha(ROOT/'reference/a10_field_physical_probe_v1.py')==PARENT_HELPER_SHA,'A10_POINT_FROZEN_FIELD_PARENT')
    candidate.verify()
    for (aw,field),pin in NATIVE.items():
        qid=f'a10-point-aw{aw}-f{field}-q1-v3';done=json.loads((ROOT/'queue/done'/f'{qid}.json').read_text())
        parent.need(done['result']['queue_report']['report_sha256']==pin and done['dependency_gate']['status']=='PASS_expected_contracts' and
            done['result']['properties']['ExecMainStatus']=='0','A10_POINT_ACTUAL_SMALL_GATES')
    files,_=parent.source_inputs();files.pop(parent.TOP+'.sv')
    parent_engine=Path(candidate.batch.repair.ENGINE_V2).name
    parent.need(hashlib.sha256(files[parent_engine]).hexdigest()==candidate.gen.PARENT_SHA,'A10_POINT_FITTED_ENGINE_PARENT')
    files.pop(parent_engine);files[Path(candidate.gen.TARGET).name]=(ROOT/candidate.gen.TARGET).read_bytes()
    recipe=parent.load_exact(parent.RECIPE,parent.RECIPE_SHA,'_point_registered_recipe')
    recipe.CHILDREN=dict(recipe.CHILDREN,**{parent.CHILD:parent.CHILD_SHA})
    wrapper,receipt=recipe.generate(files[parent.CHILD+'.sv'],TOP);files[TOP+'.sv']=wrapper.encode()
    return files,receipt


def prepare(output,workers=6):
    parent.need(type(workers) is int and workers in (4,6),'A10_POINT_FIT_WORKERS')
    parent.need(not (ROOT/'docs/briefs/PAUSE').exists(),'brief PAUSE')
    output=Path(output).resolve();parent.need(not output.exists() and output.parent.is_dir(),'A10_POINT_FRESH_PROJECT')
    files,wrapper=source_inputs();plain=parent.load_exact(parent.PLAIN,parent.PLAIN_SHA,'_point_plain')
    controls={'probe.qpf':'QUARTUS_VERSION = "26.1"\nPROJECT_REVISION = "probe"\n','probe.sdc':parent.SDC,'run.tcl':plain.FULL_TCL}
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE '+parent.DEVICE,
        'set_global_assignment -name TOP_LEVEL_ENTITY '+TOP,'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
        'set_global_assignment -name NUM_PARALLEL_PROCESSORS '+str(workers),'set_global_assignment -name SEED 1',
        'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON','set_global_assignment -name SDC_FILE probe.sdc']
    qsf+=['set_parameter -name '+name+' '+str(value) for name,value in parent.PARAMETERS.items()]
    qsf+=['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in files]
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to "'+p['name']+('[*]' if p['width'] else '')+'"' for p in wrapper['ports'] if p['name']!='clk']
    controls['probe.qsf']='\n'.join(qsf)+'\n';output.mkdir();(output/'rtl').mkdir()
    for name,raw in files.items():
        with (output/'rtl'/name).open('xb') as stream:stream.write(raw)
    for name,text in controls.items():
        with (output/name).open('x') as stream:stream.write(text)
    manifest=dict(schema='a10-point-launch-field-sizing-project-v3',target='A10_point_launch_registered_AW16_L64_F0',
        top=TOP,device=parent.DEVICE,address_width=16,core_parameters=parent.PARAMETERS,field=0,arithmetic_lanes=64,host_lanes=16,
        root_profile_format=3,seed=1,clock_period_ns=8.0,compile_processors=workers,edition='pro',
        required_quartus_version='26.1.0 Build 110 Pro Edition',bitstream_generation=False,allowed_stages=['syn','fit','sta'],
        source_sha256={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()},control_sha256={name:parent.sha(output/name) for name in controls},
        status='small_component_native_pass_matched_sizing_source_only',exemption='component_sizing_probe',
        ancestry='Frozen crtmont-derived A10 point-only successor, not production T5b/current A-next.',
        matched_parent_manifest_sha256='69f75e841081af51ada7173d6dc6f1465b5a9fe17655cd22c7a8c18f1be40da2',
        measured_parent_path_ledger_sha256=candidate.gen.LEDGER_SHA,small_native_reports={f'aw{aw}-f{f}':pin for (aw,f),pin in NATIVE.items()},
        parent_native_AW16_report_sha256=parent.NATIVE_REPORT_SHA,new_child_full_N_native_gate_pending=True,
        source_only_point_ledger=candidate.gen.ledger(16),registered_boundary_recipe_sha256=parent.RECIPE_SHA,
        registered_boundary_receipt=wrapper,wrapper_native_gate_pending=True,wrapper_request_added_edges=1,wrapper_response_added_edges=1,
        isolated_delta='Only point operand/valid launch and corresponding row+half tags add1edge; BF/roots/domain/profile/API unchanged. Newtopname/newemptyproject, samepart/clock/seed/workers/shellrecipe.',
        physical_timing_proven=False,physical_device_verified=False,vendor_executed=False,promotion_allowed=False,
        requested_intermediate_snapshots=True,numeric_full_N_NTT_locally_performed=False,
        timing_scope='One-field internal registered component;8ns target,virtualI/O/resetreleaseexcluded. No whole/auditedclockclaim.')
    with (output/'manifest.json').open('x') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
    return dict(status='prepared_matched_point_launch_sizing_not_dispatched',project=str(output),manifest_sha256=parent.sha(output/'manifest.json'),
        sources=len(files),source_sha256=manifest['source_sha256'],control_sha256=manifest['control_sha256'],native_full_N_pending=True,promotion_allowed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,choices=(4,6),default=6);args=parser.parse_args();print(json.dumps(prepare(args.output,args.workers),indent=2))
