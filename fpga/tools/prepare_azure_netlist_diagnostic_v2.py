"""Source-pinned, bounded component timing-graph qualification packet."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

FPGA = Path(__file__).resolve().parents[1]
ROOT = '/home/azureuser/gfn16-worker'
TOOLS = ROOT+'/quartus-prefit-qualification-tools-v6'
HELPERS = ['cloud/azure_prefit_diagnostic_v4.py', 'cloud/azure_netlist_diagnostic_v2.py',
           'tools/quartus_prefit_native_v3.py', 'tools/quartus_timing_graph_v2.py',
           'synthesis/capture_timing_graph_v2.tcl', 'tools/quartus_sta_output_guard_v1.py', 'cloud/host_hours_azure_v2.py']
spec = importlib.util.spec_from_file_location('runtime_admission_v5', FPGA/'tools/prepare_azure_prefit_diagnostic_v5.py')
runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
meter_path = FPGA/'cloud/host_hours_azure_v2.py'
if hashlib.sha256(meter_path.read_bytes()).hexdigest() != 'b0875ec8fb12780c637548e9664d25d47a2b77bb8ef7d3ff997bbdfc640a8c9e':
    raise ValueError('shared pure Azure host-hours source drift')
meter_spec = importlib.util.spec_from_file_location('shared_azure_hours', meter_path)
meter = importlib.util.module_from_spec(meter_spec); meter_spec.loader.exec_module(meter)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination, attempt, snapshot, observation_path, observation_pin, provider_path, provider_pin):
    if sha(observation_path) != observation_pin:
        raise ValueError('runtime observation pin drift')
    observation = json.loads(observation_path.read_text())
    baseline = FPGA/'results/throughput-20260929/crt27-mont-hostbench-azure-v1/project'
    context = json.loads((baseline/'execution-context.json').read_text())
    manifest = json.loads((baseline/'manifest.json').read_text())
    tools = dict(context['azure_admission']['tool_sha256'])
    wrapper = tools[ROOT+'/altera_pro/26.1/quartus/bin/quartus_sh']
    tools.update({ROOT+'/altera_pro/26.1/quartus/bin/'+name: wrapper for name in ('quartus_syn', 'quartus_sta', 'quartus_cdb')})
    tools[ROOT+'/altera_pro/26.1/quartus/linux64/quartus_cdb'] = '69290861124085f2fa55540bc0f7a5593cd14a5ae6eb035022847ba3fdc3a4ec'
    tools = runtime.observed_tools(tools, observation)
    specification = dict(scope='component_probe', sources={'rtl/'+name: pin for name, pin in context['source_sha256'].items()},
        settings={name: sha(baseline/name) for name in context['control_sha256']},
        identity=dict(top=manifest['top'], device=manifest['device'], parameters=manifest['core_parameters'], clock_period_ns=10, seed=manifest['seed']),
        vendor_tool_sha256=tools, graph_snapshot=snapshot)
    for name, pin in specification['sources'].items():
        if sha(baseline/name) != pin:
            raise ValueError('source baseline drift')
    descriptor = meter.make_budget('gfn16-azure-f16', 900, provider_path, provider_pin, '0'*64)
    evidence = meter.evidence_pins(descriptor)
    packet = dict(schema='azure-prefit-diagnostic-packet-v1', mode='graph', spec=specification,
        job_id=f'azure-prefit-graph-v{attempt}', unit=f'gfn16-azure-prefit-graph-v{attempt}.service',
        original_project=ROOT+'/crt27-mont-azure-hostbench-v1', destination=ROOT+f'/quartus-prefit-azure-diag-v{attempt}', pause_path=ROOT+'/PAUSE',
        manifest_sha256=context['manifest_sha256'], benchmark_context_sha256=sha(baseline/'execution-context.json'),
        benchmark_result_sha256=sha(baseline/'execution-result.json'), benchmark_final_guard_sha256=sha(baseline/'azure-final-guard.json'),
        tool_sha256=tools, helper_sha256={TOOLS+'/fpga/'+name: sha(FPGA/name) for name in sorted(set(HELPERS) | set(evidence))},
        parser_path=TOOLS+'/fpga/tools/quartus_timing_graph_v2.py',
        runtime_observation=dict(path=str(observation_path.resolve()), sha256=observation_pin, capture_helper_sha256=observation['capture_helper_sha256']))
    packet['payload_sha256'] = hashlib.sha256(json.dumps(packet, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    packet['host_hours_budget'] = meter.make_budget('gfn16-azure-f16', 900, provider_path, provider_pin, packet['payload_sha256'])
    admission = meter.validate_budget(packet['host_hours_budget'], 'gfn16-azure-f16', 900, source_sha256=packet['payload_sha256'])
    destination.mkdir(parents=True, exist_ok=False)
    (destination/'payload.json').write_text(json.dumps(packet, indent=2)+'\n')
    with tarfile.open(destination/'helpers.tar.gz', 'w:gz') as archive:
        for name in sorted(set(HELPERS) | set(evidence)):
            archive.add(FPGA/name, arcname='fpga/'+name, recursive=False)
    receipt = dict(status='prepared_not_executed_no_per_job_reservation', host_hours_admission=admission,
                   helpers_archive_sha256=sha(destination/'helpers.tar.gz'), payload_file_sha256=sha(destination/'payload.json'),
                   payload_sha256=packet['payload_sha256'], source_sha256=packet['helper_sha256'], runtime_observation_sha256=observation_pin)
    (destination/'prepare-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('destination', type=Path)
    parser.add_argument('--attempt', type=int, required=True); parser.add_argument('--snapshot', choices=('synthesized', 'final'), required=True)
    parser.add_argument('--runtime-observation', type=Path, required=True); parser.add_argument('--runtime-observation-sha256', required=True)
    parser.add_argument('--provider-path', required=True); parser.add_argument('--provider-sha256', required=True)
    args = parser.parse_args(); prepare(args.destination, args.attempt, args.snapshot, args.runtime_observation, args.runtime_observation_sha256, args.provider_path, args.provider_sha256)
