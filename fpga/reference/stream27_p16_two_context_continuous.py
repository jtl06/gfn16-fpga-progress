"""R84 uninterrupted C2 1000/context, measured by its OWN eight-thread pilot.

Only source/header/calendar planning runs locally. The captured production RTL,
generated C++ driver, independent references and runtime are reused exactly.
The private count/BITS header is the sole compiled-source change. The driver's
legacy THREAD100 label is retained for byte identity; typed counts are 1000.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_p16_two_context_continuous.py'
HEADER = 'rtl/tb/s4_p16_two_context_full_config.h'
CPP = 'rtl/tb/stream27_p16_two_context_threadpilot.cpp'
PILOT_STEP = 'normal-full-c2-own100-percontext-threadpilot'
STEP = 'normal-full-c2-continuous1000-percontext'
PILOT_VALIDATOR = 'reference/stream27_p16_two_context_threadpilot.py'
PILOT_DIR = ROOT / 'artifacts/s4-p16-c2-explicit-own100-threadpilot-v1'
PILOT_MANIFEST = PILOT_DIR / 'packet-815/manifest.json'
PILOT_SOURCE = PILOT_DIR / 'packet-815/capture/source/fpga'
PILOT_REPORT = ROOT / 'queue/evidence/s4-p16-c2-explicit-own100-threadpilot-q2-v1/attempt-0/collected/output/native/report.json'
PILOT_GATE = ROOT / 'queue/evidence/s4-p16-c2-explicit-own100-threadpilot-q2-v1/gate-receipt.json'
BASES = [604832956, 999999937]
COUNT = 1000
READY = '2026-10-02T03:52:04Z'
SCHEMA = 'stream27-p16-c2-measured-continuous-forecast-v1'
SHAPE = dict(model_command_seconds=10450, overall_seconds=10700,
             outer_seconds=10800, stop_grace_seconds=15)


def need(ok, why):
    if not ok:
        raise ValueError('R84_CONTINUOUS_' + why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def bits(count=COUNT):
    need(type(count) is int and count in (100, 1000), 'EXPLICIT_FINITE_COUNT')
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


def header(pilot_header):
    """Only COUNT and its deterministic table; MAX_EDGES already uses COUNT."""
    text = pilot_header.decode()
    need(text.count('COUNT=100,INTERVAL') == 1 and
         'MAX_EDGES=COUNT*uint64_t(INTERVAL)+3*11ull*N+100000;' in text,
         'CAPTURED_COUNT_HEADER')
    match = re.search(r'BITS\[2\]\[COUNT\]=\{(.*)\};\n\Z', text)
    need(match is not None, 'FINAL_EXACT_BITS_TABLE')
    expected = ','.join('{' + ','.join(map(str, row)) + '}' for row in bits(100))
    need(match.group(1) == expected, 'OWN100_DETERMINISTIC_PREFIX')
    result = text[:match.start(1)] + ','.join('{' + ','.join(map(str, row)) + '}' for row in bits()) + text[match.end(1):]
    result = result.replace('COUNT=100,INTERVAL', 'COUNT=1000,INTERVAL', 1)
    return result.encode()


def config():
    return dict(aw=16, p=16, contexts=2, bases=BASES, count=COUNT,
                threads=8, doubles=sum(map(sum, bits())))


def validate(stdout, stderr, rc, config, assets):
    need(config == globals()['config']() and assets == {}, 'CONFIG')
    need(type(rc) is int and rc == 0 and stderr == '' and
         stdout.startswith('R84_C2_THREAD100_PASS '), 'TYPED_OUTPUT')
    value = json.loads(stdout.removeprefix('R84_C2_THREAD100_PASS '))
    expected = dict(aw=16, p=16, contexts=2, bases=BASES, count_per_context=COUNT,
        squares=2*COUNT, descriptors=2*(COUNT-1), doubles=config['doubles'], reads=4*65536,
        signed96=True, independent_reference=True, initial_resets=1,
        initial_load_words=2*65536, interval=8459, peer_live_reads=65536, model_threads=8)
    variable = {'launches', 'joint_cycles', 'overlap_edges', 'done_edges', 'warm_edges',
                'setup_edges', 'reference_seconds', 'model_seconds', 'seconds'}
    need(set(value) == set(expected) | variable and
         all(value[k] == v and type(value[k]) is type(v) for k, v in expected.items()),
         'EXACT_CONTINUOUS_COUNTS')
    need(stdout.endswith('\n') and '\n' not in stdout[:-1], 'ONE_FOOTER')
    launch = value['launches']
    need(type(launch) is list and len(launch) == 2 and
         all(type(row) is list and len(row) == COUNT and
             all(type(x) is int and x > 0 for x in row) for row in launch), 'ALL_2000_LAUNCHES')
    need(launch == [[204 + k*8459 for k in range(COUNT)],
                    [4433 + k*8459 for k in range(COUNT)]], 'EXACT_FIRST_AND_PERIODIC_CALENDAR')
    for name in ('done_edges', 'warm_edges', 'setup_edges'):
        need(type(value[name]) is list and len(value[name]) == 2 and
             all(type(x) is int and x > 0 for x in value[name]), 'EDGE_PAIR')
    need(value['setup_edges'] == [99, 199] and
         value['warm_edges'] == [row[-1] + 12558 for row in launch] and
         all(value['done_edges'][c] > value['warm_edges'][c] + 10*65536 for c in (0, 1)),
         'FINAL_TRUE_LAST_CANONICAL_COPY_PUBLICATION')
    need(type(value['joint_cycles']) is int and max(value['done_edges']) + 65536 <= value['joint_cycles']
         < COUNT*8459 + 33*65536 + 100000 and
         type(value['overlap_edges']) is int and value['overlap_edges'] > 0, 'ACTUAL_FINITE_OVERLAP')
    need(all(type(value[k]) in (int, float) and math.isfinite(value[k]) and
             0 < value[k] < SHAPE['model_command_seconds']
             for k in ('reference_seconds', 'model_seconds', 'seconds')), 'FINITE_PHASES')
    need(abs(value['reference_seconds'] + value['model_seconds'] - value['seconds']) < .05,
         'PHASE_SUM')
    return dict(status='PASS_expected_contracts', measurements=value, promotion_allowed=False,
        scope='Own corrected C2 uninterrupted1000 percontext: one reset/2N initial loads, real FIFO1998 descriptors, independent full-N reference and all final signed96; no hardware area/clock/2x throughput claim.')


def predict(command_seconds, overall_seconds, margin=1.75, reserve_seconds=600):
    """Operation ratio is deliberately conservative; no C1 or tick forecast."""
    need(all(type(v) in (int, float) and math.isfinite(v) and v > 0
             for v in (command_seconds, overall_seconds, margin, reserve_seconds)), 'FINITE_FORECAST')
    need(overall_seconds >= command_seconds and margin >= 1.75 and reserve_seconds >= 600,
         'MEASURED_ANCILLARY_AND_MARGIN')
    command = command_seconds * 10 * margin
    ancillary = (overall_seconds - command_seconds) * margin
    overall = command + ancillary + reserve_seconds
    return dict(method='own_C2_command_operation_ratio_with_fixed_overhead_and_reference_included',
        pilot_count_per_context=100, continuous_count_per_context=1000, operation_ratio=10,
        margin=margin, measured_command_seconds=command_seconds,
        measured_overall_seconds=overall_seconds, continuous_command_seconds_estimate=command,
        nonmodel_seconds_estimate=ancillary, additional_replay_and_uncertainty_reserve_seconds=reserve_seconds,
        overall_seconds_estimate=overall, finite_shape=SHAPE,
        fits_finite_shape=command <= SHAPE['model_command_seconds'] and overall <= SHAPE['overall_seconds'],
        scope='Conservative own-source eight-thread planning estimate, not native1000 success, physical throughput or an OOM guarantee; native reference already included in measured command.')


def role():
    raw = json.loads((PILOT_DIR/'manifest-815.json').read_text())
    selected = json.loads(PILOT_MANIFEST.read_text())
    need(raw['build'] == selected['build'] and raw['probe'] == selected['probe'], 'CAPTURED_BUILD_PROBE')
    files = {name: (PILOT_SOURCE/name).read_bytes() for name in raw['sources']}
    need(all(sha(files[name]) == pin == selected['sources'][name]
             for name, pin in raw['sources'].items()), 'CAPTURED_COMPLETE_PILOT_ROLE')
    original_header = files[HEADER]
    files[HEADER] = header(original_header)
    files[SELF] = (ROOT/SELF).read_bytes()
    m = deepcopy(raw)
    m['fixed_execution'] = deepcopy(selected['fixed_execution'])
    m['steps'] = [dict(name=STEP, argv=['{exe}'], expected_returncode=0,
        validator=dict(source=SELF, function='validate', config=config(), assets={}))]
    m['sources'] = {name: sha(v) for name, v in files.items()}
    # Existing wide validator proves serial->threaded configuration only. This
    # new serial declaration describes this exact1000 role, not the pilot role.
    serial = {key: deepcopy(m[key]) for key in ('build', 'probe', 'steps', 'sources')}
    serial['build'].pop('runtime_threads', None)
    serial['build']['cflags'] = [x for x in serial['build']['cflags'] if x != '-DGFN16_RUNTIME_THREADS=8']
    serial['probe']['expected_json'] = dict(context_threads=1, model_threads=1, expected_threads=1)
    m['wide_thread_pilot']['serial_contract'] = serial
    m['wide_thread_pilot']['serial_contract_sha256'] = sha(canonical(serial))
    m['wide_thread_pilot']['purpose'] = 'Measured own-C2 uninterrupted1000/ctx successor, no pilot or C1 outcome inherited.'
    m['r84']['continuous'] = dict(count_per_context=1000, model_threads=8,
        production_and_cpp_unchanged=True, compiled_source_delta=[HEADER],
        original_header_sha256=sha(original_header), full_header_sha256=sha(files[HEADER]),
        deterministic_prefix_equal=True, initial_resets=1, initial_load_words=2*65536,
        descriptors=1998, bases=BASES, no_reload_or_checkpoint_barrier=True,
        full_N_numeric_locally_performed=False)
    m['test_role'] = 'normal'
    m['rtl_readiness']['candidate_id'] = 's4-p16-c2-explicit-continuous1000-v1'
    m['rtl_readiness']['rtl_ready_at_utc'] = READY
    return m, files


def forecast(manifest):
    p, r, g = [json.loads(path.read_text()) for path in (PILOT_MANIFEST, PILOT_REPORT, PILOT_GATE)]
    pins = {key: sha(path.read_bytes()) for key, path in
            (('pilot_manifest', PILOT_MANIFEST), ('pilot_report', PILOT_REPORT), ('pilot_gate', PILOT_GATE))}
    need(g['status'] == 'PASS_expected_contracts' and g['manifest_sha256'] == pins['pilot_manifest']
         and g['report_sha256'] == pins['pilot_report'] and r['manifest_sha256'] == pins['pilot_manifest']
         and r['host'] == 'gfn16-azure-sim-f32' and r['model_threads'] == 8, 'ACTUAL_OWN_PILOT_BINDINGS')
    rows = [row for row in r['steps'] if row['name'] == PILOT_STEP]
    gates = [row for row in g['steps'] if row['name'] == PILOT_STEP]
    need(len(rows) == len(gates) == 1 and rows[0]['returncode'] == gates[0]['actual_returncode'] == 0
         and rows[0]['error'] is None, 'OWN_PILOT_COMMAND')
    names = set(manifest['build']['sv_sources']) | {CPP, 'rtl/tb/native_runtime_context_v1.h',
        'rtl/tb/stream27_host_chain_full_reference_v1.h', 'rtl/tb/stream27_shared_reference_ntt_v1.h'}
    return dict(schema=SCHEMA, status='PASS_C2_own100_measured_continuous_forecast',
        generator=SELF, generator_sha256=sha((ROOT/SELF).read_bytes()), compatible_hosts=[r['host']],
        model_threads=8, short_manifest_sha256=pins['pilot_manifest'], short_report_sha256=pins['pilot_report'],
        short_gate_sha256=pins['pilot_gate'], source_model_build=manifest['build'],
        source_model_pins={name: manifest['sources'][name] for name in sorted(names)},
        pilot_native_validation=gates[0]['validation'],
        allowed_compiled_delta=dict(path=HEADER, pilot_sha256=p['sources'][HEADER], full_sha256=manifest['sources'][HEADER]),
        full_config=config(), forecast=predict(rows[0]['seconds'], r['seconds']))


def prepare_role(output):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists() and READY != 'SOURCE_NOT_YET_FROZEN', 'FRESH_FROZEN_ROLE')
    need(not any((ROOT/n).exists() for n in ('docs/briefs/PAUSE', 'queue/PAUSE')), 'PAUSE')
    m, files = role()
    source = out/'source/fpga'
    source.mkdir(parents=True)
    for name, raw in files.items():
        path = source/name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    dump(out/'manifest.json', m)
    dump(out/'forecast.json', forecast(m))
    return dict(manifest=str(out/'manifest.json'), source_root=str(source), forecast=str(out/'forecast.json'),
        evidence=dict(pilot_manifest=str(PILOT_MANIFEST), pilot_report=str(PILOT_REPORT), pilot_gate=str(PILOT_GATE)),
        status='source_role_prepared_not_native')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_role(args.output), indent=2))
