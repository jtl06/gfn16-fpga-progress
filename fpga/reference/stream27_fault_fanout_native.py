"""Normal-first native P8 field replica roles using existing queue packaging.

Independent signed NTT/reference calendar is inherited verbatim from its
frozen normal harness. Only the actual field's same-edge replica binding and
normal label change. No native execution or full-N numerical work on the Mac.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from . import stream27_shared_field_flags as donor
from . import stream27_fault_fanout_bind as binding
from .stream27_shared_warm_full_native_v1 import compile_bench,BENCH
from .stream27_p8_warm_native_v2 import lease_ledger

ROOT=donor.ROOT
SELF='reference/stream27_fault_fanout_native.py'
CPP='rtl/tb/stream27_fault_fanout_normal.cpp'
HEADER='rtl/tb/s4_full_config_v1.h'
REFERENCE='rtl/tb/stream27_shared_reference_ntt_v1.h'
# First source/model completion declaration; package materialization and the
# dispatcher's accepted normal-submission timestamp are separate later events.
RTL_READY='2026-10-01T22:01:42Z'


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def dump(path,value):
    with Path(path).open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def field_bundle(aw=8,field=2,*,boundary_inputreg=0):
    need(type(aw) is int and aw in (8,16) and type(field) is int and field in (0,1,2),
         'S4_FAULT_FANOUT_NORMAL_GEOMETRY')
    parent=donor.prepare(1<<aw,8,field,mode='warm_signed',contexts=1,
                         allow_full_constants=aw==16,boundary_inputreg=boundary_inputreg)
    return binding.bind(parent)


def role(aw=8,field=2,*,boundary_inputreg=0):
    b=field_bundle(aw,field,boundary_inputreg=boundary_inputreg);g=b['geometry'];rows=g['rows']
    groups=([0],[0,g['warm_interval']],[0,g['warm_interval']+16])
    ledgers=[lease_ledger(starts,g['sink_accept'],rows) for starts in groups]
    need(all(not item['rejected'] for item in ledgers),'S4_FAULT_FANOUT_REAL_LEASE_CALENDAR')
    cpp,header=compile_bench(b,field)
    label=f'S4_FAULT_FANOUT_NORMAL aw={aw} p=8 field={field} boundary_inputreg={boundary_inputreg}'
    need(cpp.count('S4_SHARED_AW16_PASS')==1,'S4_FAULT_FANOUT_NORMAL_LABEL')
    cpp=cpp.replace('S4_SHARED_AW16_PASS',label,1)
    counts=dict(cases=9,frames=9,physical_rows=9*rows,physical_words=9*(1<<aw),
                eligible_rows=7*rows,commits=7*rows,peak_owners=max(x['peak'] for x in ledgers))
    footer=label+' '+' '.join(f'{key}={value}' for key,value in counts.items())+'\n'
    files={'rtl/'+name:value.encode() for name,value in b['files'].items()}
    files.update({CPP:cpp.encode(),HEADER:header.encode(),REFERENCE:(ROOT/REFERENCE).read_bytes()})
    for name in b['source_dependencies']:files['lineage/'+name]=(ROOT/name).read_bytes()
    for name in (SELF,'reference/stream27_shared_warm_full_native_v1.py','reference/stream27_p8_warm_native_v2.py',BENCH):
        files['lineage/'+name]=(ROOT/name).read_bytes()
    snapshot={'rtl/'+b['top']+'.sv':b['generated_sha256'][b['top']+'.sv'],
              'rtl/'+Path(binding.LEAF).name:b['generated_sha256'][Path(binding.LEAF).name]}
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',
        source_root='/unbound/fault-fanout/fpga',output_parent='/unbound/fault-fanout/output',
        sources={name:sha(raw) for name,raw in files.items()},
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=CPP,
                   parameters={key:value for key,value in b['parameters'].items() if key!='FIELD'},
                   cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='s4-p8-field-fault-fanout-normal',argv=['{exe}'],expected_returncode=0,
                    expected_stdout=footer,expected_stderr='')],test_role='normal',
        fault_fanout=dict(binding=b['fault_fanout'],geometry=g,counts=counts,
                         source_sha256=b['source_sha256'],generated_sha256=b['generated_sha256'],
                         scope='One real P8 field, nine actual arithmetic/lease cases plus normal reset/origin fault; no three-field/carry/host/clock qualification.'))
    return manifest,files,snapshot


def prepare(output,aw,field,budget,*,boundary_inputreg=0):
    """Emit finite immutable normal role and initial admitted GCP variant.

    Public queue submission emits every compatible admitted lane variant;
    this helper does not reserve resources, start workers or change guards.
    """
    from fpga.tools import native_class_package_v2 as package
    output=Path(output).resolve()
    need(not output.exists() and not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')),
         'S4_FAULT_FANOUT_FRESH_PAUSE')
    m,files,snapshot=role(aw,field,boundary_inputreg=boundary_inputreg)
    ready=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    m['rtl_readiness']=dict(schema='gfn16-candidate-rtl-ready-v1',
        candidate_id=f's4-p8-fault-fanout-aw{aw}-f{field}-b{boundary_inputreg}-v1',
        candidate_source_sha256=sha(canonical(snapshot)),rtl_ready_at_utc=RTL_READY,source_snapshot=snapshot)
    source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest=output/'input/manifest.json';dump(manifest,m)
    qid=f's4-p8-fault-fanout-aw{aw}-f{field}-b{boundary_inputreg}-normal-q1-v1'
    profile='gcp-c4d-static01-v1';worker=qid+'-01';packet=output/'packet-01'
    result=package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
    variant=dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),
        sha256=result['archive_sha256'],ticket_sha256=result['ticket_sha256'],
        manifest_sha256=sha((packet/'manifest.json').read_bytes()),native_root=result['native_root'],
        runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
        stager=str(ROOT/'tools/native_package_v3.py'),stager_sha256=sha((ROOT/'tools/native_package_v3.py').read_bytes()),
        stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256=sha((ROOT/'tools/native_package_v2.py').read_bytes()))],
        max_seconds=3700)
    ticket=dict(schema='gfn16-global-ticket-v1',id=qid,owner='fault-fanout',created=ready,
        priority='P1',kind='sim',needs='verilator',tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8 if aw==16 else 4,
        minimum_ram_rationale='Small bounded field uses existing4GiB exploration envelope; fullN preserves8GiB. No measured peak claim.',
        est_minutes=10,promotion_bound=False,test_role='normal',packages=[variant],rtl_readiness=m['rtl_readiness'])
    if aw==16:
        ticket.update(after=[f's4-p8-fault-fanout-aw8-f{field}-b{boundary_inputreg}-normal-q1-v1'],
                      on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket)
    return dict(status='normal_source_prepared_not_submitted',id=qid,ticket=str(output/'global-ticket-v1.json'),
                manifest_sha256=sha(manifest.read_bytes()),top=m['build']['top'],counts=m['fault_fanout']['counts'])


def prepare_project(destination):
    """Source-only field2 fit snapshot; no exceptions or timing claims."""
    from fpga.cloud.plain_fit_v5 import FULL_TCL
    from fpga.tools import fit_dispatch
    destination=Path(destination).resolve()
    need(destination.is_relative_to(ROOT) and not destination.exists(),'S4_FAULT_FANOUT_PROJECT_FRESH')
    b=field_bundle(16,2);rtl=destination/'rtl';rtl.mkdir(parents=True)
    for name,text in b['files'].items():
        with (rtl/name).open('x') as stream:stream.write(text)
    qsf=['set_global_assignment -name FAMILY "Arria 10"',
         'set_global_assignment -name DEVICE 10AX115N4F40E3SG',
         'set_global_assignment -name TOP_LEVEL_ENTITY '+b['top'],
         'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
         'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4',
         'set_global_assignment -name SEED 1',
         'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on',
         'set_global_assignment -name SDC_FILE probe.sdc']
    qsf += ['set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name for name in b['rtl_sources']]
    parameters={key:value for key,value in b['parameters'].items() if key!='FIELD'}
    qsf += [f'set_parameter -name {key} {value}' for key,value in parameters.items()]
    ports=['rst_n','in_slot_valid','frame_start','context_enabled','generation_in[*]','live_generation[*]',
           'base_in[*]','epoch_in[*]','correction_epoch[*]','correction_valid','correction_generation[*]',
           'data_in[*]','c0_in[*]','c1_in[*]','out_slot_valid','out_frame_start','out_eligible','out_error',
           'fault_pending','generation_out[*]','data_out[*]','out_epoch[*]','commit_valid','commit_frame_start',
           'commit_generation[*]','commit_epoch[*]','commit_data[*]','owner_count[*]','frame_accept',
           'correction_accept','output_row[*]','cycle_count[*]','frame_count[*]']
    qsf += ['set_instance_assignment -name VIRTUAL_PIN ON -to {'+port+'}' for port in ports]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n',
              'probe.sdc':'create_clock -name kernel_clk -period 10.000 [get_ports {clk}]\nderive_clock_uncertainty\n',
              'run.tcl':FULL_TCL}
    for name,text in controls.items():
        with (destination/name).open('x') as stream:stream.write(text)
    m=dict(schema='s4-p8-fault-fanout-field-probe-v1',status='source_prepared_native_gate_pending',
        top=b['top'],edition='pro',device='10AX115N4F40E3SG',compile_processors=4,seed=1,
        clock_period_ns=10,address_width=16,bitstream_generation=False,allowed_stages=['syn','fit','sta'],
        core_parameters=parameters,raw_multiplier_parameters=None,field_parameters=None,
        source_sha256=b['generated_sha256'],control_sha256={name:sha(text.encode()) for name,text in controls.items()},
        preparation_source_sha256=b['source_sha256'],geometry=b['geometry'],fault_fanout=b['fault_fanout'],
        native_source_gate='s4-p8-fault-fanout-aw16-f2-b0-normal-q1-v1',
        parent='Exact field2 root/children from captured canonical1 whole; only two transform-local fault copies.',
        scope='One-field virtual-pin 10ns physical measurement. No false paths, whole benefit, reset-release sign-off or promotion.',
        promotion_allowed=False)
    dump(destination/'manifest.json',m)
    return fit_dispatch.snapshot(destination)


def submit_project(project):
    from fpga.tools import fit_submit
    return fit_submit.submit(ROOT/'queue/standing-fits','s4-p8-fault-fanout-field2-10000-v1',
        Path(project).resolve(),'10',1,dict(azure4=list('abcd'),aws6=list('ab')),
        'component_probe',dict(exemption='component_sizing_probe'),priority=45,track='S',purpose='clock_push',
        native_source_gate='s4-p8-fault-fanout-aw16-f2-b0-normal-q1-v1')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--budget',type=Path,required=True);parser.add_argument('--aw',type=int,choices=(8,16),default=8)
    parser.add_argument('--field',type=int,choices=(0,1,2),default=2);parser.add_argument('--boundary-inputreg',type=int,choices=(0,1),default=0)
    args=parser.parse_args()
    print(json.dumps(prepare(args.output,args.aw,args.field,args.budget,boundary_inputreg=args.boundary_inputreg),indent=2))
