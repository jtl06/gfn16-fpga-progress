"""Source-only selector experiment roles/projects; reuse shared native/fit tools.

MODE0 is a 27-bit frozen-style radix2 selector baseline, MODE1 the canonical
N1 packed-root route, MODE2 the root-local three-source route. No root ROM,
butterfly, whole core, tool invocation or numerical NTT is hidden here.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

from fpga.reference import radix22_root_local_model_v1 as local
from fpga.cloud import plain_fit_v2 as plain

ROOT = Path(__file__).resolve().parents[1]
TOP = 'radix22_selector_probe_v1'
SV = 'rtl/kernel/radix22_selector_probe_v1.sv'
BENCH = 'rtl/tb/radix22_selector_probe_v1.cpp'
HEADER = 'rtl/tb/native_runtime_context_v1.h'
HEADER_PIN = 'afd27444d1b4c991d11c84482db08f2fcef62757968e96ac83c5d44e55622f90'
LOCAL_PIN = '40165e879c1be3275f87a10c7ee63415328e7859e3303bfcef49e080cb75a4c6'
RECEIPT = 'docs/briefs/replies/2026-10-01-B20261001N1G-root-local-model-v1.json'
RECEIPT_PIN = '8cf0bc671b09694916fd6d8b21d5b7723df1baf966d0925fb07485285319a099'
PLAIN_PIN = '6ae141be72ccfdc77b2035d9b7347e5f555b37e94b4d7a7476ccfb3530d9883e'
MODES = {0: 'radix2_baseline', 1: 'canonical_paired', 2: 'local_paired'}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def source_guard():
    local.source_guard()
    for name, pin in [('reference/radix22_root_local_model_v1.py', LOCAL_PIN),
                      (RECEIPT, RECEIPT_PIN), (HEADER, HEADER_PIN), ('cloud/plain_fit_v2.py', PLAIN_PIN)]:
        need(sha(ROOT/name) == pin, 'N1 selector frozen parent/shared pin:'+name)
    return {name: sha(ROOT/name) for name in (SV, BENCH, HEADER, __file__)}


def data_maps(mode, pattern, orientation):
    need(type(mode) is int and mode in MODES and 0 <= pattern < 7 and 0 <= orientation < 4,
         'typed selector mode/control')
    degree = 2 if mode == 0 else 4
    low = (pattern+6)%7
    coordinates = [c for c in range(7) if c != pattern and (mode == 0 or c != low)]
    def bank(lane, index):
        free = sum(((lane >> j)&1) << c for j,c in enumerate(coordinates))
        return free | (index << pattern) if mode == 0 else free | ((index>>1)<<pattern) | ((index&1)<<low)
    read = [bank(i//degree,(i%degree)^(orientation&(degree-1))) for i in range(128)]
    write = [None]*128
    for logical, physical in enumerate(read):
        write[physical] = logical
    need(sorted(read) == sorted(write) == list(range(128)), 'selector bijection/read-write inverse')
    return read, write


def root_indices(mode, pass_sel, xors, root_mask=63, inverse=False):
    need(type(mode) is int and mode in MODES and 0 <= pass_sel < 8 and 0 <= xors < 64
         and 0 <= root_mask < 64 and type(inverse) is bool, 'typed root selector control')
    if mode == 0:
        result = []
        for out in range(64):
            index = out
            for bit in range(6):
                b,m,x = (out>>bit)&1,(root_mask>>bit)&1,(xors>>bit)&1
                if ((not m) or x) if b else (m and x):
                    index ^= 1 << bit
            result.append(index)
        return result+[None]*32
    if mode == 2:
        offset,shift = (0,0) if pass_sel == 0 else (96,2) if pass_sel == 1 else (120,4)
        return [offset+3*(group>>shift)+k for group in range(32) for k in range(3)]
    rows = local.frozen.packed_root_layout()['rows']
    offset = sum(row['packed_words'] for row in rows[:pass_sel])
    streams = rows[pass_sel]['high_streams']
    return [int(inverse)*141+offset+3*((group>>(2*pass_sel) if pass_sel<3 else 0)^(xors&(streams-1)))+k
            for group in range(32) for k in range(3)]


def prepare_roles(output):
    need(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    source_guard()
    output = Path(output)
    need(output.is_absolute() and output.parent.resolve() == output.parent and output.parent.is_dir()
         and not output.exists(), 'fresh canonical selector role output')
    output.mkdir()
    source = output/'source/fpga'
    names = [SV, BENCH, HEADER, 'reference/radix22_selector_experiment_v1.py',
             'reference/radix22_root_local_model_v1.py', RECEIPT]
    pins = {name: sha(ROOT/name) for name in names}
    for name, pin in pins.items():
        destination = source/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, destination)
        need(sha(destination) == pin, 'selector role source copy drift')
    manifests = {}
    for mode, label in MODES.items():
        role = dict(schema='native-source-gate-v1', status='prepared_not_executed',
            host='aethia', cpu_profile='aethia-physical-0-2-v1',
            source_root=str(source), output_parent=str(output), sources=pins,
            build=dict(top=TOP, sv_sources=[SV], cpp_source=BENCH,
                parameters=dict(MODE=mode),
                cflags=['-std=c++17', '-Werror=return-type', f'-DN1_SELECTOR_MODE={mode}'], runtime_threads=1),
            probe=dict(argv=['{exe}', '--runtime-probe'],
                expected_json=dict(context_threads=1, model_threads=1, expected_threads=1)),
            steps=[dict(name='selector-control', argv=['{exe}'], expected_returncode=0,
                expected_stdout=f'N1_SELECTOR_PASS mode={mode} cases=8192 responses=8192 aborts=4 faults=1 threads=1\n',
                expected_stderr=''),
                dict(name='selector-negative', argv=['{exe}', '--negative-selector'], expected_returncode=1,
                     expected_stdout='', expected_stderr='N1_SELECTOR_MISMATCH\n')],
            source_scope='27-bit isolated selector tokens only;8192 geometrical packets,bubbles,fall-edge hold,4launch-cancellation resets,illegal-pattern rejection. No ROM/field arithmetic/NTT/whole core.',
            selector_mode=label, parent_model_sha256=LOCAL_PIN, parent_model_receipt_sha256=RECEIPT_PIN,
            physical_or_whole_core_promotion=False)
        path = output/(label+'-manifest.json')
        save(path, role)
        manifests[label] = dict(path=str(path), sha256=sha(path), mode=mode)
    result = dict(status='prepared_source_only_selector_roles_no_native_execution', manifests=manifests,
        source_root=str(source), sources=pins, preparer_sha256=sha(__file__),
        native_execution=False, vendor_execution=False, promotion_allowed=False)
    save(output/'preparation.json', result)
    return result


def prepare_project(output, mode, workers=4):
    need(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    source_guard()
    need(type(mode) is int and mode in MODES and type(workers) is int and workers in (4,6), 'selector project mode/workers')
    output = Path(output)
    need(output.is_absolute() and output.parent.resolve() == output.parent and output.parent.is_dir()
         and not output.exists(), 'fresh canonical selector project')
    output.mkdir()
    (output/'rtl').mkdir()
    shutil.copyfile(ROOT/SV, output/'rtl/radix22_selector_probe_v1.sv')
    controls = dict(
        **{'probe.qpf': 'QUARTUS_VERSION = "26.1"\nPROJECT_REVISION = "probe"\n'},
        **{'probe.sdc': 'create_clock -name kernel_clk -period 10 [get_ports {clk}]\nderive_clock_uncertainty\n# Reset release and virtual external I/O excluded from component scope.\nset_false_path -from [get_ports {rst_n}]\n'},
        **{'run.tcl': plain.FULL_TCL})
    lines = ['set_global_assignment -name FAMILY "Arria 10"',
        'set_global_assignment -name DEVICE 10AX115N4F40E3SG',
        'set_global_assignment -name TOP_LEVEL_ENTITY '+TOP,
        'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
        'set_global_assignment -name NUM_PARALLEL_PROCESSORS '+str(workers),
        'set_global_assignment -name SEED 1',
        'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON',
        'set_global_assignment -name SDC_FILE probe.sdc',
        'set_global_assignment -name SYSTEMVERILOG_FILE rtl/radix22_selector_probe_v1.sv',
        'set_parameter -name MODE '+str(mode)]
    for name, vector in [('rst_n',False),('in_valid',False),('inverse',False),('pattern',True),('pass_sel',True),
            ('orientation',True),('root_xor',True),('root_mask',True),('data_payload',True),('write_payload',True),
            ('root_payload',True),('out_valid',False),('out_fault',False),('read_result',True),
            ('write_result',True),('root_result',True)]:
        lines.append('set_instance_assignment -name VIRTUAL_PIN ON -to "'+name+('[*]' if vector else '')+'"')
    controls['probe.qsf']='\n'.join(lines)+'\n'
    for name, data in controls.items():
        with (output/name).open('x') as stream:
            stream.write(data)
    manifest=dict(schema='radix22-selector-component-project-v1', target='N1_selector_'+MODES[mode], top=TOP,
        device='10AX115N4F40E3SG', physical_device_verified=False, compile_processors=workers,
        clock_period_ns=10.0, seed=1, edition='pro', bitstream_generation=False, allowed_stages=['syn','fit','sta'],
        core_parameters=dict(MODE=mode), source_sha256={'radix22_selector_probe_v1.sv':sha(output/'rtl/radix22_selector_probe_v1.sv')},
        control_sha256={name:sha(output/name) for name in controls},
        status='prepared_selector_component_not_executed', exemption='component_sizing_probe',
        parent_model_sha256=LOCAL_PIN, parent_model_receipt_sha256=RECEIPT_PIN,
        plain_runner_sha256=PLAIN_PIN, requested_intermediate_snapshots=True,
        measurement_scope='Report whole wrapper and network child ALMs/regs separately; static MODE prunes unused ports. No root ROM/arithmetic/whole-core timing claim.',
        measured_gate='Native typed selector gate then matched10ns seed1 selector sizing: networkALM delta(local-parent) <=1959.7perfield under frozen310024.9floor+4096reserve; report routing/packing rather than promise GO.',
        numeric_full_N_NTT_locally_performed=False, architectural_RTL_GO=False, physical_timing_proven=False, promotion_allowed=False)
    save(output/'manifest.json',manifest)
    return dict(project=str(output),manifest_sha256=sha(output/'manifest.json'),mode=mode,workers=workers,
                source_sha256=manifest['source_sha256'],control_sha256=manifest['control_sha256'],vendor_execution=False)


def prepare_all(output):
    """Data/config preparation through existing pinned shared package API only."""
    from fpga.tools import native_class_package_v2 as package
    from fpga.cloud import host_hours_admit_v1 as meter
    source_guard()
    need(sha(package.__file__) == '03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604',
         'shared class package v2 pin')
    need(sha(meter.__file__) == '6fd1904025f4d76557497dba2eac2a5514b419a799c8616b177bc696f051379a',
         'shared existing host-hours pin')
    output = Path(output)
    need(output.is_absolute() and output.parent.resolve() == output.parent and output.parent.is_dir()
         and not output.exists(), 'fresh canonical complete selector experiment')
    output.mkdir()
    roles = prepare_roles(output/'roles')
    hour = meter.admit('gcp-c4d',3715)
    save(output/'host-hours.json',hour)
    budget = dict(provider='gcp', observed_at=hour['observed_at_utc'], total_allowance_usd=100,
        planning_usd_per_hour=hour['hourly_rate_usd'], remaining_after_reserves_usd=hour['remaining_total_after_storage_usd'],
        actual_billing=False, source_receipt_sha256=sha(output/'host-hours.json'))
    save(output/'budget.json',budget)
    (output/'packets').mkdir()
    jobs = []
    for mode,label in MODES.items():
        variants = []
        for suffix,profile in [('01','gcp-c4d-static01-v1'),('23','gcp-c4d-static23-v1')]:
            worker_id=f'n1-selector-mode{mode}-static{suffix}-v1'
            out=output/'packets'/worker_id
            info=package.prepare(Path(roles['manifests'][label]['path']), Path(roles['source_root']),
                profile,worker_id,'run',out,output/'budget.json')
            variants.append(dict(archive=str(out/'package.tar.gz'), sha256=info['archive_sha256'],
                ticket_sha256=info['ticket_sha256'], manifest_sha256=sha(out/'manifest.json'),
                worker_id=worker_id, profile=profile, native_root=info['native_root'],
                runner='tools/native_class_package_v2.py',runner_sha256=sha(package.__file__),
                stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha(ROOT/'tools/native_package_v4.py'),
                stager_dependencies=[dict(path=str(ROOT/'tools'/name),sha256=sha(ROOT/'tools'/name))
                    for name in ('native_package_v3.py','native_package_v2.py')],max_seconds=3700))
        ticket=dict(schema='gfn16-global-ticket-v1',id=f'n1-selector-mode{mode}-q1-v1',
            candidate_id=f'n1-selector-{label}-v1',owner='radix22-sol',
            created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P2',kind='sim',needs='verilator',
            tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
            resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),est_minutes=3,
            promotion_bound=False,packages=variants,
            source_scope='ONE queued N1 selector-measurement experiment, three independent static modes; P2 behind r54NOW. Token routing only, no ROM/NTT/root arithmetic/core fit.',
            source_gate=dict(model_sha256=LOCAL_PIN,model_receipt_sha256=RECEIPT_PIN,
                selector_SV_sha256=sha(ROOT/SV),selector_CPP_sha256=sha(ROOT/BENCH),
                no_architectural_N1_RTL_GO=True,no_full_N_numeric_local=True))
        path=output/(label+'-global-ticket.json')
        save(path,ticket)
        project=prepare_project(output/('physical-mode'+str(mode)+'-workers6'),mode,6)
        jobs.append(dict(mode=mode,label=label,global_ticket=str(path),global_ticket_sha256=sha(path),
            source_project=project,packages=variants))
    result=dict(status='prepared_N1_selector_only_one_experiment_three_static_roles',jobs=jobs,
        native_execution=False,vendor_execution=False,transfer_attempted=False,
        measurement_incomplete=True,architectural_N1_RTL_GO=False,promotion_allowed=False)
    save(output/'preparation.json',result)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--project-mode',type=int,choices=tuple(MODES))
    parser.add_argument('--workers',type=int,choices=(4,6),default=4)
    parser.add_argument('--all',action='store_true')
    args=parser.parse_args()
    need(not args.all or args.project_mode is None,'one preparation mode')
    value=prepare_all(args.output) if args.all else prepare_roles(args.output) if args.project_mode is None else prepare_project(args.output,args.project_mode,args.workers)
    print(json.dumps(value,indent=2))
