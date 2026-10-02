"""Additive diagnostic preparation with observed, package-verified Python pin.

Only /usr/bin/python3 may differ from the completed benchmark tool set. Native
Quartus/runtime tool drift, unknown package provenance and tampering are refused.
The native runner remains source-frozen and rechecks every resulting tool pin.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tarfile

FPGA = Path(__file__).resolve().parents[1]
ROOT = '/home/azureuser/gfn16-worker'
TOOLS = ROOT+'/quartus-prefit-qualification-tools-v4'
HELPERS = ['cloud/azure_prefit_diagnostic_v3.py', 'tools/quartus_prefit_native_v3.py',
           'synthesis/prefit_design_assistant_v2.tcl', 'synthesis/postplace_timing_diagnostic_v1.tcl']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def observed_tools(expected, observation, now=None):
    if observation.get('schema') != 'quartus-diagnostic-runtime-observation-v1' or observation.get('transport_returncode') != 0:
        raise ValueError('successful read-only runtime capture required')
    tools = observation.get('tool_sha256', {})
    if set(tools) != set(expected) or any(not re.fullmatch('[0-9a-f]{64}', pin) for pin in tools.values()):
        raise ValueError('complete exact tool set required')
    changed = {name: pin for name, pin in tools.items() if expected[name] != pin}
    if set(changed) != {'/usr/bin/python3'}:
        raise ValueError('only documented Python runtime update is admitted')
    verification = observation.get('dpkg_verification', {})
    if (observation.get('installed_python_package_files_match') is not True or verification.get('returncode') != 0
            or verification.get('stdout') or verification.get('stderr') or verification.get('argv') != ['dpkg', '--verify', 'python3.12-minimal']):
        raise ValueError('installed Python package verification required')
    package = observation.get('installed_packages', {})
    if package.get('returncode') != 0 or 'python3.12-minimal\t3.12.3-1ubuntu0.17\n' not in package.get('stdout', ''):
        raise ValueError('unsupported Python package version')
    if observation.get('python_resolved_path') != '/usr/bin/python3.12' or observation.get('python_version', {}).get('stdout') != 'Python 3.12.3\n':
        raise ValueError('unsupported Python runtime identity')
    history = observation.get('apt_history', '')
    if hashlib.sha256(history.encode()).hexdigest() != observation.get('apt_history_sha256') or not re.search(
            r'Commandline: /usr/bin/unattended-upgrade\nUpgrade: [^\n]*python3\.12-minimal:amd64 \(3\.12\.3-1ubuntu0\.16, 3\.12\.3-1ubuntu0\.17\)', history):
        raise ValueError('recorded existing unattended-upgrade provenance required')
    age = ((now or datetime.now(timezone.utc))-datetime.fromisoformat(observation['observed_at_utc'])).total_seconds()
    if not 0 <= age <= 900:
        raise ValueError('fresh runtime observation required')
    return tools


def prepare(destination, mode, attempt, runtime_path, runtime_pin):
    if sha(runtime_path) != runtime_pin:
        raise ValueError('runtime observation identity drift')
    observation = json.loads(runtime_path.read_text())
    baseline = FPGA/'results/throughput-20260929/crt27-mont-hostbench-azure-v1/project'
    context = json.loads((baseline/'execution-context.json').read_text())
    manifest = json.loads((baseline/'manifest.json').read_text())
    tools = dict(context['azure_admission']['tool_sha256'])
    wrapper = tools[ROOT+'/altera_pro/26.1/quartus/bin/quartus_sh']
    tools.update({ROOT+'/altera_pro/26.1/quartus/bin/'+name: wrapper for name in ('quartus_syn', 'quartus_sta', 'quartus_cdb')})
    tools[ROOT+'/altera_pro/26.1/quartus/linux64/quartus_cdb'] = '69290861124085f2fa55540bc0f7a5593cd14a5ae6eb035022847ba3fdc3a4ec'
    tools = observed_tools(tools, observation)
    spec = dict(scope='component_probe', sources={'rtl/'+name: pin for name, pin in context['source_sha256'].items()},
        settings={name: sha(baseline/name) for name in context['control_sha256']},
        identity=dict(top=manifest['top'], device=manifest['device'], parameters=manifest['core_parameters'], clock_period_ns=10, seed=manifest['seed']),
        selected_clock='kernel_clk', vendor_tool_sha256=tools)
    for name, pin in spec['sources'].items():
        if sha(baseline/name) != pin:
            raise ValueError('source baseline drift')
    destination.mkdir(parents=True, exist_ok=False)
    unit = f'gfn16-azure-prefit-{mode}-v{attempt}.service'
    packet = dict(schema='azure-prefit-diagnostic-packet-v1', mode=mode, spec=spec,
        job_id=f'azure-prefit-{mode}-v{attempt}', unit=unit, original_project=ROOT+'/crt27-mont-azure-hostbench-v1',
        destination=ROOT+f'/quartus-prefit-azure-diag-v{attempt}', pause_path=ROOT+'/PAUSE',
        manifest_sha256=context['manifest_sha256'], benchmark_context_sha256=sha(baseline/'execution-context.json'),
        benchmark_result_sha256=sha(baseline/'execution-result.json'), benchmark_final_guard_sha256=sha(baseline/'azure-final-guard.json'),
        tool_sha256=tools, helper_sha256={TOOLS+'/fpga/'+name: sha(FPGA/name) for name in HELPERS},
        parser_path=TOOLS+'/fpga/tools/quartus_prefit_native_v3.py', capture_netlist_help=(mode == 'da'),
        runtime_observation=dict(path=str(runtime_path.resolve()), sha256=runtime_pin, capture_helper_sha256=observation['capture_helper_sha256'],
                                 scope='Existing package-verified unattended Python update only; no Quartus change or infrastructure mutation.'))
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
        source_sha256=packet['helper_sha256'], runtime_observation_sha256=runtime_pin, status='prepared_not_executed'), indent=2)+'\n')
    print(json.dumps(dict(destination=str(destination), request_sha256=sha(destination/'budget-request.json'),
                         payload_sha256=packet['payload_sha256'], unit=unit), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('destination', type=Path)
    parser.add_argument('--mode', choices=('da', 'postplace'), required=True); parser.add_argument('--attempt', type=int, required=True)
    parser.add_argument('--runtime-observation', type=Path, required=True); parser.add_argument('--runtime-observation-sha256', required=True)
    args = parser.parse_args(); prepare(args.destination, args.mode, args.attempt, args.runtime_observation, args.runtime_observation_sha256)
