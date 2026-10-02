"""Exact native-passed A10 field0 plus common registered-I/O sizing shell.

Source/project preparation only. No RTL, vendor or full-N numeric execution.
The child remains the isolated crtmont-derived A10 experiment, not T5b/A-next.
Sizing probes are r53 pre-screen-exempt, but fit owner still admits exact
source/tool/version/settings, actual physical slot/RAM/runtime/budget/PAUSE.
"""
import argparse
import hashlib
import json
from pathlib import Path
import types

ROOT = Path(__file__).resolve().parents[1]
DONOR = 'results/throughput-20260929/a10-batch-v1/aw16-f0/packet-01'
DONOR_MANIFEST_SHA = '417f2c0fba931224eeb71609c970359ef629077c54744f82eb453243a6da0f77'
NATIVE_REPORT_SHA = '5010e25afeeb83c0f2e3a115b342391ba73d7e06a3297c071533fc5f1bc84385'
RECIPE = 'tools/registered_probe_recipe_v1.py'
RECIPE_SHA = '9ca0de19a859ca3298c4a06e027f50d4345a47303db9b3d2756c374ba67d1594'
PLAIN = 'cloud/plain_fit_v2.py'
PLAIN_SHA = '6ae141be72ccfdc77b2035d9b7347e5f555b37e94b4d7a7476ccfb3530d9883e'
CHILD = 'genefer_a10_banked27_host16_engine_v1'
CHILD_SHA = 'e430a6ea603fa83909f1c7d732f2610f8f5c5ad764718e5a61f4b07ef14dd6e1'
TOP = 'genefer_a10_registered_field_probe_v1'
PARAMETERS = dict(AW=16, LANES=64, HOST_LANES=16, P=104857601, Q=4190109697)
DEVICE = '10AX115N4F40E3SG'
SDC = '''# Exploratory registered virtual-I/O field only; not a board/whole clock.
create_clock -name kernel_clk -period 8 [get_ports {clk}]
derive_clock_uncertainty
# Reset-release/virtual external I/O timing are outside this component probe.
set_false_path -from [get_ports {rst_n}]
'''


def need(ok, reason):
    if not ok: raise ValueError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_exact(relative, pin, name):
    path = ROOT/relative
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == pin, 'A10_FIELD_SHARED_TOOL_DRIFT ' + relative)
    result = types.ModuleType(name)
    result.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), result.__dict__)
    return result


def source_inputs():
    donor = ROOT/DONOR
    need(sha(donor/'manifest.json') == DONOR_MANIFEST_SHA, 'A10_FIELD_NATIVE_SOURCE_IDENTITY')
    m = json.loads((donor/'manifest.json').read_text())
    need(m['build']['parameters'] == PARAMETERS, 'A10_FIELD_NATIVE_GEOMETRY')
    done = json.loads((ROOT/'queue/done/a10-aw16-f0-batch-v1.json').read_text())
    need(done['result']['queue_report']['report_sha256'] == NATIVE_REPORT_SHA and
         done['result']['properties']['ExecMainStatus'] == '0' and
         done['dependency_gate']['status'] == 'PASS_expected_contracts',
         'A10_FIELD_ACTUAL_NATIVE_GATE')
    source = donor/'capture/source/fpga'
    files = {}
    for name in m['build']['sv_sources']:
        p = source/name
        need(p.is_file() and not p.is_symlink() and p.stat().st_nlink == 1 and sha(p) == m['sources'][name],
             'A10_FIELD_COMPILED_SOURCE_DRIFT ' + name)
        files[Path(name).name] = p.read_bytes()
    need(len(files) == len(m['build']['sv_sources']) == 8, 'A10_FIELD_SOURCE_NAMES')
    recipe = load_exact(RECIPE, RECIPE_SHA, '_a10_registered_recipe')
    # Add one exactly pinned qualified child to a fresh instance of the frozen
    # common recipe. No parent file or shared module dictionary is modified.
    recipe.CHILDREN = dict(recipe.CHILDREN, **{CHILD: CHILD_SHA})
    wrapper, receipt = recipe.generate(files[CHILD+'.sv'], TOP)
    files[TOP+'.sv'] = wrapper.encode()
    return files, receipt


