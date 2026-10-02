"""Fresh matched8ns one-field sizing packet after exact upper native gates."""
import argparse
import hashlib
import json
from pathlib import Path
from fpga.reference import a10_point_field_probe_v3 as parent
from fpga.reference import a10_upper_sum_engine_prepare_v2 as candidate

ROOT=candidate.ROOT; base=parent.parent
TOP='genefer_a10_registered_field_probe_upper_sum_v2'
NATIVE={(5,0):'17b4c6e730e7c446a5b70f1f496d9d63b8e9549dc1701bacc4563cff0780daa0',
        (5,1):'23187cbe5f0746d87a124beb5c395e81eb5610793bdb1f202c3a5c42272e402c',
        (5,2):'2dba74a2239d9fe3855f460a71fcb7168edf0c5f9fbfbc5e19b2afb1c6370b4f',
        (8,0):'d8d7dbb9c64e877784b1c011efdda9d9c94a7284b06a0d2941c1514869796eab',
        (8,1):'8ac9f634b23117407fb3701f3c6678bb0abe9c3c9a7a8f3ee87f5e55ecd88c07',
        (8,2):'33c25f2a1b421bcceb382d5a5f9086673df377b4c12829ca840952378a8f9436',
        (16,0):'e9da4f7aee3c19d8c62c1bb407952e20fd00a7a8dc352a0823e0ffd621fd3131',
        (16,1):'313e5aa445b984455b8a8cb1724baa6e8454bdf8aabe1a5c4e44b0f00f27619b',
        (16,2):'3a9011b48f601261fd76ab0af5a091641cb0afd50fe17830e15ed8abfc84d846'}
PAIR_GATES=['d57235bb75cf4af4ffffccedad4d686a2c3b7956b9bfc05b7ad2f7a6e971192d',
            'c3831b38c23f70339e27312a478c77df9e817d27fe2c1b2fd7fdab36e34c5398',
            '39fa9345e9bd20661d258c948fc8130f747340e3188b79761d4771c131a86408']


def source_inputs():
    candidate.verify()
    for (aw,field),pin in NATIVE.items():
        done=json.loads((ROOT/'queue/done'/f'a10-upper-engine-aw{aw}-f{field}-q1-v2.json').read_text())
        candidate.gen.need(done['result']['queue_report']['report_sha256']==pin and
            done['dependency_gate']['status']=='PASS_expected_contracts' and done['result']['properties']['ExecMainStatus']=='0',
            'A10_UPPER_ACTUAL_CONNECTED_GATES')
    for field,pin in enumerate(PAIR_GATES):
        path=ROOT/'queue/evidence'/f'a10-upper-sum-f{field}-q1-v2/gate-receipt.json'
        candidate.gen.need(base.sha(path)==pin and json.loads(path.read_text())['status']=='PASS_expected_contracts',
                           'A10_UPPER_ACTUAL_PAIRED_BF_GATES')
    files,_=parent.source_inputs();files.pop(parent.TOP+'.sv')
    for old,new in ((candidate.gen.PARENT,candidate.gen.TARGET),(candidate.gen.POINT,candidate.gen.ENGINE)):
        files.pop(Path(old).name);files[Path(new).name]=(ROOT/new).read_bytes()
    recipe=base.load_exact(base.RECIPE,base.RECIPE_SHA,'_upper_registered_recipe')
    recipe.CHILDREN=dict(recipe.CHILDREN,**{base.CHILD:base.CHILD_SHA})
    wrapper,receipt=recipe.generate(files[base.CHILD+'.sv'],TOP);files[TOP+'.sv']=wrapper.encode()
    return files,receipt


