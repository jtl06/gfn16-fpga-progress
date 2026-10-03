"""Own R7 normal-first roles from immutable R6 captures; no shared writes.

Rebind exact production graph and native-only identifiers/observer parameter.
All captured C++/reference/probe/step contracts remain unchanged. Preparation
does not execute HDL or inherit R2/R3/R5 numerical, fault, pilot or clock results.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
SELF = 'reference/stream27_context_storage_combo_faultlocal_native.py'
BINDER = 'reference/stream27_context_storage_combo_faultlocal_bind.py'
BINDER_PIN = '847dc928e3c84e565d8971fbd05e65ff2e3d50627e0d8b8347ff2ae025918d06'
READY = '2026-10-02T14:08:53Z'
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-oneshot-native-v1'
DONORS = {
    'aw8': ('e474173543888a3a6936df81af97f4c127284348e0fcadb06e2c972dbcbe2f7e',
            'adb0a1490b84a7f517678300160e1cfe221620ac9388fd378bc60d90bf616345'),
    'full': ('57f33da990b668b127498f0525b4d367d4531c5297278906b9c64f38a122ec8f',
             '4abcfdfc3d32c650019f385ec16b0d9462874ff65607c1f1bebd573a746b7a70')}
IDS = {s: 's4-p16-c2-combo-r7-' + s + '-normal-q1-v1' for s in DONORS}


def need(ok, why):
    if not ok:
        raise ValueError('C2_R7_NATIVE_' + why)


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
    need((sha(manifest_raw), sha(bundle_raw)) == DONORS[stage], 'IMMUTABLE_R6_CAPTURE')
    manifest, bundle = json.loads(manifest_raw), json.loads(bundle_raw)
    files = {}
    for name, digest in manifest['sources'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'SOURCE_PATH')
        raw = (directory / 'source/fpga' / name).read_bytes()
        need(sha(raw) == digest, 'CAPTURE_SOURCE:' + name)
        files[name] = raw
    meta = manifest['context_storage_combo_loadlocal']
    need(bundle['generated_sha256'] == meta['production_generated_sha256'] and
         bundle['top'] == meta['production_top'] and len(bundle['files']) == 55 and
         all(files['rtl/' + n] == text.encode() for n, text in bundle['files'].items()),
         'EXACT_R6_PRODUCTION55')
    return manifest, files, bundle


def role(stage):
    from fpga.reference import stream27_context_storage_combo_faultlocal_bind as core
    need(sha((ROOT / BINDER).read_bytes()) == BINDER_PIN, 'CORE_FREEZE')
    manifest, files, captured = capture(stage)
    before = copy.deepcopy(manifest)
    # JSON capture serializes schedule tuples as lists. Reconstruct the pinned
    # parent's Python representation ONLY after complete canonical equality;
    # its SV map, flags and all metadata must match the immutable capture.
    parent = core.oneshot.prepare(captured['geometry']['n'], enabled=1)
    need(json.loads(json.dumps(parent)) == captured, 'CAPTURE_EQUALS_PINNED_R6_REPRESENTATION')
    production = core.bind(parent, enabled=1)
    parameters = {k: v for k, v in before['build']['parameters'].items()
                  if k not in ('EPOCH_SEED0', 'EPOCH_SEED1')}
    need(production['geometry'] == captured['geometry'] and len(production['files']) == 55 and
         production['parameters'] == dict(parameters, COMM_OWNER_COMPARE_LOCAL=1), 'ONLY_COMPARE_BEFORE_PHASE_DELTA')
    contract = production['context_storage_combo_faultlocal']
    need(contract['reverse_to_parent_exact'] and contract['comparison_full_valid_owner_generation'] and
         contract['data_and_tag_routing_unchanged'] and contract['all_register_reset_fault_publication_edges_exact'] and
         contract['calendar_delta'] == 0 and contract['no_new_registers_or_delayed_faults'] and
         contract['stage_instances'] == 6*(production['geometry']['aw']-4), 'EXACT_OWNER_FAULT_EDGE_CONTRACT')
    oldtop, newtop = captured['top'], production['top']
    cpp = files[manifest['build']['cpp_source']]
    for name in captured['generated_sha256']:
        files.pop('rtl/' + name)
    files.update({'rtl/' + n: text.encode() for n, text in production['files'].items()})
    sv = ['rtl/' + n for n in production['rtl_sources']]
    if stage == 'aw8':
        header = 'rtl/tb/s4_host_contexts_config_v1.h'
        text = files[header].decode()
        need(text.count(oldtop) == 2 and 'INTERVAL=213,FIRST_DIGIT=194,CARRY_DONE=213' in text,
             'AW8_CAPTURED_IDENTIFIER_CALENDAR')
        files[header] = text.replace(oldtop, newtop).encode()
        manifest['build']['top'] = newtop
    else:
        observer = manifest['build']['top']
        text = files['rtl/' + observer + '.sv'].decode()
        text, count = re.subn(r'\b' + re.escape(oldtop) + r'\b', newtop, text)
        need(count == 1 and not re.search(r'\b(always|always_ff|always_comb|initial)\b', text),
             'STATELESS_OBSERVER_EXACT_ROOT')
        text = once(text, 'CANONICAL_LOAD_LOCAL=1,', 'CANONICAL_LOAD_LOCAL=1,COMM_OWNER_COMPARE_LOCAL=1,')
        text = once(text, '.CANONICAL_LOAD_LOCAL(CANONICAL_LOAD_LOCAL),',
                    '.CANONICAL_LOAD_LOCAL(CANONICAL_LOAD_LOCAL),\n  .COMM_OWNER_COMPARE_LOCAL(COMM_OWNER_COMPARE_LOCAL),')
        files['rtl/' + observer + '.sv'] = text.encode()
        sv.append('rtl/' + observer + '.sv')
    manifest['build']['sv_sources'] = sv
    manifest['build']['parameters']['COMM_OWNER_COMPARE_LOCAL'] = 1
    for name, digest in production['source_sha256'].items():
        raw = (ROOT / name).read_bytes()
        need(sha(raw) == digest, 'PINNED_CORE_IMPORT:' + name)
        files['lineage/' + name] = raw
    files['lineage/' + SELF] = (ROOT / SELF).read_bytes()
    manifest['sources'] = {name: sha(raw) for name, raw in files.items()}
    snapshot = {name: pin for name, pin in manifest['sources'].items() if name.endswith('.sv')}
    manifest.update(source_root='UNBOUND', output_parent='UNBOUND', test_role='normal',
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1', candidate_id=IDS[stage].removesuffix('-q1-v1'),
            source_snapshot=snapshot, candidate_source_sha256=sha(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()),
            rtl_ready_at_utc=READY))
    for name in ('context_storage_combo_boundary', 'context_storage_combo_quarantine', 'context_storage_combo_readlocal', 'context_storage_combo_loadlocal', 'context_storage_combo_oneshot'):
        manifest[name].update(production_top=newtop, production_generated_sha256=production['generated_sha256'])
    if stage == 'aw8':
        for name in ('r84_explicit_small', 'host_contexts'):
            manifest[name]['generated_sha256'] = production['generated_sha256']
    else:
        manifest['r84']['production_generated_sha256'] = production['generated_sha256']
        manifest['r84']['native_observer'].update(production_top=newtop,
            production_root_sha256=production['generated_sha256'][newtop + '.sv'])
    manifest['context_storage_combo_faultlocal'] = dict(contract=contract, production_top=newtop,
        production_generated_sha256=production['generated_sha256'], source_sha256=production['source_sha256'],
        geometry=production['geometry'], donor_manifest_sha256=DONORS[stage][0], source_freeze_utc=READY,
        unchanged_cpp_reference_probe_steps=True, donor_numerical_fault_pilot_clock_not_inherited=True,
        full_N_numeric_locally_performed=False, promotion_allowed=False)
    need(manifest['steps'] == before['steps'] and manifest['probe'] == before['probe'] and
         manifest['build']['parameters'] == dict(before['build']['parameters'], COMM_OWNER_COMPARE_LOCAL=1) and
         files[before['build']['cpp_source']] == cpp, 'UNCHANGED_NORMAL_ORACLE_AND_PROBE')
    return manifest, files, production


def prepare(output, stage):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'FRESH_OUTPUT')
    need(not any((ROOT / p).exists() for p in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'PAUSE')
    manifest, files, production = role(stage)
    source = out / 'source/fpga'
    source.mkdir(parents=True)
    for name, raw in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    manifest['source_root'] = str(source)
    dump(out / 'manifest.json', manifest)
    dump(out / 'production-bundle.json', production)
    dump(out / 'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static' + pair + '-v1'
        worker = 's4-p16-c2-combo-r7-' + stage + '-' + pair + '-v1'
        packet = out / ('packet-' + pair)
        result = package.prepare(out / 'manifest.json', source, profile, worker, 'run', packet, out / 'host-hours.json')
        ticket = json.loads((packet / 'ticket.json').read_text())
        variants.append(dict(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=ticket['native_root'], runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT / 'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT / 'tools/native_package_v4.py'), stager_sha256=sha((ROOT / 'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT / p), sha256=sha((ROOT / p).read_bytes()))
                for p in ('tools/native_package_v3.py', 'tools/native_package_v2.py')], max_seconds=3700))
    logical = dict(schema='gfn16-global-ticket-v1', id=IDS[stage], owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P1', kind='sim', needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1', allowed_hosts=['gfn16-pilot-c4d', 'aethia'],
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=4,
        minimum_ram_rationale='Bounded N256 exploratory4GiB cap; no measured peak or full-N sizing inheritance.' if stage == 'aw8'
            else 'Bounded exploratory4GiB fullN cap: same C2 geometry/two new control bits, earlier own full gates peaked under3GiB; not a sufficiency/PASS promise. DesiredGCP8 unchanged; preserve OOM/timeout.',
        est_minutes=25, promotion_bound=False, test_role='normal', rtl_readiness=manifest['rtl_readiness'], packages=variants)
    if stage == 'full':
        logical.update(after=[IDS['aw8']], on='PASS_expected_contracts')
    dump(out / 'global-ticket.json', logical)
    return dict(id=IDS[stage], ticket=str(out / 'global-ticket.json'), production_rtl=55,
                compiled_rtl=len(manifest['build']['sv_sources']), status='PREPARED_NOT_NATIVE')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=('aw8', 'full'), required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.stage), indent=2))

