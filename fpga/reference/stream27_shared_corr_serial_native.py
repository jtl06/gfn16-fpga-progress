"""Normal-first shared-field native ladder for CORR_SERIAL_BFS=2.

Only source/constants and scalar lease calendars run on the coordinator.
Independent iterative NTT (small schoolbook selfcheck) and all actual RTL
word/tag/calendar checks execute on the admitted native worker.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from fpga.reference import stream27_shared_field_v5 as core
from fpga.reference.stream27_shared_warm_full_native_v1 import compile_bench
from fpga.reference.stream27_p8_warm_native_v2 import lease_ledger
from fpga.tools import native_class_package_v2 as package
from fpga.tools import native_class_v1 as executor

ROOT=core.ROOT
SELF='reference/stream27_shared_corr_serial_native.py'
CPP='rtl/tb/stream27_shared_corr_serial_normal.cpp'
HEADER='rtl/tb/s4_full_config_v1.h'
REFERENCE='rtl/tb/stream27_shared_reference_ntt_v1.h'


def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def dump(path,x):
    with path.open('x') as stream:json.dump(x,stream,indent=2);stream.write('\n')


def role(aw=5,p=16,field=0,*,comm_stage_shared_mlab=0,mont_factored=0):
    core.need(type(aw) is int and aw in (5,8,16) and type(p) is int and p in (8,16)
              and type(field) is int and 0<=field<3,'S4_CORR_SERIAL_NATIVE_GEOMETRY')
    composed=bool(comm_stage_shared_mlab or mont_factored)
    core.need((comm_stage_shared_mlab,mont_factored) in ((0,0),(1,1)),
              'S4_DIET_FIELD_EXPLICIT_COMPOSITION')
    if composed:
        from fpga.reference import stream27_shared_field_flags as flags
        b=flags.prepare(1<<aw,p,field,mode='warm',contexts=1,allow_full_constants=aw==16,
            corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1)
    else:
        b=core.prepare(1<<aw,p,field,mode='warm',contexts=1,allow_full_constants=aw==16,corr_serial_bfs=2)
    g=b['geometry'];rows=g['rows'];interval=g['warm_interval']
    groups=([0],[0,interval],[0,interval+16])
    ledgers=[lease_ledger(starts,g['sink_accept'],rows) for starts in groups]
    core.need(all(not l['rejected'] for l in ledgers),'S4_CORR_SERIAL_NATIVE_LEASE')
    peak=max(l['peak'] for l in ledgers)
    text,header=compile_bench(b,field)
    marker=f'S4_{"DIET" if composed else "CORR_SERIAL"}_FIELD_PASS aw={aw} p={p} field={field}'
    text=text.replace('S4_SHARED_AW16_PASS',marker)
    anchor='counts.peak=std::max(counts.peak,unsigned(d.owner_count));'
    core.need(text.count(anchor)==1,'S4_CORR_SERIAL_NATIVE_OWNERS_ANCHOR')
    text=text.replace(anchor,'''unsigned expected_owners=0;
        for(const auto& f:frames)expected_owners+=tick>=f.start && tick<f.start+SINK+T-1;
        need(unsigned(d.owner_count)==expected_owners,"S4_CORR_SERIAL_FIELD_OWNER_EDGE tick="+std::to_string(tick));
        counts.peak=std::max(counts.peak,unsigned(d.owner_count));''')
    counts=dict(cases=9,frames=9,physical_rows=9*rows,physical_words=9*(1<<aw),eligible_rows=7*rows,commits=7*rows,peak_owners=peak)
    footer=marker+' '+' '.join(f'{k}={v}' for k,v in counts.items())+'\n'
    files={'rtl/'+name:value.encode() for name,value in b['files'].items()}
    files.update({CPP:text.encode(),HEADER:header.encode(),REFERENCE:(ROOT/REFERENCE).read_bytes()})
    for path in b['source_dependencies']:
        files['lineage/'+path]=(ROOT/path).read_bytes()
    files['lineage/'+SELF]=(ROOT/SELF).read_bytes()
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/not-a-dispatch-path/corr-serial-field/fpga',output_parent='/not-a-dispatch-path/corr-serial-field/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=CPP,
            parameters={name:value for name,value in b['parameters'].items() if name!='FIELD'},
            cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='corr-serial-shared-field-normal',argv=['{exe}'],expected_returncode=0,expected_stdout=footer,expected_stderr='')],
        correction_serial=dict(flag=2,geometry=g,counts=counts,lease_ledger=ledgers,
            composition=dict(COMM_STAGE_SHARED_MLAB=comm_stage_shared_mlab,MONT_FACTORED=mont_factored),
            source_sha256=b['source_sha256'],generated_sha256=b['generated_sha256'],
            full_N_numeric_locally_performed=False,scope='Shared one-field correction serialization numeric/tag/calendar gate; not three-field/carry/host/PRP or whole-fit qualification.'))
    return m,files


def prepare(output,aw,p,field,budget,*,comm_stage_shared_mlab=0,mont_factored=0):
    output=Path(output).resolve();core.need(not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists(),'S4_CORR_SERIAL_NORMAL_FRESH_PAUSE')
    m,files=role(aw,p,field,comm_stage_shared_mlab=comm_stage_shared_mlab,mont_factored=mont_factored)
    family='diet' if comm_stage_shared_mlab else 'corr'
    ready=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m);variants=[]
    for pair in ('01','23'):
        profile=f'gcp-c4d-static{pair}-v1';worker=f's4-{family}-field-aw{aw}-p{p}-f{field}-{pair}-v1';packet=output/('packet-'+pair)
        r=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
        variants.append(dict(profile=profile,worker_id=worker,packet=str(packet),archive=str(packet/'package.tar.gz'),
            sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
            native_root=r['native_root'],build_key=r['build_key'],archive_bytes=r['archive_bytes'],
            resource_profile_sha256=sha(canonical(executor.profile(profile))),runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),stager=str(ROOT/'tools/native_package_v3.py'),
            stager_sha256=sha((ROOT/'tools/native_package_v3.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256=sha((ROOT/'tools/native_package_v2.py').read_bytes()))],max_seconds=3700))
    qid=f's4-{family}-field-aw{aw}-p{p}-f{field}-normal-q1-v1'
    changed={'rtl/'+m['build']['top']+'.sv':m['sources']['rtl/'+m['build']['top']+'.sv']}
    t=dict(schema='gfn16-global-ticket-v1',id=qid,owner='stream-core',created=ready,priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=8 if aw==16 else 4,
        minimum_ram_rationale='FullN requires8GiB; small bounded field4GiB exploratory allowance, no measured peak; preserve failures.',
        est_minutes=10,promotion_bound=False,test_role='normal',packages=variants,
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id=f's4-{family}-field-aw{aw}-p{p}-f{field}-v1',
            candidate_source_sha256=sha(canonical(changed)),rtl_ready_at_utc=ready,source_snapshot=changed))
    if aw!=5:t.update(after=[f's4-{family}-field-aw{5 if aw==8 else 8}-p{p}-f{field}-normal-q1-v1'],on='PASS_expected_contracts')
    if aw==16 and family=='diet':t['after']=[f's4-diet-field-aw8-p{p}-f{i}-normal-q1-v1' for i in range(3)]
    dump(output/'global-ticket-v1.json',t);dump(output/'preparation.json',dict(status='source_ready_not_dispatched',id=qid,geometry=m['correction_serial']['geometry']))
    return dict(status='source_ready_not_dispatched',id=qid)


def prepare_project(destination,*,comm_stage_shared_mlab=0,mont_factored=0):
    """Source-identical full-N warm F0 sizing; not a whole-P16 GO."""
    from fpga.cloud.plain_fit_v5 import FULL_TCL
    from fpga.tools import fit_dispatch
    destination=Path(destination).resolve()
    core.need(destination.is_relative_to(ROOT) and not destination.exists()
              and not (ROOT/'docs/briefs/PAUSE').exists(),'S4_CORR_FIELD_FIT_FRESH_PAUSE')
    composed=bool(comm_stage_shared_mlab or mont_factored)
    core.need((comm_stage_shared_mlab,mont_factored) in ((0,0),(1,1)),
              'S4_DIET_FIELD_EXPLICIT_COMPOSITION')
    if composed:
        from fpga.reference import stream27_shared_field_flags as flags
        b=flags.prepare(65536,16,0,mode='warm',contexts=1,allow_full_constants=True,
            corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1)
    else:
        b=core.prepare(65536,16,0,mode='warm',contexts=1,allow_full_constants=True,corr_serial_bfs=2)
    family='diet' if composed else 'corr'
    captured=ROOT/f'results/throughput-20260929/s4-{family}-field-aw16-p16-f0-normal-v1/input/manifest.json'
    native=json.loads(captured.read_text())
    core.need(b['generated_sha256']==native['correction_serial']['generated_sha256'],
              'S4_CORR_FIELD_FIT_NATIVE_RTL_JOIN')
    rtl=destination/'rtl';rtl.mkdir(parents=True)
    for name,text in b['files'].items():
        with (rtl/name).open('x') as stream:stream.write(text)
    qsf=['set_global_assignment -name FAMILY "Arria 10"',
        'set_global_assignment -name DEVICE 10AX115N4F40E3SG',
        'set_global_assignment -name TOP_LEVEL_ENTITY '+b['top'],
        'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
        'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4',
        'set_global_assignment -name SEED 1',
        'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON',
        'set_global_assignment -name SDC_FILE probe.sdc']
    qsf+=['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in b['rtl_sources']]
    params={name:value for name,value in b['parameters'].items() if name!='FIELD'}
    qsf+=['set_parameter -name '+name+' '+str(value) for name,value in params.items()]
    ports=['rst_n','in_slot_valid','frame_start','context_enabled','generation_in[*]',
        'live_generation[*]','base_in[*]','epoch_in[*]','correction_epoch[*]',
        'correction_valid','correction_generation[*]','data_in[*]','c0_in[*]','c1_in[*]',
        'out_slot_valid','out_frame_start','out_eligible','out_error','fault_pending',
        'generation_out[*]','data_out[*]','out_epoch[*]','commit_valid','commit_frame_start',
        'commit_generation[*]','commit_epoch[*]','commit_data[*]','owner_count[*]',
        'frame_accept','correction_accept','output_row[*]','cycle_count[*]','frame_count[*]']
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to {'+port+'}' for port in ports]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n',
        'probe.sdc':'create_clock -name kernel_clk -period 10.000 [get_ports {clk}]\nderive_clock_uncertainty\n# Component sizing only; inherited reset-release exclusion.\nset_false_path -from [get_ports {rst_n}]\n',
        'run.tcl':FULL_TCL}
    for name,text in controls.items():
        with (destination/name).open('x') as stream:stream.write(text)
    manifest=dict(schema='s4-corr-serial-warm-field-sizing-v1',
        status='source_prepared_native_gate_required',top=b['top'],edition='pro',
        device='10AX115N4F40E3SG',compile_processors=4,seed=1,clock_period_ns=10,
        address_width=16,bitstream_generation=False,allowed_stages=['syn','fit','sta'],
        core_parameters=params,
        source_sha256=b['generated_sha256'],
        control_sha256={name:sha(text.encode()) for name,text in controls.items()},
        intermediate_snapshots=True,geometry=b['geometry'],
        qualified_native_manifest=dict(path=str(captured),sha256=sha(captured.read_bytes())),
        parent='reference/stream27_shared_field_v4.py',
        scope=('One full-N warm P16 F0 field, composed L1/P1P2/L3a flags; frozen normalized Montgomery consumers retained. No CRT/carry/host/two-context/wholeP16 GO or clock inheritance.' if composed else
               'One full-N warm P16 F0 field, CORR_SERIAL_BFS2 only; no shared-comm/MLAB/factored-Montgomery/CRT/carry/host/two-context/wholeP16 or clock inheritance.'),
        full_N_numeric_locally_performed=False,promotion_allowed=False)
    dump(destination/'manifest.json',manifest)
    return fit_dispatch.snapshot(destination)


def submit_project(project,*,comm_stage_shared_mlab=0,mont_factored=0):
    from fpga.tools import fit_submit
    composed=bool(comm_stage_shared_mlab or mont_factored)
    core.need((comm_stage_shared_mlab,mont_factored) in ((0,0),(1,1)),
              'S4_DIET_FIELD_EXPLICIT_COMPOSITION')
    qid=f's4-{"diet" if composed else "corr"}-field-aw16-p16-f0-normal-q1-v1'
    path=ROOT/'queue/evidence'/qid/'gate-receipt.json';gate=json.loads(path.read_text())
    core.need(gate['status']=='PASS_expected_contracts' and gate['id']==qid,'S4_CORR_FIELD_ACTUAL_GATE')
    requires=[dict(path=str(path),sha256=sha(path.read_bytes()),
                   fields=dict(status='PASS_expected_contracts',id=qid))]
    return fit_submit.submit(ROOT/'queue/standing-fits',
        's4-diet-warm-p16-f0-v1' if composed else 's4-corr-serial-warm-p16-f0-v1',
        Path(project).resolve(),'10',1,dict(azure4=list('abcd'),aws6=list('ab')),
        'component_probe',dict(exemption='component_sizing_probe'),priority=50,
        requires=requires,track='S',purpose='p16_diet')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--aw',type=int,choices=(5,8,16),required=True)
    parser.add_argument('--p',type=int,choices=(8,16),required=True);parser.add_argument('--field',type=int,choices=(0,1,2),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    parser.add_argument('--comm-shared-mlab',type=int,choices=(0,1),default=0)
    parser.add_argument('--mont-factored',type=int,choices=(0,1),default=0)
    a=parser.parse_args();print(json.dumps(prepare(a.output,a.aw,a.p,a.field,a.budget,
        comm_stage_shared_mlab=a.comm_shared_mlab,mont_factored=a.mont_factored)))
