"""Prepare source-pinned private-copy native qualification; no cloud execution."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

FPGA = Path(__file__).resolve().parents[1]
ROOT = '/home/azureuser/gfn16-worker'
TOOLS = ROOT+'/quartus-prefit-qualification-tools-v1'
HELPERS = ['cloud/azure_prefit_diagnostic_v1.py', 'tools/quartus_prefit_native_v1.py',
           'synthesis/prefit_design_assistant_v1.tcl', 'synthesis/postplace_timing_diagnostic_v1.tcl']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination, mode, attempt):
    destination.mkdir(parents=True, exist_ok=False)
    baseline = FPGA/'results/throughput-20260929/crt27-mont-hostbench-azure-v1/project'
    context = json.loads((baseline/'execution-context.json').read_text())
    manifest = json.loads((baseline/'manifest.json').read_text())
    tools = dict(context['azure_admission']['tool_sha256'])
    wrapper = tools[ROOT+'/altera_pro/26.1/quartus/bin/quartus_sh']
    tools.update({ROOT+'/altera_pro/26.1/quartus/bin/'+name: wrapper for name in ('quartus_syn', 'quartus_sta')})
    spec = dict(scope='component_probe', sources={'rtl/'+name: pin for name, pin in context['source_sha256'].items()},
        settings={name: sha(baseline/name) for name in context['control_sha256']},
        identity=dict(top=manifest['top'], device=manifest['device'], parameters=manifest['core_parameters'], clock_period_ns=10, seed=manifest['seed']),
        selected_clock='kernel_clk', vendor_tool_sha256=tools)
    for name, pin in spec['sources'].items():
        if sha(baseline/name) != pin:
            raise ValueError('source baseline drift')
    unit = f'gfn16-azure-prefit-{mode}-v{attempt}.service'
    packet = dict(schema='azure-prefit-diagnostic-packet-v1', mode=mode, spec=spec,
        job_id=f'azure-prefit-{mode}-v{attempt}', unit=unit, original_project=ROOT+'/crt27-mont-azure-hostbench-v1',
        destination=ROOT+f'/quartus-prefit-azure-diag-v{attempt}', pause_path=ROOT+'/PAUSE',
        manifest_sha256=context['manifest_sha256'], benchmark_context_sha256=sha(baseline/'execution-context.json'),
        benchmark_result_sha256=sha(baseline/'execution-result.json'), benchmark_final_guard_sha256=sha(baseline/'azure-final-guard.json'),
        tool_sha256=tools, helper_sha256={TOOLS+'/fpga/'+name: sha(FPGA/name) for name in HELPERS},
        parser_path=TOOLS+'/fpga/tools/quartus_prefit_native_v1.py', capture_netlist_help=(mode == 'da'))
    packet['payload_sha256'] = hashlib.sha256(json.dumps(packet, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    (destination/'payload.json').write_text(json.dumps(packet, indent=2)+'\n')
    request = dict(schema='fit-budget-request-v1', job_id=packet['job_id'], host_id='azure-f16',
                   manifest_sha256=packet['manifest_sha256'], packet_sha256=packet['payload_sha256'],
                   outer_runtime_max_seconds=840, stop_grace_seconds=60)
    (destination/'budget-request.json').write_text(json.dumps(request, indent=2)+'\n')
    with tarfile.open(destination/'helpers.tar.gz', 'w:gz') as archive:
        for name in HELPERS:
            archive.add(FPGA/name, arcname='fpga/'+name, recursive=False)
    (destination/'prepare-receipt.json').write_text(json.dumps(dict(packet_sha256=sha(destination/'payload.json'),
        request_sha256=sha(destination/'budget-request.json'), helpers_archive_sha256=sha(destination/'helpers.tar.gz'),
        source_sha256=packet['helper_sha256'], status='prepared_not_executed'), indent=2)+'\n')
    print(json.dumps(dict(destination=str(destination), request_sha256=sha(destination/'budget-request.json'),
                         payload_sha256=packet['payload_sha256'], unit=unit), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('destination', type=Path)
    p.add_argument('--mode', choices=('da', 'postplace'), required=True); p.add_argument('--attempt', type=int, required=True)
    a = p.parse_args(); prepare(a.destination, a.mode, a.attempt)