def prepare(output, workers=6):
    need(type(workers) is int and workers in (4,6), 'A10_FIELD_FIT_WORKERS')
    need(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    output = Path(output).resolve()
    need(not output.exists() and output.parent.is_dir(), 'A10_FIELD_FRESH_PROJECT')
    files, wrapper = source_inputs()
    plain = load_exact(PLAIN, PLAIN_SHA, '_a10_plain_fit_recipe')
    controls = {
        'probe.qpf': 'QUARTUS_VERSION = "26.1"\nPROJECT_REVISION = "probe"\n',
        'probe.sdc': SDC,
        'run.tcl': plain.FULL_TCL,
    }
    qsf = [
        'set_global_assignment -name FAMILY "Arria 10"',
        'set_global_assignment -name DEVICE ' + DEVICE,
        'set_global_assignment -name TOP_LEVEL_ENTITY ' + TOP,
        'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
        'set_global_assignment -name NUM_PARALLEL_PROCESSORS ' + str(workers),
        'set_global_assignment -name SEED 1',
        'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON',
        'set_global_assignment -name SDC_FILE probe.sdc',
    ]
    qsf += ['set_parameter -name ' + name + ' ' + str(value) for name,value in PARAMETERS.items()]
    qsf += ['set_global_assignment -name SYSTEMVERILOG_FILE rtl/' + name for name in files]
    qsf += ['set_instance_assignment -name VIRTUAL_PIN ON -to "' + p['name'] + ('[*]' if p['width'] else '') + '"'
            for p in wrapper['ports'] if p['name'] != 'clk']
    controls['probe.qsf'] = '\n'.join(qsf)+'\n'
    output.mkdir()
    (output/'rtl').mkdir()
    for name, raw in files.items():
        with (output/'rtl'/name).open('xb') as stream: stream.write(raw)
    for name, text in controls.items():
        with (output/name).open('x') as stream: stream.write(text)
    manifest = dict(schema='a10-registered-field-sizing-project-v1', target='A10_registered_AW16_L64_F0',
        top=TOP, device=DEVICE, physical_device_verified=False, address_width=16,
        field=0, field_parameters=dict(P=PARAMETERS['P'], Q=PARAMETERS['Q']),
        core_parameters=PARAMETERS, arithmetic_lanes=64, host_lanes=16,
        root_profile_format=3, seed=1, clock_period_ns=8.0, compile_processors=workers,
        edition='pro', required_quartus_version='26.1.0 Build 110 Pro Edition',
        bitstream_generation=False, allowed_stages=['syn','fit','sta'],
        source_sha256={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()},
        control_sha256={name:sha(output/name) for name in controls},
        status='prepared_source_only_component_not_fit_or_clock_qualified',
        exemption='component_sizing_probe', ancestry='isolated canonical crtmont-derived A10; no silent T5b rebase',
        native_AW16_field0_report_sha256=NATIVE_REPORT_SHA, native_source_manifest_sha256=DONOR_MANIFEST_SHA,
        registered_boundary_recipe_sha256=RECIPE_SHA, registered_boundary_receipt=wrapper,
        wrapper_native_gate_pending=True, wrapper_request_added_edges=1,wrapper_response_added_edges=1,
        source_only_pipeline_cost=dict(arithmetic_lanes=64, extra_upper_normalizer_pipes=64,
            root_recurrence_pipes=0, packed_root_M20K_proxy_per_field=194,
            DSP_net_zero_is_unmeasured_hypothesis=True),
        omitted=['Digit conversion','Centered three-field CRT','Post-CRT integer double','Carry/digit image','Whole-core host/control/reset-release/board timing'],
        timing_scope='Internal registered-boundary one-field component at8ns; virtualI/O/resetreleaseexcluded, not usablewholeclock.',
        requested_intermediate_snapshots=True, vendor_executed=False, physical_timing_proven=False,
        promotion_allowed=False, numeric_full_N_NTT_locally_performed=False)
    with (output/'manifest.json').open('x') as stream:
        json.dump(manifest,stream,indent=2);stream.write('\n')
    return dict(status='prepared_A10_component_source_only',project=str(output),
        manifest_sha256=sha(output/'manifest.json'),sources=len(files),source_sha256=manifest['source_sha256'],
        control_sha256=manifest['control_sha256'],wrapper_receipt=wrapper,workers=workers,
        fit_approval_not_conferred=True,native_or_vendor_executed=False,promotion_allowed=False)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,choices=(4,6),default=6)
    args=parser.parse_args()
    print(json.dumps(prepare(args.output,args.workers),indent=2))
