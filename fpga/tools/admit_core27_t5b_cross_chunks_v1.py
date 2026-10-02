"""Measured serial Azure bridge100-square duration admission, metadata only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREDICT = 'tools/admit_core27_t5b_chunks_v1.py'
PREDICT_SHA = '2cc7dfac7cbdb8bdf1ecb625f35c9b3522b98c326c8938d019bebe0590e91524'
GATE = 'tools/native_gate_receipt_v1.py'
GATE_SHA = '131d4e6b9cafd424935094c3ec50ef81d7c2e8024efae6a5d37ce20d0c5a29d3'
BRIDGE = 'reference/core27_t5b_soak_cross_runtime_v1.py'
BRIDGE_SHA = '3be94f597e09455a2b9f3f363dfc6a4ac36a240eb26b22a1717e91a072ea1e83'
TARGET_SHA = '1a5125fa55711298b5412df91105e47aa4c13b6b42ab32191fd8b23696f081f2'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(name, pin):
    path = ROOT / name
    need(sha(path) == pin, 'pinned pure artifact helper')
    spec = importlib.util.spec_from_file_location('_cross_duration_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def admission(ticket_file, full_reference_file):
    ticket_file, full_reference_file = Path(ticket_file).resolve(), Path(full_reference_file).resolve()
    ticket = json.loads(ticket_file.read_text())
    need(ticket['id'] == 'soak-t5b-aw16-short-cross-burst16-q3-v2', 'qualified repaired bridge short')
    props = ticket['result']['properties']
    need(props['Result'] == 'success' and props['ExecMainStatus'] == '0'
         and props['MainPID'] == '0' and props['ControlGroup'] == '', 'actual terminal bridge short')
    package = ticket['package'];prepared = Path(package['archive']).parent / 'manifest.json'
    need(package['profile'].startswith('azure-burst16-static8g') and sha(package['archive']) == package['sha256']
         and sha(prepared) == package['manifest_sha256'], 'admitted8GiB original package')
    gate = load(GATE, GATE_SHA)
    report_path = Path(ticket['result']['evidence']) / 'output/native/report.json'
    manifest = json.loads(prepared.read_text());report = json.loads(report_path.read_text())
    receipt = gate.validate_result(gate.make_contract(ticket['id'], prepared), report_path, id=ticket['id'])
    link = ticket['dependency_gate']
    need(link['status'] == 'PASS_expected_contracts' and sha(link['path']) == link['sha256']
         and json.loads(Path(link['path']).read_text()) == receipt, 'replayed typed source/raw artifact gate')
    need(report['host'] == 'gfn16-azure-sim-f32' and manifest['build']['parameters'] == {'AW': 16, 'NTT_LANES': 64}
         and manifest['sources'][BRIDGE] == BRIDGE_SHA and manifest['sources']['soak/cross-runtime.json'] == TARGET_SHA
         and report['probe'] == dict(context_threads=1, model_threads=1, expected_threads=1), 'actual serial target/source identity')
    predictor = load(PREDICT, PREDICT_SHA)
    need(manifest['sources'][predictor.CORE] == predictor.CORE_SHA
         and manifest['sources'][predictor.BENCH] == predictor.BENCH_SHA, 'unchanged measured T5b model')
    validations = report['validations'];normal = validations['soak-normal']
    need(normal['status'] == 'passed_soak_segment_boundary_replay' and normal['operations'] == 2
         and normal['readbacks'] == 3 and normal['independent_gmpy2_boundary_replay'] is True
         and normal['generation_runtime_manifest_sha256'] == predictor.RUNTIME_SHA
         and normal['replay_runtime_manifest_sha256'] == TARGET_SHA and normal['original_generation_not_rehosted'] is True
         and normal['auxiliary_reference_runtime']['status'] == 'passed_exact_auxiliary_reference_runtime'
         and normal['auxiliary_reference_runtime']['files'] == 23
         and all(validations[k]['status'] == 'passed_matched_soak_negative'
                 for k in ('soak-negative-boundary', 'soak-negative-loaded-state')), 'all target GMP and negative contracts')
    steps = {s['name']: s for s in report['steps']}
    log_path = report_path.parent / 'soak-normal.log'
    need(sha(log_path) == steps['soak-normal']['sha256'], 'actual timing trace')
    rows = [json.loads(line.split(' ', 1)[1]) for line in log_path.read_text().splitlines() if line.startswith('SOAK_STEP ')]
    need(len(rows) == 2 and [r['cycles'] for r in rows] == [41674, 28826], 'matched cold/warm measured cycles')
    full = json.loads(full_reference_file.read_text())
    need(full['id'] == 'soak-t5b-aw16-full-reference-q3-v1'
         and full['reference_execution_receipt']['status'] == 'PASS_reference_execution_outputs_not_HDL_or_import',
         'preserved actual full reference cost')
    forecast = predictor.predict({k: steps[k] for k in validations}, 41674, 28826,
                                 full['result']['queue_report']['elapsed_seconds'])
    # Target full-prefix GMP replay is not measured yet. Reserve a conservative
    # explicit300s allowance inside the outer bound; never label it measured.
    forecast['target_full_reference_replay_allowance_seconds'] = 300
    forecast['target_full_reference_replay_allowance_measured'] = False
    forecast['chunk_overall_seconds_estimate'] = forecast['chunk_command_seconds_estimate'] \
        + 1.75 * (steps['lint']['seconds'] + steps['build']['seconds']) + 300 + 45
    need(forecast['chunk_command_seconds_estimate'] < 1800 and forecast['chunk_overall_seconds_estimate'] < 3600,
         'bounded target100-square forecast')
    names = [*manifest['build']['sv_sources'], predictor.BENCH, 'rtl/tb/native_runtime_context_v1.h',
             'reference/core27_t5b_soak_v1.py', 'reference/core27_crtmont_soak_v1.py',
             'reference/core27_t5b_soak_native_v1.py', BRIDGE, 'soak/cross-runtime.json',
             'soak/cross-generation-runtime.json']
    return dict(schema='core27-t5b-soak-cross-duration-admission-v1', status='PASS_bounded_target_chunk_duration_estimate',
        short_ticket_sha256=sha(ticket_file), short_gate_sha256=link['sha256'], short_report_sha256=sha(report_path),
        short_manifest_sha256=sha(prepared), short_functional_sha256=link['functional_sha256'],
        source_model_build=manifest['build'], source_model_pins={k: manifest['sources'][k] for k in names},
        full_reference_ticket_sha256=sha(full_reference_file), host='gfn16-azure-sim-f32',
        compatible_hosts=['gfn16-azure-sim-f32'], model_threads=1, minimum_ram_gib=8, forecast=forecast,
        admitted_bounds=dict(command_seconds=1800, overall_seconds=3600, outer_seconds=3700),
        continuous_admitted=False, promotion_allowed=False, arithmetic_executed=False,
        scope='Measured target serial model estimate plus mandatory native finite guards; target full-prefix replay allowance is not measured.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ticket', 'full-reference', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    value = admission(args.ticket, args.full_reference)
    with args.output.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    print(json.dumps(value, indent=2))