def prepare(output,workers=6):
    candidate.gen.need(type(workers) is int and workers in (4,6),'A10_UPPER_FIT_WORKERS')
    candidate.gen.need(not (ROOT/'docs/briefs/PAUSE').exists(),'A10_UPPER_FIT_PAUSE')
    output=Path(output).resolve();candidate.gen.need(not output.exists(),'A10_UPPER_FRESH_PROJECT')
    files,wrapper=source_inputs();plain=base.load_exact(base.PLAIN,base.PLAIN_SHA,'_upper_plain')
    controls={'probe.qpf':'QUARTUS_VERSION = "26.1"\nPROJECT_REVISION = "probe"\n','probe.sdc':base.SDC,'run.tcl':plain.FULL_TCL}
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE '+base.DEVICE,
         'set_global_assignment -name TOP_LEVEL_ENTITY '+TOP,'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
         'set_global_assignment -name NUM_PARALLEL_PROCESSORS '+str(workers),'set_global_assignment -name SEED 1',
         'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON','set_global_assignment -name SDC_FILE probe.sdc']
    qsf+=['set_parameter -name '+name+' '+str(value) for name,value in base.PARAMETERS.items()]
    qsf+=['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in files]
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to "'+p['name']+('[*]' if p['width'] else '')+'"' for p in wrapper['ports'] if p['name']!='clk']
    controls['probe.qsf']='\n'.join(qsf)+'\n';output.mkdir(parents=True);(output/'rtl').mkdir()
    for name,raw in files.items():
        with (output/'rtl'/name).open('xb') as stream:stream.write(raw)
    for name,text in controls.items():
        with (output/name).open('x') as stream:stream.write(text)
    manifest=dict(schema='a10-upper-sum-field-sizing-project-v2',target='A10_upper_sum_registered_AW16_L64_F0',
        top=TOP,device=base.DEVICE,address_width=16,core_parameters=base.PARAMETERS,field=0,
        arithmetic_lanes=64,host_lanes=16,root_profile_format=3,seed=1,clock_period_ns=8.0,
        compile_processors=workers,edition='pro',required_quartus_version='26.1.0 Build 110 Pro Edition',
        bitstream_generation=False,allowed_stages=['syn','fit','sta'],
        source_sha256={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()},
        control_sha256={name:base.sha(output/name) for name in controls},
        status='full_size_connected_component_native_pass_source_only_sizing',exemption='component_sizing_probe',
        ancestry='Canonical A10 explicit point+upper-launch isolated successor; not current production T5b or fitting A-next.',
        matched_parent_manifest_sha256='99816830cde736bbade38a841fc962dcb735e81af7e84f846f1bf8349a862ec0',
        measured_parent_STA_SHA256=candidate.gen.STA_SHA,measured_parent_path_ledger_SHA256=candidate.gen.PATH_LEDGER_SHA,
        native_connected_reports={f'aw{aw}-f{field}':pin for (aw,field),pin in NATIVE.items()},paired_cell_gate_SHA256=PAIR_GATES,
        native_full_N_child_verified=True,source_only_cell_ledger=candidate.gen.ledger(),
        source_only_engine_ledger=candidate.small.gen.ledger(16),
        isolated_delta='Upper canonical sum+rhs launch replaces one outputalignment stage; raw engine singlecellbinding only. Samek+5/II1 and pointparent cycles,source BF mathematical outputs confirmed all3fields.',
        registered_boundary_recipe_sha256=base.RECIPE_SHA,registered_boundary_receipt=wrapper,
        wrapper_native_gate_pending=True,wrapper_request_added_edges=1,wrapper_response_added_edges=1,
        promotion_allowed=False,physical_timing_proven=False,physical_device_verified=False,vendor_executed=False,
        requested_intermediate_snapshots=True,numeric_full_N_NTT_locally_performed=False,
        timing_scope='Matched onefield registered8ns component, virtualI/O/resetreleaseexcluded; no whole/auditedclock.')
    with (output/'manifest.json').open('x') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
    return dict(project=str(output),manifest_sha256=base.sha(output/'manifest.json'),sources=len(files),
        source_sha256=manifest['source_sha256'],control_sha256=manifest['control_sha256'],
        status='prepared_matched_upper_sum_field_not_dispatched',promotion_allowed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,choices=(4,6),default=6);args=parser.parse_args()
    print(json.dumps(prepare(args.output,args.workers),indent=2))
