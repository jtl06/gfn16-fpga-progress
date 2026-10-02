"""Normal-first warm-field L3 ladder, exact frozen v4 donor plus leaf binding."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from fpga.reference import stream27_shared_field_v4 as core
from fpga.reference import stream27_montgomery_factored_bind as binding
from fpga.reference.stream27_shared_warm_full_native_v1 import compile_bench,BENCH
from fpga.reference.stream27_p8_warm_native_v2 import lease_ledger
from fpga.tools import native_class_package_v2 as package

ROOT=core.ROOT;SELF='reference/stream27_montgomery_factored_field_native.py'
CPP='rtl/tb/stream27_montgomery_factored_field_normal.cpp'
HEADER='rtl/tb/s4_full_config_v1.h';REFERENCE='rtl/tb/stream27_shared_reference_ntt_v1.h'
PARENT='reference/stream27_shared_field_v4.py'
READY='2026-10-01T19:47:07Z'
def need(ok,why):
    if not ok:raise ValueError(why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def dump(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def field_bundle(aw=5,p=16,field=0):
    need(type(aw) is int and aw in (5,8,16) and type(p) is int and p in (8,16)
         and type(field) is int and field in (0,1,2),'L3_FIELD_GEOMETRY')
    return binding.bind(core.prepare(1<<aw,p,field,mode='warm',contexts=1,allow_full_constants=aw==16))
def role(aw=5,p=16,field=0):
    b=field_bundle(aw,p,field);g=b['geometry'];rows=g['rows'];interval=g['warm_interval']
    groups=([0],[0,interval],[0,interval+16])
    ledgers=[lease_ledger(starts,g['sink_accept'],rows) for starts in groups]
    need(all(not item['rejected'] for item in ledgers),'L3_FIELD_LEASE_GEOMETRY')
    text,header=compile_bench(b,field);marker=f'S4_L3_FIELD_PASS aw={aw} p={p} field={field}'
    need(text.count('S4_SHARED_AW16_PASS')==1,'L3_FIELD_NORMAL_FOOTER')
    text=text.replace('S4_SHARED_AW16_PASS',marker)
    counts=dict(cases=9,frames=9,physical_rows=9*rows,physical_words=9*(1<<aw),eligible_rows=7*rows,
                commits=7*rows,peak_owners=max(item['peak'] for item in ledgers))
    footer=marker+' '+' '.join(f'{k}={v}' for k,v in counts.items())+'\n'
    files={'rtl/'+name:value.encode() for name,value in b['files'].items()}
    files.update({CPP:text.encode(),HEADER:header.encode(),REFERENCE:(ROOT/REFERENCE).read_bytes()})
    for name in b['source_dependencies']:files['lineage/'+name]=(ROOT/name).read_bytes()
    for name in (SELF,'reference/stream27_shared_warm_full_native_v1.py','reference/stream27_p8_warm_native_v2.py',BENCH):
        files['lineage/'+name]=(ROOT/name).read_bytes()
    changed={'rtl/'+name:b['generated_sha256'][name] for name in b['montgomery_factored']['identifier_changes']}
    changed['rtl/'+Path(binding.NEW).name]=binding.NEW_PIN
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/L3-field/fpga',output_parent='/not-a-dispatch-path/L3-field/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=CPP,
            parameters=dict(AW=aw,P=p,CONTEXTS=1),cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='factored-montgomery-warm-field-normal',argv=['{exe}'],expected_returncode=0,
                    expected_stdout=footer,expected_stderr='')],
        test_role='normal',rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',
            candidate_id=f's4-l3-field-aw{aw}-p{p}-f{field}-v1',candidate_source_sha256=sha(canonical(changed)),
            rtl_ready_at_utc=READY,source_snapshot=changed),
        l3_binding=dict(geometry=g,counts=counts,leaf=b['montgomery_factored'],parent=PARENT,
          parent_delta_from_measured_v1='v4 valid-qualified internal start only; no cell or calendar change. Not byte-identical to measured v1 warm field.',
          source_sha256=b['source_sha256'],generated_sha256=b['generated_sha256'],
          scope='One warm field only, independent signed NTT oracle; no CRT/carry/host/wholeP16 fit or new clock claim.'))
    return m,files
def prepare(output,aw,p,field,budget):
    output=Path(output).resolve();need(not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists(),'L3_FIELD_FRESH_PAUSE')
    m,files=role(aw,p,field);source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:f.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m);variants=[]
    for pair in ('01','23'):
        profile=f'gcp-c4d-static{pair}-v1';worker=f's4-l3-field-aw{aw}-p{p}-f{field}-{pair}-v1';packet=output/('packet-'+pair)
        r=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
        variants.append(dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),
          sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
          native_root=r['native_root'],runner='tools/native_class_package_v2.py',
          runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),stager=str(ROOT/'tools/native_package_v3.py'),
          stager_sha256=sha((ROOT/'tools/native_package_v3.py').read_bytes()),
          stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256=sha((ROOT/'tools/native_package_v2.py').read_bytes()))],max_seconds=3700))
    qid=f's4-l3-field-aw{aw}-p{p}-f{field}-normal-q1-v1'
    t=dict(schema='gfn16-global-ticket-v1',id=qid,owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=8 if aw==16 else 4,minimum_ram_rationale='FullN8GiB unchanged envelope; small bounded warm field4GiB exploration, no measured peak claim.',
        est_minutes=10,promotion_bound=False,test_role='normal',packages=variants,rtl_readiness=m['rtl_readiness'])
    if aw==8:t.update(after=[f's4-l3-field-aw5-p{p}-f{field}-normal-q1-v1'],on='PASS_expected_contracts')
    if aw==16:t.update(after=[f's4-l3-field-aw8-p{p}-f{i}-normal-q1-v1' for i in range(3)],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',t)
    return dict(id=qid,ticket=str(output/'global-ticket-v1.json'))
def field_gate_ids(p=16):
    return [f's4-l3-field-aw{aw}-p{p}-f{field}-normal-q1-v1' for aw in (5,8) for field in range(3)]+[f's4-l3-field-aw16-p{p}-f0-normal-q1-v1']
def prepare_project(destination):
    """Immutable source project now; native prerequisites bind at submission."""
    from fpga.cloud.plain_fit_v5 import FULL_TCL
    from fpga.tools import fit_dispatch
    destination=Path(destination).resolve();need(destination.is_relative_to(ROOT) and not destination.exists(),'L3_FIELD_PROJECT_FRESH')
    b=field_bundle(16,16,0);rtl=destination/'rtl';rtl.mkdir(parents=True)
    for name,text in b['files'].items():
        with (rtl/name).open('x') as f:f.write(text)
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE 10AX115N4F40E3SG',
      'set_global_assignment -name TOP_LEVEL_ENTITY '+b['top'],'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
      'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4','set_global_assignment -name SEED 1',
      'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on','set_global_assignment -name SDC_FILE probe.sdc']
    qsf += ['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in b['rtl_sources']]
    qsf += ['set_parameter -name AW 16','set_parameter -name P 16','set_parameter -name CONTEXTS 1']
    ports=['rst_n','in_slot_valid','frame_start','context_enabled','generation_in[*]','live_generation[*]','base_in[*]',
      'epoch_in[*]','correction_epoch[*]','correction_valid','correction_generation[*]','data_in[*]','c0_in[*]','c1_in[*]',
      'out_slot_valid','out_frame_start','out_eligible','out_error','fault_pending','generation_out[*]','data_out[*]',
      'out_epoch[*]','commit_valid','commit_frame_start','commit_generation[*]','commit_epoch[*]','commit_data[*]',
      'owner_count[*]','frame_accept','correction_accept','output_row[*]','cycle_count[*]','frame_count[*]']
    qsf += ['set_instance_assignment -name VIRTUAL_PIN ON -to {'+port+'}' for port in ports]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n',
      'probe.sdc':'create_clock -name kernel_clk -period 10.000 [get_ports {clk}]\nderive_clock_uncertainty\n# Component only; inherited reset-release exclusion.\nset_false_path -from [get_ports {rst_n}]\n',
      'run.tcl':FULL_TCL}
    for name,text in controls.items():
        with (destination/name).open('x') as f:f.write(text)
    manifest=dict(schema='s4-l3-factored-warm-field-sizing-v1',status='source_prepared_native_gates_required',
      top=b['top'],target='s4_l3_factored_warm_p16_f0',edition='pro',device='10AX115N4F40E3SG',compile_processors=4,
      seed=1,clock_period_ns=10,address_width=16,bitstream_generation=False,allowed_stages=['syn','fit','sta'],
      core_parameters=dict(AW=16,P=16,CONTEXTS=1),source_sha256=b['generated_sha256'],
      control_sha256={name:sha(text.encode()) for name,text in controls.items()},intermediate_snapshots=True,
      l3_binding=b['montgomery_factored'],geometry=b['geometry'],native_needed_ids=field_gate_ids(),
      parent=PARENT,parent_delta_from_measured_v1='v4 internal start qualifier only; cell/calendar unchanged; no byte-identical matched-v1 claim.',
      scope='One warm P16 F0 field, leaf-only substitution. No CORR_SERIAL2/CRT/carry/host/wholeP16 GO or inherited whole clock.',
      source_variable_multiplier_delta=0,full_N_numeric_locally_performed=False,promotion_allowed=False)
    dump(destination/'manifest.json',manifest);return fit_dispatch.snapshot(destination)
def submit_project(project):
    from fpga.tools import fit_submit
    requires=[]
    for qid in field_gate_ids():
        path=ROOT/'queue/evidence'/qid/'gate-receipt.json';raw=path.read_bytes();gate=json.loads(raw)
        need(gate['status']=='PASS_expected_contracts' and gate['id']==qid,'L3_FIELD_ACTUAL_NATIVE_GATES')
        requires.append(dict(path=str(path),sha256=sha(raw),fields=dict(status='PASS_expected_contracts',id=qid)))
    return fit_submit.submit(ROOT/'queue/standing-fits','s4-l3-factored-warm-p16-f0-v1',Path(project).resolve(),
        '10',1,dict(azure4=list('abcd'),aws6=list('ab')),'component_probe',dict(exemption='component_sizing_probe'),
        priority=50,requires=requires,track='S',purpose='p16_diet')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--aw',type=int,choices=(5,8,16),required=True)
    p.add_argument('--p',type=int,choices=(8,16),default=16);p.add_argument('--field',type=int,choices=(0,1,2),required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--budget',type=Path,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output,a.aw,a.p,a.field,a.budget)))
