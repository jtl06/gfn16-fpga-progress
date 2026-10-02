"""Source-specific C2 timing transfer native adapter (no generator writes).

Immutable corrected C2 normal captures supply the benches and independent
oracles. Only the production source graph and source-derived calendar change.
The native profile observer stays read-only and is never a physical wrapper.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_timing_native.py'
DONORS = {
    'aw8': ('artifacts/s4-p16-c2-explicit-aw8-normal-v1',
            'f4831d7113001ae41581dc469052cd6c4ca9e929697927fc7a8e62c14e642f98'),
    'full': ('artifacts/s4-p16-c2-explicit-full-normal-v1',
             '9e6d2479033b4b006ea4d98cbf964e6fa81964fa1f904dc35c596c6b4cf5bc57')}
IDS = {stage: 's4-p16-c2-timing-' + stage + '-normal-q1-v1' for stage in DONORS}
BINDER_PIN = 'd2e047d30d6290c46c622c2f69e51cd2c53c0cad36ca5de489696f9c6ef8756a'
RTL_READY = '2026-10-02T05:26:55Z'


def need(ok, label):
    if not ok:
        raise ValueError('C2_TIMING_NATIVE_' + label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def capture(stage):
    need(stage in DONORS, 'AW8_FULL_ONLY')
    relative, pin = DONORS[stage]
    directory = ROOT / relative
    raw = (directory / 'manifest.json').read_bytes()
    need(sha(raw) == pin, 'IMMUTABLE_CAPTURE_MANIFEST')
    manifest = json.loads(raw)
    files = {}
    for name, digest in manifest['sources'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'SOURCE_PATH')
        data = (directory / 'source/fpga' / name).read_bytes()
        need(sha(data) == digest, 'SOURCE_SHA:' + name)
        files[name] = data
    meta = manifest['r84_explicit_small'] if stage == 'aw8' else manifest['r84']
    generated = meta['generated_sha256'] if stage == 'aw8' else meta['production_generated_sha256']
    top = manifest['build']['top'] if stage == 'aw8' else meta['native_observer']['production_top']
    production = {name: files['rtl/' + name].decode() for name in generated}
    need(len(production) == 53 and all(sha(text.encode()) == generated[name]
         for name, text in production.items()), 'PRODUCTION53')
    bundle = dict(top=top, files=production, rtl_sources=list(production), geometry=meta['geometry'],
                  parameters=meta['parameters'], generated_sha256=generated)
    return manifest, files, bundle


def constant(text, name, value):
    pattern = r'\b' + re.escape(name) + r'=\d+'
    result, count = re.subn(pattern, name + '=' + str(value), text)
    need(count == 1, 'ONE_HEADER_CONSTANT:' + name)
    return result


def validator_config(bundle, calendar):
    g = bundle['geometry']
    return dict(aw=16, p=16, contexts=2, bases=[604832956, 999999937], count=2,
                interval=g['warm_interval'], carry_done=g['carry_done'],
                first_edges=calendar['joint_first_edges'], max_edges=3 * 11 * 65536 + 100000)


def validate_full(stdout, stderr, rc, config, assets):
    need(assets == {} and type(rc) is int and rc == 0 and stderr == '', 'NORMAL_RESULT')
    need(stdout.startswith('R84_C2_FULL_PASS ') and stdout.endswith('\n')
         and '\n' not in stdout[:-1], 'ONE_FOOTER')
    value = json.loads(stdout.removeprefix('R84_C2_FULL_PASS '))
    interval = config['interval']
    expected = dict(aw=16, p=16, contexts=2, bases=config['bases'], squares=8,
                    reads=6 * 65536, signed96=True, context_alone_bit_identical=True,
                    independent_reference=True, interval=interval, pair_launch_cycles=interval,
                    peer_live_reads=65536, model_threads=1)
    measured = {'launches', 'single_cycles', 'joint_cycles', 'overlap_edges', 'done_edges',
                'warm_edges', 'setup_edges', 'single_first', 'seconds'}
    need(set(value) == set(expected) | measured, 'FOOTER_KEYS')
    need(all(value[k] == v and type(value[k]) is type(v) for k, v in expected.items()), 'EXACT_COUNTS')
    for name in ('single_cycles', 'done_edges', 'warm_edges', 'setup_edges', 'single_first'):
        need(type(value[name]) is list and len(value[name]) == 2
             and all(type(x) is int and x > 0 for x in value[name]), 'EDGE_VECTOR:' + name)
    launches = value['launches']
    need(type(launches) is list and len(launches) == 2 and all(type(row) is list and len(row) == 2
         and all(type(x) is int and x > 0 for x in row) for row in launches), 'LAUNCH_VECTOR')
    a, b = launches
    need([a[0], b[0]] == config['first_edges'], 'SOURCE_FIRST_EDGES')
    need(a[1] - a[0] == interval and b[1] - b[0] == interval
         and b[0] - a[0] == interval // 2 and a[1] - b[0] == interval - interval // 2, 'PAIR_CALENDAR')
    need(all(value['warm_edges'][c] == launches[c][1] + config['carry_done'] + 1
         and value['setup_edges'][c] < launches[c][0]
         and value['done_edges'][c] > value['warm_edges'][c] + 10 * 65536 for c in range(2)),
         'WARM_SETUP_PUBLICATION')
    need(type(value['joint_cycles']) is int and max(value['done_edges']) + 65536 <= value['joint_cycles']
         < config['max_edges'], 'JOINT_BOUND')
    need(type(value['overlap_edges']) is int and value['overlap_edges'] > 0
         and type(value['seconds']) in (int, float) and math.isfinite(value['seconds'])
         and 0 < value['seconds'] < 3700, 'MEASURED_SCOPE')
    return dict(status='PASS_expected_contracts', measurements=value, promotion_allowed=False,
                scope='Source-specific timing C2 alone/joint and independent native oracle; no inherited clock, long-chain or physical result.')


def adapt(stage, bundle, calendar, freeze):
    """Calendar is mandatory owner-proved input; no inherited schedule defaults."""
    manifest, files, parent = capture(stage)
    original = copy.deepcopy(manifest)
    original_cpp = files[manifest['build']['cpp_source']]
    need(all(bundle['parameters'].get(key) == value for key, value in parent['parameters'].items()),
         'EXACT_PARENT_GEOMETRY_PARAMETERS')
    need(set(bundle['rtl_sources']) <= set(bundle['files']), 'SOURCE_CLOSURE')
    need(all(sha(text.encode()) == bundle['generated_sha256'][name]
             for name, text in bundle['files'].items()), 'GENERATED_PINS')
    need(calendar['stage'] == stage and calendar['geometry'] == bundle['geometry'], 'CALENDAR_GEOMETRY_JOIN')
    need(calendar['schedule_proved'] is True and len(calendar['joint_first_edges']) == 2,
         'ACTUAL_SCHEDULE_PROOF')
    need(freeze['rtl_ready_at_utc'] and freeze['binder_sha256'], 'FREEZE_PIN')
    oldtop, newtop = parent['top'], bundle['top']
    for name in parent['rtl_sources']:
        files.pop('rtl/' + name)
    files.update({'rtl/' + name: text.encode() for name, text in bundle['files'].items()})
    g = bundle['geometry']
    if stage == 'full':
        observer = manifest['build']['top']
        text = files['rtl/' + observer + '.sv'].decode()
        text, count = re.subn(r'\b' + re.escape(oldtop) + r'\b', newtop, text)
        need(count == 1 and not re.search(r'\b(always|always_ff|always_comb|initial)\b', text),
             'TRANSPARENT_PROFILE_OBSERVER')
        files['rtl/' + observer + '.sv'] = text.encode()
        sv_sources = ['rtl/' + name for name in bundle['rtl_sources']] + ['rtl/' + observer + '.sv']
        header = 'rtl/tb/s4_p16_two_context_full_config.h'
        config = validator_config(bundle, calendar)
        manifest['steps'][0]['validator'] = dict(source=SELF, function='validate_full', config=config, assets={})
    else:
        header = 'rtl/tb/s4_host_contexts_config_v1.h'
        text = files[header].decode()
        need(text.count(oldtop) == 2, 'AW8_MODEL_IDENTIFIER')
        files[header] = text.replace(oldtop, newtop).encode()
        manifest['build']['top'] = newtop
        manifest['build']['parameters'] = dict(bundle['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42)
        sv_sources = ['rtl/' + name for name in bundle['rtl_sources']]
    text = files[header].decode()
    for name, value in [('INTERVAL', g['warm_interval']), ('FIRST_DIGIT', g['first_digit']), ('CARRY_DONE', g['carry_done'])]:
        text = constant(text, name, value)
    if stage == 'aw8':
        first = calendar['joint_first_edges']
        text, count = re.subn(r'FIRST\[2\]=\{\d+,\d+\}', 'FIRST[2]={' + ','.join(map(str, first)) + '}', text)
        need(count == 1, 'AW8_FIRST_CALENDAR')
        need(calendar['capture_during_copy'] is True, 'UNCHANGED_AW8_WITNESS')
    files[header] = text.encode()
    files[SELF] = (ROOT / SELF).read_bytes()
    manifest['build']['sv_sources'] = sv_sources
    manifest['sources'] = {name: sha(raw) for name, raw in files.items()}
    snapshot = {name: pin for name, pin in manifest['sources'].items() if name.endswith('.sv')}
    manifest['rtl_readiness'] = dict(schema='gfn16-candidate-rtl-ready-v1', candidate_id=IDS[stage].removesuffix('-q1-v1'),
        source_snapshot=snapshot, candidate_source_sha256=sha(canonical(snapshot)),
        rtl_ready_at_utc=freeze['rtl_ready_at_utc'])
    manifest.update(source_root='UNBOUND', output_parent='UNBOUND', test_role='normal')
    manifest['context_timing'] = dict(parent_manifest_sha256=DONORS[stage][1],
        production_top=newtop, production_generated_sha256=bundle['generated_sha256'],
        calendar=calendar, freeze=freeze, native_observer_is_not_physical=True,
        independent_oracle_and_cpp_unchanged=True, wholefit_released=False,
        parent_qualification_inherited=False, clock_inherited=False, promotion_allowed=False)
    # Keep parent provenance explicit; do not leave an old I8459/current-root
    # claim beside the new source-specific validator and actual graph.
    if stage == 'full':
        meta = manifest['r84']
        meta.update(geometry=g, parameters=bundle['parameters'],
                    production_generated_sha256=bundle['generated_sha256'])
        meta['native_observer'].update(production_top=newtop,
            production_root_sha256=bundle['generated_sha256'][newtop + '.sv'])
    else:
        manifest['r84_explicit_small'].update(geometry=g, parameters=bundle['parameters'],
                                             generated_sha256=bundle['generated_sha256'])
        manifest['host_contexts'].update(geometry=g, generated_sha256=bundle['generated_sha256'],
                                        two_context_schedule=calendar)
    need(manifest['probe'] == original['probe'] and all(manifest['build']['parameters'].get(key) == value
         for key, value in original['build']['parameters'].items()), 'UNCHANGED_RUNTIME_PARAMETERS')
    need(files[manifest['build']['cpp_source']] == original_cpp, 'UNCHANGED_BENCH')
    return manifest, files


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def emitted_inputs(stage):
    from fpga.reference import stream27_context_timing_bind as binder
    need(stage in DONORS and sha((ROOT / binder.SELF).read_bytes()) == BINDER_PIN, 'FROZEN_BINDER')
    n = 256 if stage == 'aw8' else 65536
    parent = binder.prepare(n, enabled=0, allow_full_constants=n == 65536)
    need(parent['generated_sha256'] == capture(stage)[2]['generated_sha256'], 'EXACT_CAPTURE_PARENT_MAP')
    bundle = binder.prepare(n, enabled=1, allow_full_constants=n == 65536)
    g = bundle['geometry']
    expected = [214, 195, 214, 79, 153, 78, 18] if stage == 'aw8' else [8460, 8459, 12558, 4207, 8417, 78, 0]
    need([g[k] for k in ('warm_interval', 'first_digit', 'carry_done', 'pointwise_accept',
         'sink_accept', 'correction_cache_latency', 'feedback_delay')] == expected, 'FROZEN_GEOMETRY')
    plan = binder.schedule(g, counts=(3, 14) if stage == 'aw8' else (2, 2))
    need(plan['status'] == 'PASS_MODEL_ONLY', 'OWN_PORT_CALENDAR')
    calendar = dict(stage=stage, geometry=g, schedule_proved=True, schedule=plan,
                    joint_first_edges=[204, 311] if stage == 'aw8' else [204, 4434],
                    solo_first_edges=[104, 104], capture_during_copy=stage == 'aw8')
    if stage == 'aw8':
        a_warm = 204 + 2 * g['warm_interval'] + g['carry_done'] + 1
        copy_first = a_warm + g['rows'] + 6 + 9 * n
        b_capture = 311 + 13 * g['warm_interval'] + g['first_digit'] + 1
        need(copy_first + 8 < b_capture and b_capture + g['rows'] < copy_first + n - 8,
             'OWN_CAPTURE_COPY_WITNESS')
        calendar['capture_copy_witness'] = dict(copy_first=copy_first, b_capture=b_capture,
                                               b_last_capture=b_capture + g['rows'] - 1)
    freeze = dict(rtl_ready_at_utc=RTL_READY, binder_sha256=BINDER_PIN,
                  production_root_sha256=bundle['generated_sha256'][bundle['top'] + '.sv'])
    return bundle, calendar, freeze


def prepare(output, stage, bundle_path=None, calendar_path=None, freeze_path=None):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'FRESH_OUTPUT')
    need(not any((ROOT / path).exists() for path in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'PAUSE')
    supplied = (bundle_path, calendar_path, freeze_path)
    need(all(path is None for path in supplied) or all(path is not None for path in supplied), 'ALL_OR_NO_INPUTS')
    bundle, calendar, freeze = (emitted_inputs(stage) if bundle_path is None else
        [json.loads(Path(path).read_text()) for path in supplied])
    binder = ROOT / 'reference/stream27_context_timing_bind.py'
    need(sha(binder.read_bytes()) == freeze['binder_sha256'], 'ACTUAL_BINDER_SOURCE_PIN')
    manifest, files = adapt(stage, bundle, calendar, freeze)
    files['lineage/reference/stream27_context_timing_bind.py'] = binder.read_bytes()
    for name in bundle.get('source_dependencies', []):
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'DEPENDENCY_PATH')
        raw = (ROOT / name).read_bytes()
        need(sha(raw) == bundle['source_sha256'][name], 'FROZEN_DEPENDENCY:' + name)
        files['lineage/' + name] = raw
    manifest['context_timing']['production_source_sha256'] = bundle.get('source_sha256', {})
    manifest['sources'] = {name: sha(raw) for name, raw in files.items()}
    source = out / 'source/fpga'
    source.mkdir(parents=True)
    for name, raw in files.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    manifest['source_root'] = str(source)
    dump(out / 'manifest.json', manifest)
    dump(out / 'production-bundle.json', bundle)
    dump(out / 'calendar.json', calendar)
    dump(out / 'freeze.json', freeze)
    dump(out / 'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static' + pair + '-v1'
        worker = 's4-p16-c2-timing-' + stage + '-' + pair + '-v1'
        packet = out / ('packet-' + pair)
        result = package.prepare(out / 'manifest.json', source, profile, worker, 'run', packet, out / 'host-hours.json')
        ticket = json.loads((packet / 'ticket.json').read_text())
        variants.append(dict(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=ticket['native_root'], runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT / 'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT / 'tools/native_package_v4.py'), stager_sha256=sha((ROOT / 'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT / name), sha256=sha((ROOT / name).read_bytes()))
                for name in ('tools/native_package_v3.py', 'tools/native_package_v2.py')], max_seconds=3700))
    logical = dict(schema='gfn16-global-ticket-v1', id=IDS[stage], owner='p16-mlab',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P1', kind='sim',
        needs='verilator', tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=8,
        minimum_ram_rationale='Existing bounded serial C2 normal, no inherited measured peak.',
        est_minutes=25, promotion_bound=False, test_role='normal', rtl_readiness=manifest['rtl_readiness'], packages=variants)
    if stage == 'full':
        logical.update(after=[IDS['aw8']], on='PASS_expected_contracts')
    dump(out / 'global-ticket.json', logical)
    return dict(id=IDS[stage], ticket=str(out / 'global-ticket.json'), compiled_rtl=len(manifest['build']['sv_sources']),
                status='source_prepared_not_native', wholefit_released=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=('aw8', 'full'), required=True)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--calendar', type=Path)
    parser.add_argument('--freeze', type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.stage, args.bundle, args.calendar, args.freeze), indent=2))
