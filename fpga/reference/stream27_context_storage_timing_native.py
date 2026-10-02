"""Source-specific clean timing58 + storage2 normal roles from immutable admitted captures.

No generator re-emission, HDL execution, fullN numeric generation or launcher.
The existing public queue owns all-compatible preparation and actual dispatch.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from . import stream27_context_storage_timing_bind as binder

ROOT = binder.ROOT
SELF = 'reference/stream27_context_storage_timing_native.py'
DONORS = {
    'aw8': ('results/throughput-20260929/trackS-c2-timing-v1/aw8-normal-v1',
            '1716be3e4ac59620a4b03c50b61e23976fa89600ec345a59ea739d5b7c03619d'),
    'full': ('results/throughput-20260929/trackS-c2-timing-v1/full-normal-v1',
             '06160c4cafce4c801a15de9bce0fdbf9926a8e292c90136c8e27857d8cc94acf')}
IDS = {stage: 's4-p16-c2-timing-storage2-' + stage + '-normal-q1-v1' for stage in DONORS}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def need(ok, label):
    if not ok:
        raise ValueError('C2_STORAGE_NATIVE_' + label)


def capture(stage):
    need(stage in DONORS, 'AW8_FULL_ONLY')
    relative, pin = DONORS[stage]
    base = ROOT / relative
    raw = (base / 'manifest.json').read_bytes()
    need(sha(raw) == pin, 'IMMUTABLE_CAPTURE_MANIFEST')
    manifest = json.loads(raw)
    files = {}
    for name, digest in manifest['sources'].items():
        path = base / 'source/fpga' / name
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'SOURCE_PATH')
        data = path.read_bytes()
        need(sha(data) == digest, 'SOURCE_SHA:' + name)
        files[name] = data
    meta = manifest['context_timing']
    generated = meta['production_generated_sha256']
    top = meta['production_top']
    production = {name: files['rtl/' + name].decode() for name in generated}
    need(len(production) == 58 and all(sha(text.encode()) == generated[name] for name, text in production.items()), 'PRODUCTION58')
    bundle = json.loads((base / 'production-bundle.json').read_text())
    need(bundle['files'] == production and bundle['top'] == top, 'CAPTURED_TIMING_BUNDLE')
    return manifest, files, bundle


def role(stage):
    manifest, files, parent = capture(stage)
    original = copy.deepcopy(manifest)
    source = binder.bind(parent, enabled=1)
    oldtop, newtop = parent['top'], source['top']
    for name in parent['rtl_sources']:
        files.pop('rtl/' + name)
    files.update({'rtl/' + name: text.encode() for name, text in source['files'].items()})
    # Full observer has no state and retains its identical external C++ ABI.
    # AW8 has no observer; only its DUT/header identifier changes.
    if stage == 'full':
        observer = manifest['build']['top']
        files['rtl/' + observer + '.sv'] = binder.transform.re_identifier(
            files['rtl/' + observer + '.sv'].decode(), oldtop, newtop).encode()
        sv_sources = ['rtl/' + name for name in source['rtl_sources']] + ['rtl/' + observer + '.sv']
    else:
        header = 'rtl/tb/s4_host_contexts_config_v1.h'
        text = files[header].decode()
        need(text.count(oldtop) == 2, 'AW8_DUT_IDENTIFIER')
        files[header] = text.replace(oldtop, newtop).encode()
        manifest['build']['top'] = newtop
        sv_sources = ['rtl/' + name for name in source['rtl_sources']]
    manifest['build']['sv_sources'] = sv_sources
    for name in (binder.transform.SELF, 'reference/stream27_c2_state_analysis.py', binder.SELF, SELF):
        files['lineage/' + name] = (ROOT / name).read_bytes()
    manifest['sources'] = {name: sha(data) for name, data in files.items()}
    ready = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    snapshot = {name: pin for name, pin in manifest['sources'].items() if name.endswith('.sv')}
    manifest['rtl_readiness'] = dict(schema='gfn16-candidate-rtl-ready-v1',
        candidate_id=IDS[stage].removesuffix('-q1-v1'), source_snapshot=snapshot,
        candidate_source_sha256=sha(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()),
        rtl_ready_at_utc=ready)
    manifest['context_timing'].update(production_top=newtop, production_generated_sha256=source['generated_sha256'])
    manifest['source_root'] = 'UNBOUND'
    manifest['output_parent'] = 'UNBOUND'
    manifest['test_role'] = 'normal'
    manifest['timing_storage2'] = dict(parent_manifest_sha256=DONORS[stage][1], parent_directory=DONORS[stage][0],
        production_top=newtop, production_generated_sha256=source['generated_sha256'],
        contract=source['storage_contract'], geometry=source['geometry'],
        unchanged_bench_reference_probe_steps=True, default_parent_qualification_not_inherited=True,
        wholefit_released=False, promotion_allowed=False)
    need(manifest['steps'] == original['steps'] and manifest['probe'] == original['probe'], 'EXACT_NORMAL_ORACLE_CONTRACT')
    need(manifest['build']['parameters'] == original['build']['parameters'], 'UNCHANGED_GEOMETRY_PARAMETERS')
    return manifest, files, source


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def prepare(output, stage):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'FRESH_CONTAINED_OUTPUT')
    need(not any((ROOT / path).exists() for path in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'PAUSE')
    manifest, files, source = role(stage)
    snapshot = out / 'source/fpga'
    snapshot.mkdir(parents=True)
    for name, raw in files.items():
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    manifest['source_root'] = str(snapshot)
    dump(out / 'manifest.json', manifest)
    dump(out / 'production-bundle.json', source)
    dump(out / 'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static' + pair + '-v1'
        worker = 's4-p16-c2-timing-storage2-' + stage + '-' + pair + '-v1'
        packet = out / ('packet-' + pair)
        result = package.prepare(out / 'manifest.json', snapshot, profile, worker, 'run', packet, out / 'host-hours.json')
        ticket = json.loads((packet / 'ticket.json').read_text())
        variants.append(dict(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=ticket['native_root'], runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT / 'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT / 'tools/native_package_v4.py'), stager_sha256=sha((ROOT / 'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT / name), sha256=sha((ROOT / name).read_bytes()))
                for name in ('tools/native_package_v3.py', 'tools/native_package_v2.py')], max_seconds=3700))
    logical = dict(schema='gfn16-global-ticket-v1', id=IDS[stage], owner='independent-review',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P1', kind='sim',
        needs='verilator', tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=8,
        minimum_ram_rationale='Existing bounded serial C2 normal; no parent measured peak sizing credit.',
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
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.stage), indent=2))
