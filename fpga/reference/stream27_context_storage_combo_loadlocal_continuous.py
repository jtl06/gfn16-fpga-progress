"""Private R95 R5 LOAD-local C2 own-pilot100→uninterrupted1000 metadata.

Existing finite-long class consumes scalar source-bound evidence. Never imports
or executes a full-N arithmetic oracle locally; never inherits other source/thread time.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
SELF = 'reference/stream27_context_storage_combo_loadlocal_continuous.py'
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-loadlocal-ownlong-v1'
PILOT_DIR = BASE / 'own100-serial-v1'
PILOT_MANIFEST = ROOT / 'queue/evidence/s4-p16-c2-combo-r5-own100-serial-q1-v1/attempt-0/collected/output/native/approved-manifest.json'
PILOT_SOURCE = PILOT_DIR / 'source/fpga'
PILOT_ID = 's4-p16-c2-combo-r5-own100-serial-q1-v1'
PILOT_STEP = 'normal-full-c2-combo-r5-own100-percontext'
PILOT_VALIDATOR = 'reference/stream27_context_storage_combo_loadlocal_long_native.py'
PILOT_REPORT = ROOT / 'queue/evidence' / PILOT_ID / 'attempt-0/collected/output/native/report.json'
PILOT_GATE = ROOT / 'queue/evidence' / PILOT_ID / 'gate-receipt.json'
HEADER = 'rtl/tb/s4_p16_two_context_full_config.h'
CPP = 'rtl/tb/stream27_p16_two_context_threadpilot.cpp'
STEP = 'normal-full-c2-combo-r5-continuous1000-percontext'
BASES = [604832956, 999999937]
COUNT = 1000
THREADS = 1
READY = '2026-10-02T11:53:46Z'
SCHEMA = 'stream27-p16-c2-measured-continuous-forecast-v1'
SHAPE = dict(model_command_seconds=10450, overall_seconds=10700, outer_seconds=10800, stop_grace_seconds=15)


def need(ok, why):
    if not ok:
        raise ValueError('C2_COMBO_CONTINUOUS_' + why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def bits(count=COUNT):
    need(type(count) is int and count in (100, 1000), 'FINITE_COUNT')
    result = []
    for ctx, seed in enumerate((0x1732f5a9, 0x7b28c361)):
        row, state = [ctx], seed
        for _ in range(1, count):
            state ^= (state << 13) & 0xffffffff
            state ^= state >> 17
            state ^= (state << 5) & 0xffffffff
            row.append(state & 1)
        result.append(row)
    return result


def config():
    return dict(aw=16, p=16, contexts=2, bases=BASES, count=COUNT, threads=THREADS,
                doubles=sum(map(sum, bits())), interval=8459, carry_done=12557,
                joint_first_edges=[204, 4433])


def header(pilot_header):
    text = pilot_header.decode()
    need(text.count('COUNT=100,INTERVAL=8459') == 1
         and 'MAX_EDGES=COUNT*uint64_t(INTERVAL)+3*11ull*N+100000;' in text, 'OWN_PILOT_COUNT_HEADER')
    match = re.search(r'BITS\[2\]\[COUNT\]=\{(.*)\};\n\Z', text)
    need(match is not None, 'EXACT_BITS_TABLE')
    expected = ','.join('{' + ','.join(map(str, row)) + '}' for row in bits(100))
    need(match.group(1) == expected, 'DETERMINISTIC100_PREFIX')
    result = text[:match.start(1)] + ','.join('{' + ','.join(map(str, row)) + '}' for row in bits()) + text[match.end(1):]
    return result.replace('COUNT=100,INTERVAL=8459', 'COUNT=1000,INTERVAL=8459', 1).encode()


def predict(command_seconds, overall_seconds, margin=1.75, reserve_seconds=600):
    need(all(type(v) in (int, float) and math.isfinite(v) and v > 0
         for v in (command_seconds, overall_seconds, margin, reserve_seconds)), 'FINITE_FORECAST')
    need(overall_seconds >= command_seconds and margin >= 1.75 and reserve_seconds >= 600,
         'ACTUAL_ANCILLARY_MARGIN')
    command = command_seconds * 10 * margin
    ancillary = (overall_seconds - command_seconds) * margin
    overall = command + ancillary + reserve_seconds
    return dict(method='own_C2_command_operation_ratio_with_fixed_overhead_and_reference_included',
        pilot_count_per_context=100, continuous_count_per_context=1000, operation_ratio=10, margin=margin,
        measured_command_seconds=command_seconds, measured_overall_seconds=overall_seconds,
        continuous_command_seconds_estimate=command, nonmodel_seconds_estimate=ancillary,
        additional_replay_and_uncertainty_reserve_seconds=reserve_seconds, overall_seconds_estimate=overall,
        finite_shape=SHAPE, fits_finite_shape=command <= SHAPE['model_command_seconds'] and overall <= SHAPE['overall_seconds'],
        scope='Own R95 R5 LOAD-local/source/thread planning estimate only; no1000 outcome, hardware throughput or OOM guarantee.')


def role():
    from fpga.reference import stream27_context_storage_combo_loadlocal_long_native as own
    raw = json.loads((PILOT_DIR / 'manifest.json').read_text())
    files = {name: (PILOT_SOURCE / name).read_bytes() for name in raw['sources']}
    need(all(sha(files[name]) == pin for name, pin in raw['sources'].items()), 'COMPLETE_OWN_PILOT_ROLE')
    previous = files[HEADER]
    files[HEADER] = header(previous)
    files[SELF] = (ROOT / SELF).read_bytes()
    m = deepcopy(raw)
    m['steps'] = [dict(name=STEP, argv=['{exe}'], expected_returncode=0,
        validator=dict(source=PILOT_VALIDATOR, function='validate', config=config(), assets={}))]
    m['sources'] = {name: sha(data) for name, data in files.items()}
    m['r84']['continuous'] = dict(count_per_context=1000, model_threads=THREADS, production_and_cpp_unchanged=True,
        compiled_source_delta=[HEADER], original_header_sha256=sha(previous), full_header_sha256=sha(files[HEADER]),
        deterministic_prefix_equal=True, initial_resets=1, initial_load_words=131072, descriptors=1998,
        bases=BASES, no_reload_or_checkpoint_barrier=True, full_N_numeric_locally_performed=False)
    m['context_storage_combo_loadlocal']['own_long'].update(count_per_context=1000, descriptors=1998,
        own_calendar=own.calendar(m['context_storage_combo_loadlocal']['geometry'], 1000), source_count_only_not_native=True)
    m['rtl_readiness']['candidate_id'] = 's4-p16-c2-combo-r5-continuous1000-v1'
    need(m['rtl_readiness']['rtl_ready_at_utc'] == READY, 'ORIGINAL_READINESS')
    return m, files

def forecast(manifest):
    pilot, report, gate = [json.loads(path.read_text()) for path in (PILOT_MANIFEST, PILOT_REPORT, PILOT_GATE)]
    pins = {key: sha(path.read_bytes()) for key, path in (('pilot_manifest', PILOT_MANIFEST),
        ('pilot_report', PILOT_REPORT), ('pilot_gate', PILOT_GATE))}
    need(gate['status'] == 'PASS_expected_contracts' and gate['manifest_sha256'] == pins['pilot_manifest']
         and gate['report_sha256'] == pins['pilot_report'] and report['manifest_sha256'] == pins['pilot_manifest']
         and report['host'] == 'gfn16-pilot-c4d' and report['model_threads'] == THREADS,
         'ACTUAL_OWN_COMBO_PILOT_BINDINGS')
    rows = [row for row in report['steps'] if row['name'] == PILOT_STEP]
    gates = [row for row in gate['steps'] if row['name'] == PILOT_STEP]
    need(len(rows) == len(gates) == 1 and rows[0]['returncode'] == gates[0]['actual_returncode'] == 0
         and rows[0]['error'] is None, 'OWN_PILOT_COMMAND')
    validation = gates[0]['validation']
    need(validation['measurements']['count_per_context'] == 100
         and validation['measurements']['interval'] == 8459, 'OWN_COUNT_CALENDAR')
    names = set(manifest['build']['sv_sources']) | {CPP, 'rtl/tb/native_runtime_context_v1.h',
        'rtl/tb/stream27_host_chain_full_reference_v1.h', 'rtl/tb/stream27_shared_reference_ntt_v1.h'}
    need(len(manifest['build']['sv_sources']) == 56 and all(manifest['sources'][name] == pilot['sources'][name]
         for name in names), 'EXACT_COMBO_SOURCE_MODEL')
    return dict(schema=SCHEMA, status='PASS_C2_own100_measured_continuous_forecast', generator=SELF,
        generator_sha256=sha((ROOT / SELF).read_bytes()), compatible_hosts=[report['host']], model_threads=THREADS,
        short_manifest_sha256=pins['pilot_manifest'], short_report_sha256=pins['pilot_report'], short_gate_sha256=pins['pilot_gate'],
        source_model_build=manifest['build'], source_model_pins={name: manifest['sources'][name] for name in sorted(names)},
        pilot_native_validation=validation,
        allowed_compiled_delta=dict(path=HEADER, pilot_sha256=pilot['sources'][HEADER], full_sha256=manifest['sources'][HEADER]),
        full_config=config(), forecast=predict(rows[0]['seconds'], report['seconds']))


def prepare_role(output, source_only=False):
    out = Path(output).resolve()
    need(out.is_relative_to(BASE) and not out.exists(), 'FRESH_ROLE')
    need(not any((ROOT / name).exists() for name in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'PAUSE')
    manifest, files = role()
    source = out / 'source/fpga'
    source.mkdir(parents=True)
    for name, raw in files.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    dump(out / 'manifest.json', manifest)
    if not source_only:
        measured = forecast(manifest)
        need(measured['forecast']['fits_finite_shape'], 'OWN_FORECAST_EXCEEDS_EXISTING_SHAPE')
        dump(out / 'forecast.json', measured)
    return dict(manifest=str(out / 'manifest.json'), source_root=str(source),
        forecast=str(out / 'forecast.json') if not source_only else None,
        status='source_only_no_forecast_no_submission' if source_only else 'own_pilot_bound_role_prepared_not_native')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare_role(args.output, args.source_only), indent=2))
