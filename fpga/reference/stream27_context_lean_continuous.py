"""Own lean-R7 measured serial100→1000, HEADER count/bits-only native delta.

lean build; host GL assumed (unimplemented). Source/reference donors are not
numerical, clock or duration inheritance. No full-N arithmetic is run locally.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import re

from . import stream27_context_lean_long_native as pilot

ROOT = pilot.ROOT
SELF = 'reference/stream27_context_lean_continuous.py'
PILOT_DIR = ROOT/'results/throughput-20260929/trackS-c2-lean-r7-ownlong-v1/own100-serial-v1'
RAW = ROOT/'queue/evidence'/pilot.ID/'attempt-0/collected/output/native'
PILOT_GATE = ROOT/'queue/evidence'/pilot.ID/'gate-receipt.json'
PILOT_STEP = 'normal-full-c2-lean-r7-own100-percontext'
STEP = 'normal-full-c2-lean-r7-continuous1000-percontext'
SHAPE = dict(model_command_seconds=10450, overall_seconds=10700, outer_seconds=10800, stop_grace_seconds=15)
BASES = [604832956, 999999937]
COUNT = 1000
THREADS = 1
SCHEMA = 'stream27-p16-c2-measured-continuous-forecast-v1'
need, sha, read, dump = pilot.need, pilot.sha, pilot.read, pilot.dump


def bits(count=COUNT):
    need(type(count) is int and count in (100, 1000), 'FINITE_COUNT')
    result = []
    for context, seed in enumerate((0x1732f5a9, 0x7b28c361)):
        row, state = [context], seed
        for _ in range(1, count):
            state ^= (state << 13) & 0xffffffff
            state ^= state >> 17
            state ^= (state << 5) & 0xffffffff
            row.append(state & 1)
        result.append(row)
    return result


def config():
    return dict(aw=16, p=16, contexts=2, bases=BASES, count=COUNT, threads=THREADS,
                doubles=sum(map(sum,bits())), interval=8459, carry_done=12557,
                joint_first_edges=[204,4433])


def header(pilot_header):
    text = pilot_header.decode()
    need(text.count('COUNT=100,INTERVAL=8459') == 1, 'OWN_COUNT100_HEADER')
    match = re.search(r'BITS\[2\]\[COUNT\]=\{(.*)\};\n\Z', text)
    need(match is not None and match.group(1) == ','.join('{'+','.join(map(str,row))+'}' for row in bits(100)),
         'EXACT100_BIT_PREFIX')
    long_bits = ','.join('{'+','.join(map(str,row))+'}' for row in bits())
    text = text[:match.start(1)]+long_bits+text[match.end(1):]
    return text.replace('COUNT=100,INTERVAL=8459', 'COUNT=1000,INTERVAL=8459', 1).encode()


def predict(command_seconds, overall_seconds, margin=1.75, reserve_seconds=600):
    need(all(type(value) in (int,float) and math.isfinite(value) and value > 0
             for value in (command_seconds,overall_seconds,margin,reserve_seconds)) and
         overall_seconds >= command_seconds and margin >= 1.75 and reserve_seconds >= 600,
         'FINITE_MEASURED_PHASES_MARGIN_RESERVE')
    command = command_seconds*10*margin
    ancillary = (overall_seconds-command_seconds)*margin
    overall = command+ancillary+reserve_seconds
    return dict(method='own_lean_serial100 operation ratio with fixed ancillary margin and replay reserve',
        pilot_count_per_context=100, continuous_count_per_context=COUNT, operation_ratio=10, margin=margin,
        measured_command_seconds=command_seconds, measured_overall_seconds=overall_seconds,
        continuous_command_seconds_estimate=command, nonmodel_seconds_estimate=ancillary,
        additional_replay_and_uncertainty_reserve_seconds=reserve_seconds,
        overall_seconds_estimate=overall, finite_shape=SHAPE,
        fits_finite_shape=command<=SHAPE['model_command_seconds'] and overall<=SHAPE['overall_seconds'],
        scope='lean build; host GL assumed (unimplemented); own-source/serial planning estimate only, '
              'not1000/clock/board or memory guarantee.')


def role():
    # Complete immutable OWN pilot capture; no current protected re-emission.
    raw = read(PILOT_DIR/'manifest.json')
    files = {name: (PILOT_DIR/'source/fpga'/name).read_bytes() for name in raw['sources']}
    need(all(sha(data) == raw['sources'][name] for name, data in files.items()), 'OWN_PILOT_CAPTURE')
    files[pilot.HEADER] = header(files[pilot.HEADER])
    files[SELF] = (ROOT/SELF).read_bytes()
    manifest = copy.deepcopy(raw)
    full_validator_config = copy.deepcopy(raw['steps'][0]['validator']['config'])
    full_validator_config['parent_config'] = config()
    manifest['steps'] = [dict(name=STEP, argv=['{exe}'], expected_returncode=0,
        validator=dict(source=pilot.SELF, function='validate', config=full_validator_config, assets={}))]
    manifest['sources'] = {name: sha(data) for name,data in files.items()}
    manifest['r84']['continuous'] = dict(count_per_context=COUNT, model_threads=THREADS,
        production_and_cpp_unchanged=True, compiled_source_delta=[pilot.HEADER],
        original_header_sha256=raw['sources'][pilot.HEADER], full_header_sha256=manifest['sources'][pilot.HEADER],
        deterministic_prefix_equal=True, initial_resets=1, initial_load_words=131072,
        descriptors=1998, bases=BASES, no_reload_or_checkpoint_barrier=True,
        full_N_numeric_locally_performed=False)
    manifest['lean_production']['own_serial_pilot'].update(count_per_context=COUNT, descriptors=1998,
        own_measured_forecast_pending=False, label=pilot.LABEL)
    manifest['rtl_readiness']['candidate_id'] = 's4-p16-c2-lean-r7-continuous1000-v1'
    names = set(manifest['build']['sv_sources']) | {pilot.CPP, 'rtl/tb/native_runtime_context_v1.h',
        'rtl/tb/stream27_host_chain_full_reference_v1.h', 'rtl/tb/stream27_shared_reference_ntt_v1.h'}
    need(len(manifest['build']['sv_sources']) == 56 and
         all(manifest['sources'][name] == raw['sources'][name] for name in names), 'OWN56_CPP_REFERENCE_RUNTIME')
    return manifest, files


def forecast(manifest):
    approved, report, gate = [read(path) for path in (RAW/'approved-manifest.json', RAW/'report.json', PILOT_GATE)]
    pins = {key: sha(path.read_bytes()) for key,path in (
        ('pilot_manifest',RAW/'approved-manifest.json'), ('pilot_report',RAW/'report.json'), ('pilot_gate',PILOT_GATE))}
    need(gate['status'] == 'PASS_expected_contracts' and gate['manifest_sha256'] == pins['pilot_manifest'],
         'OWN_TYPED_MANIFEST')
    need(gate['report_sha256'] == pins['pilot_report'] and report['manifest_sha256'] == pins['pilot_manifest']
         and report['host'] == 'gfn16-pilot-c4d' and report['model_threads'] == THREADS,
         'OWN_RAW_REPORT_THREADS_HOST')
    row = [entry for entry in report['steps'] if entry['name'] == PILOT_STEP]
    typed = [entry for entry in gate['steps'] if entry['name'] == PILOT_STEP]
    need(len(row) == len(typed) == 1 and row[0]['returncode'] == typed[0]['actual_returncode'] == 0
         and row[0]['error'] is None, 'OWN100_COMMAND')
    value = typed[0]['validation']
    need(value['build_label'] == pilot.LABEL and not value['host_gl_implemented']
         and value['measurements']['count_per_context'] == 100 and value['measurements']['interval'] == 8459,
         'OWN_LEAN_TYPED_PILOT')
    names = set(manifest['build']['sv_sources']) | {pilot.CPP, 'rtl/tb/native_runtime_context_v1.h',
        'rtl/tb/stream27_host_chain_full_reference_v1.h', 'rtl/tb/stream27_shared_reference_ntt_v1.h'}
    need(all(manifest['sources'][name] == approved['sources'][name] for name in names), 'ACTUAL_SAME_MODEL_SOURCE')
    full_config = config()
    need(manifest['steps'][0]['validator']['config']['parent_config'] == full_config,
         'EXACT_OWN_FULL_CONFIG')
    command, overall = row[0]['seconds'], report['seconds']
    need(type(command) in (int,float) and type(overall) in (int,float) and 0 < command <= overall < 3700,
         'FINITE_MEASURED_PHASES')
    plan = predict(command,overall)
    need(plan['fits_finite_shape'], 'OWN_FORECAST_EXCEEDS_EXISTING_SHAPE')
    return dict(schema=SCHEMA, status='PASS_C2_own100_measured_continuous_forecast', generator=SELF,
        generator_sha256=sha((ROOT/SELF).read_bytes()), compatible_hosts=[report['host']], model_threads=THREADS,
        short_manifest_sha256=pins['pilot_manifest'], short_report_sha256=pins['pilot_report'],
        short_gate_sha256=pins['pilot_gate'], source_model_build=manifest['build'],
        source_model_pins={name:manifest['sources'][name] for name in sorted(names)}, pilot_native_validation=value,
        allowed_compiled_delta=dict(path=pilot.HEADER, pilot_sha256=approved['sources'][pilot.HEADER],
                                   full_sha256=manifest['sources'][pilot.HEADER]), full_config=full_config, forecast=plan,
        lean_build_label=pilot.LABEL, host_gl_implemented=False, promotion_allowed=False)


def prepare_role(output):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'FRESH_OUTPUT')
    manifest, files = role()
    measured = forecast(manifest)
    source = out/'source/fpga'
    source.mkdir(parents=True)
    for name,data in files.items():
        path = source/name
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
    manifest['source_root'] = str(source)
    dump(out/'manifest.json',manifest)
    dump(out/'forecast.json',measured)
    return dict(manifest=str(out/'manifest.json'), forecast=str(out/'forecast.json'),
                label=pilot.LABEL, forecast_summary=measured['forecast'], status='PREPARED_NOT_NATIVE')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_role(args.output),indent=2))
