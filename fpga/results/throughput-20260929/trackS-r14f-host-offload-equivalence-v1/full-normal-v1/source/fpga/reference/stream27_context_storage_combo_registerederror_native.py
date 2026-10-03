"""R9 own normal-first harness; disabled until the producer contract is frozen.

Captured R7 inputs are source/reference donors only. No numerical result or
clock is inherited. No HDL or full-N arithmetic is executed during preparation.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
SELF = 'reference/stream27_context_storage_combo_registerederror_native.py'
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-native-v1'
BINDER = 'reference/stream27_context_storage_combo_registerederror_bind.py'
BINDER_PIN = '3a507134f0a68fa393653ca1f8c7ac6e7fe7288d1f5ad0e7e36dc9657cf2a865'
READY = '2026-10-02T17:33:18Z'
CONTRACT_KEY = 'context_registered_error'
NEW_PARAMETERS = dict(CANONICAL_C0_DIRECT=1, ERROR_AGGREGATION_REGISTERED=1)
PUBLICATION_FENCE = 1
PRODUCTION_COUNT = 55
DONORS = {
    'aw8': ('80063877960064da299a3aeb9b5204b2f4244c6fbddfdea95d57be6b725ad8b9',
            '7f17f9e1410eac6d1fbfc3909717bbd28296e943833b15230aeab53dcc625608'),
    'full': ('08ed54df8c3336b56d0c1c391e84e016c9d99b792f906635e89b0c5ff90bcdb3',
             'e2671f87b4f6173dbfebd5eb30ddfbe0113cb78fe692d4b594d2492e60c343e7'),
}
IDS = {stage: 's4-p16-c2-combo-r9-' + stage + '-normal-q1-v1' for stage in DONORS}


def need(ok, why):
    if not ok:
        raise ValueError('C2_R9_NATIVE_' + why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def once(text, before, after):
    need(text.count(before) == 1, 'UNIQUE_ANCHOR:' + before[:48])
    return text.replace(before, after, 1)


def capture(stage):
    need(stage in DONORS, 'AW8_FULL_ONLY')
    directory = BASE / (stage + '-normal')
    manifest_raw = (directory / 'manifest.json').read_bytes()
    bundle_raw = (directory / 'production-bundle.json').read_bytes()
    need((sha(manifest_raw), sha(bundle_raw)) == DONORS[stage], 'IMMUTABLE_SOURCE_DONOR')
    manifest, bundle = json.loads(manifest_raw), json.loads(bundle_raw)
    files = {}
    for name, digest in manifest['sources'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'SOURCE_PATH')
        raw = (directory / 'source/fpga' / name).read_bytes()
        need(sha(raw) == digest, 'CAPTURE_SOURCE:' + name)
        files[name] = raw
    need(len(bundle['files']) == 55 and
         all(files['rtl/' + name] == text.encode() for name, text in bundle['files'].items()),
         'EXACT_PRODUCTION_DONOR')
    runtime_before_model(files[manifest['build']['cpp_source']].decode())
    return manifest, files, bundle


def runtime_before_model(text):
    """The actual C++ must configure its context before every DUT constructor."""
    need('gfn16_runtime::configure(context,argc,argv)' in text, 'RUNTIME_CONFIGURE')
    constructors = list(re.finditer(r'\bDUT\s+\w+\s*[({]', text))
    need(len(constructors) == 1 and text.index('gfn16_runtime::configure(context,argc,argv)') <
         constructors[0].start() and 'gfn16_runtime::matches(context,d)' in text,
         'RUNTIME_BEFORE_EVERY_MODEL')


def require_freeze():
    need(READY != 'SOURCE_NOT_FROZEN' and BINDER != 'SOURCE_NOT_FROZEN' and
         CONTRACT_KEY != 'SOURCE_NOT_FROZEN' and type(NEW_PARAMETERS) is dict and
         type(PUBLICATION_FENCE) is int and type(PRODUCTION_COUNT) is int, 'EXACT_PRODUCER_FREEZE_REQUIRED')
    need(sha((ROOT / BINDER).read_bytes()) == BINDER_PIN, 'PRODUCER_PIN')


def config():
    require_freeze()
    return dict(aw=16, p=16, contexts=2, bases=[604832956, 999999937], count=2,
                interval=8459, publication_fence_edges=PUBLICATION_FENCE)


def publication(warm_edges, rows, n, fence):
    """Source calendar seam; final frozen producer must prove this formula."""
    release = -1
    done = []
    for warm in warm_edges:
        release = max(warm + 2, release + 1) + rows + 10*n + 6 + fence
        done.append(release)
    return done


def validate(stdout, stderr, rc, config, assets):
    # On a worker only literal frozen constants are used; no generator import.
    expected_config = dict(aw=16, p=16, contexts=2, bases=[604832956, 999999937], count=2,
                           interval=8459, publication_fence_edges=PUBLICATION_FENCE)
    need(config == expected_config and assets == {} and type(PUBLICATION_FENCE) is int, 'CONFIG')
    need(type(rc) is int and rc == 0 and stderr == '' and stdout.startswith('R84_C2_FULL_PASS ')
         and stdout.endswith('\n') and '\n' not in stdout[:-1], 'EXACT_NORMAL_OUTPUT')
    value = json.loads(stdout.removeprefix('R84_C2_FULL_PASS '))
    fixed = dict(aw=16, p=16, contexts=2, bases=[604832956, 999999937], squares=8, reads=393216,
                 signed96=True, context_alone_bit_identical=True, independent_reference=True,
                 interval=8459, pair_launch_cycles=8459, peer_live_reads=65536, model_threads=1)
    variable = {'launches', 'single_cycles', 'joint_cycles', 'overlap_edges', 'done_edges',
                'warm_edges', 'setup_edges', 'single_first', 'seconds'}
    need(set(value) == set(fixed) | variable and
         all(value[k] == v and type(value[k]) is type(v) for k, v in fixed.items()), 'COUNTS_AND_KEYS')
    need(value['launches'] == [[204, 8663], [4433, 12892]] and value['setup_edges'] == [99, 199] and
         value['warm_edges'] == [21221, 25450] and value['single_first'] == [104, 104], 'SOURCE_WARM_CALENDAR')
    done = publication(value['warm_edges'], 4096, 65536, PUBLICATION_FENCE)
    single_done = publication([104+8459+12558], 4096, 65536, PUBLICATION_FENCE)[0]
    need(value['done_edges'] == done and value['joint_cycles'] == done[-1] + 65536 and
         value['single_cycles'] == [single_done+65536]*2 and
         value['overlap_edges'] == done[0]-1, 'EXACT_PUBLICATION_FENCE')
    need(type(value['seconds']) in (int, float) and math.isfinite(value['seconds']) and
         0 < value['seconds'] < 3700, 'FINITE_TIME')
    return dict(status='PASS_expected_contracts', measurements=value, promotion_allowed=False,
                scope='OWN R9 source/cycles, SAME C2 alone/joint and independent reference; no ancestor qualification.')


def role(stage):
    require_freeze()
    core = importlib.import_module('fpga.' + BINDER.removesuffix('.py').replace('/', '.'))
    manifest, files, parent = capture(stage)
    before = copy.deepcopy(manifest)
    production = core.prepare(parent['geometry']['n'], p=16, contexts=2, enabled=1)
    need(len(production['files']) == PRODUCTION_COUNT and
         production['parameters'] == dict(parent['parameters'], **NEW_PARAMETERS), 'EXACT_OWN_PARAMETERS')
    for key in ('n', 'p', 'rows', 'warm_interval', 'first_digit', 'carry_done'):
        need(production['geometry'][key] == parent['geometry'][key], 'WARM_GEOMETRY:' + key)
    need(CONTRACT_KEY in production, 'PRODUCER_EXECUTABLE_CONTRACT')
    contract = production[CONTRACT_KEY]
    need(contract['arithmetic_raw_field_checks_and_controllers_literal'] and
         contract['early_barrier_registered_sources_only'] and
         contract['public_error_max_added_edges'] == 1 and
         contract['healthy_warm_and_cold_calendar_delta'] == 0 and
         contract['publication_fence_edges_per_job'] == PUBLICATION_FENCE and
         contract['copy_cycles_extra_per_job'] == PUBLICATION_FENCE and
         contract['joint_publication_delta'] == [1, 2] and
         contract['solo_publication_delta'] == 1 and
         contract['full56_publication_owner_count_lease_check'] and
         contract['reset_and_newjob_clear'] and contract['public_ports_unchanged'] and
         contract['reverse_to_protected_R7_exact'], 'SOURCE_BARRIER_AND_PUBLICATION_CONTRACT')
    oldtop, newtop = parent['top'], production['top']
    for name in parent['generated_sha256']:
        files.pop('rtl/' + name)
    files.update({'rtl/' + name: text.encode() for name, text in production['files'].items()})
    sv = ['rtl/' + name for name in production['rtl_sources']]
    if stage == 'aw8':
        header = 'rtl/tb/s4_host_contexts_config_v1.h'
        text = files[header].decode()
        need(text.count(oldtop) == 2, 'SMALL_TOP_IDENTIFIER')
        files[header] = text.replace(oldtop, newtop).encode()
        manifest['build']['top'] = newtop
    else:
        observer = manifest['build']['top']
        text = files['rtl/' + observer + '.sv'].decode()
        text, count = re.subn(r'\b' + re.escape(oldtop) + r'\b', newtop, text)
        need(count == 1 and not re.search(r'\b(always|always_ff|always_comb|initial)\b', text),
             'TRANSPARENT_OBSERVER')
        for parameter, default in NEW_PARAMETERS.items():
            text = once(text, 'COMM_OWNER_COMPARE_LOCAL=1,',
                        'COMM_OWNER_COMPARE_LOCAL=1,' + parameter + '=' + str(default) + ',')
            text = once(text, '.COMM_OWNER_COMPARE_LOCAL(COMM_OWNER_COMPARE_LOCAL),',
                        '.COMM_OWNER_COMPARE_LOCAL(COMM_OWNER_COMPARE_LOCAL),\n  .' + parameter + '(' + parameter + '),')
        files['rtl/' + observer + '.sv'] = text.encode()
        sv.append('rtl/' + observer + '.sv')
    cpp = manifest['build']['cpp_source']
    text = files[cpp].decode()
    text = once(text, 'lane64(d.image_copy_cycles,ctx)==N+3',
                'lane64(d.image_copy_cycles,ctx)==N+' + str(3+PUBLICATION_FENCE))
    runtime_before_model(text)
    files[cpp] = text.encode()
    manifest['build']['sv_sources'] = sv
    manifest['build']['parameters'].update(NEW_PARAMETERS)
    for name, digest in production['source_sha256'].items():
        raw = (ROOT / name).read_bytes()
        need(sha(raw) == digest, 'PRODUCER_IMPORT:' + name)
        files['lineage/' + name] = raw
    files[SELF] = (ROOT / SELF).read_bytes()
    manifest['sources'] = {name: sha(raw) for name, raw in files.items()}
    snapshot = {name: digest for name, digest in manifest['sources'].items() if name.endswith('.sv')}
    manifest.update(source_root='UNBOUND', output_parent='UNBOUND', test_role='normal',
                    rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',
                        candidate_id=IDS[stage].removesuffix('-q1-v1'), source_snapshot=snapshot,
                        candidate_source_sha256=sha(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()),
                        rtl_ready_at_utc=READY))
    for key, value in manifest.items():
        if isinstance(value, dict) and 'production_generated_sha256' in value:
            value.update(production_top=newtop, production_generated_sha256=production['generated_sha256'])
    if stage == 'aw8':
        for key in ('r84_explicit_small', 'host_contexts'):
            manifest[key]['generated_sha256'] = production['generated_sha256']
    else:
        manifest['r84']['native_observer'].update(production_top=newtop,
            production_root_sha256=production['generated_sha256'][newtop + '.sv'])
        manifest['steps'][0].update(name='normal-full-c2-r9-alone-and-joint',
            validator=dict(source=SELF, function='validate', config=config(), assets={}))
    manifest[CONTRACT_KEY] = dict(contract=production[CONTRACT_KEY], production_top=newtop,
        production_generated_sha256=production['generated_sha256'], source_sha256=production['source_sha256'],
        geometry=production['geometry'], source_freeze_utc=READY, donor_manifest_sha256=DONORS[stage][0],
        donor_results_not_inherited=True, cpp_delta='Only source-proved copy/publication drain cost assertion.',
        runtime_context_explicitly_configured_before_every_model=True, full_N_numeric_locally_performed=False,
        promotion_allowed=False)
    need(manifest['probe'] == before['probe'] and
         manifest['build']['parameters'] == dict(before['build']['parameters'], **NEW_PARAMETERS),
         'PROBE_AND_EXACT_PARAMETERS')
    return manifest, files, production


def prepare(output, stage):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    require_freeze()
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'FRESH_OUTPUT')
    need(not any((ROOT / p).exists() for p in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'PAUSE')
    manifest, files, production = role(stage)
    source = out / 'source/fpga'
    source.mkdir(parents=True)
    for name, raw in files.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    manifest['source_root'] = str(source)
    dump(out / 'manifest.json', manifest)
    dump(out / 'production-bundle.json', production)
    dump(out / 'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static' + pair + '-v1'
        worker = 's4-p16-c2-combo-r9-' + stage + '-' + pair + '-v1'
        packet = out / ('packet-' + pair)
        result = package.prepare(out / 'manifest.json', source, profile, worker, 'run', packet, out / 'host-hours.json')
        native_ticket = json.loads((packet / 'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=native_ticket['native_root'],
            runner='tools/native_class_package_v2.py', runner_sha256=sha((ROOT / 'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT / 'tools/native_package_v4.py'), stager_sha256=sha((ROOT / 'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT / p), sha256=sha((ROOT / p).read_bytes()))
                                 for p in ('tools/native_package_v3.py', 'tools/native_package_v2.py')], max_seconds=3700))
    ticket = dict(schema='gfn16-global-ticket-v1', id=IDS[stage], owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P1', kind='sim', needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1', allowed_hosts=['gfn16-pilot-c4d', 'aethia'],
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=4,
        minimum_ram_rationale='Bounded exploratory4GiB normal cap with desiredGCP8 preserved; not measured R9 RAM/PASS. Retain OOM/timeout.',
        est_minutes=25, promotion_bound=False, test_role='normal', rtl_readiness=manifest['rtl_readiness'], packages=variants)
    if stage == 'full':
        ticket.update(after=[IDS['aw8']], on='PASS_expected_contracts')
    dump(out / 'global-ticket.json', ticket)
    return dict(id=IDS[stage], ticket=str(out / 'global-ticket.json'), production_sv=len(production['files']),
                compiled_sv=len(manifest['build']['sv_sources']), status='PREPARED_NOT_NATIVE')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=('aw8', 'full'), required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.stage), indent=2))
