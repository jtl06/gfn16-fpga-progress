"""Measured, source-bound single-model long shape; no host or thread expansion."""
import hashlib
import json
import math
from pathlib import Path, PurePosixPath

SHAPE = {'id': 'continuous-model-10800-v1', 'model_command_seconds': 10450,
         'ancillary_command_seconds': 1800, 'overall_seconds': 10700,
         'outer_seconds': 10800, 'stop_grace_seconds': 15, 'lock_wait_seconds': 1800,
         'model_threads': 1}
EVIDENCE = ('forecast', 'pilot_manifest', 'pilot_report', 'pilot_gate')


def need(ok, why):
    if not ok:
        raise ValueError('long duration: ' + why)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def number(value):
    need(type(value) in (int, float) and math.isfinite(value) and value > 0, 'positive finite measurement')
    return value


def contract(manifest):
    names = set(manifest['build']['sv_sources']) | {manifest['build']['cpp_source']}
    for step in manifest['steps']:
        validator = step.get('validator', {})
        if validator:
            names.add(validator['source'])
            names.update(validator.get('assets', {}).values())
        for arg in step['argv']:
            if arg.startswith('{root}/'):
                names.add(arg[len('{root}/'):])
    return digest(dict(build=manifest['build'], probe=manifest['probe'], steps=manifest['steps'],
                       pins={name: manifest['sources'][name] for name in sorted(names)}))


def assess(manifest, values, raw_pins, host):
    """Pure measured forecast admission; never executes a role/reference module."""
    need(host == 'gfn16-pilot-c4d', 'first long shape is GCP only')
    need(set(values) == set(raw_pins) == set(EVIDENCE), 'four exact evidence inputs')
    forecast, pilot, report, gate = (values[name] for name in EVIDENCE)
    need(gate['status'] == 'PASS_expected_contracts' and gate['promotion_allowed'] is False,
         'actual typed pilot contract PASS')
    need(gate['manifest_sha256'] == raw_pins['pilot_manifest']
         and gate['report_sha256'] == raw_pins['pilot_report'], 'pilot gate raw bindings')
    need(report['status'] == 'completed_native_commands_unreviewed'
         and report['manifest_sha256'] == raw_pins['pilot_manifest']
         and report['host'] == host, 'completed pilot on exact host')
    need(forecast['status'].startswith('PASS_') and host in forecast['compatible_hosts']
         and forecast['short_manifest_sha256'] == raw_pins['pilot_manifest']
         and forecast['short_report_sha256'] == raw_pins['pilot_report']
         and forecast['short_gate_sha256'] == raw_pins['pilot_gate'], 'source-bound forecast/pilot')
    need(manifest['build'] == pilot['build'] == forecast['source_model_build'], 'unchanged pilot model configuration')
    need(manifest['probe'] == pilot['probe'] and manifest['probe']['expected_json'] ==
         dict(context_threads=1, model_threads=1, expected_threads=1), 'exact single-thread probe')
    pins = forecast['source_model_pins']
    compiled = set(manifest['build']['sv_sources']) | {manifest['build']['cpp_source']}
    need(compiled <= set(pins), 'forecast covers every compiled source')
    need(all(manifest['sources'].get(name) == pilot['sources'].get(name) == pin
             for name, pin in pins.items()), 'unchanged compiled/harness/runtime lineage')
    need(len(manifest['steps']) == 1, 'one uninterrupted model command only')
    step = manifest['steps'][0]
    need(step.get('expected_returncode', 0) == 0 and step['argv'][0] == '{exe}', 'normal model contract')
    need(step['name'] in [row['name'] for row in pilot['steps']], 'pilot model step identity')
    need(step.get('validator', {}).get('config', {}).get('negative') == 'none', 'normal typed validator only')
    measured = {row['name']: row for row in report['steps']}
    f = forecast['forecast']
    margin = number(f['margin']); need(margin >= 1.75, 'at least measured1.75 margin')
    ratios = []
    for name, ticks in f['measured_ticks'].items():
        row = measured[name]
        need(row.get('error') is None and type(ticks) is int and ticks > 0, 'successful measured command/ticks')
        ratios.append(number(row['seconds']) / ticks)
    upper = max(ratios)
    need(math.isclose(upper, f['model_seconds_per_tick_upper_observed'], rel_tol=1e-10), 'recomputed measured tick envelope')
    ticks = f['continuous_model_ticks']
    need(type(ticks) is int and ticks > 0 and f['continuous_operations'] == 1000, 'explicit1000 operation forecast')
    estimate = upper * ticks * margin
    need(math.isclose(estimate, f['continuous_command_seconds_estimate'], rel_tol=1e-10), 'recomputed continuous forecast')
    normal_seconds = number(measured[step['name']]['seconds'])
    overhead = max(0, number(report['seconds']) - normal_seconds) * margin
    replay = number(f['full_reference_replay_seconds_estimate'])
    need(estimate <= SHAPE['model_command_seconds'] and estimate + overhead + replay <= SHAPE['overall_seconds'],
         'measured model plus nonmodel/replay allowance fits finite shape')
    return dict(status='PASS_measured_finite_duration_only', shape=SHAPE,
                model_seconds_estimate=estimate, overall_seconds_estimate=estimate + overhead + replay,
                host=host, contract_sha256=contract(manifest), model_step=step['name'],
                promotion_allowed=False, no_reset_reload_or_thread_change=True)


def validate(manifest, root, host):
    value = manifest['runtime_duration']
    need(value['shape'] == SHAPE and value['contract_sha256'] == contract(manifest), 'exact duration/role contract')
    need(set(value['evidence']) == set(EVIDENCE), 'closed duration evidence set')
    values, pins = {}, {}
    for key, item in value['evidence'].items():
        name = item['path']
        need(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts, 'relative evidence')
        path = Path(root) / name
        need(not path.is_symlink() and path.resolve().is_relative_to(Path(root).resolve()), 'contained evidence')
        raw = path.read_bytes(); pin = hashlib.sha256(raw).hexdigest()
        need(pin == item['sha256'] == manifest['sources'][name], 'source-closed duration evidence')
        values[key], pins[key] = json.loads(raw), pin
    return assess(manifest, values, pins, host)
