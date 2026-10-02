"""Paired native qualification of the selected three literal instance moves."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'results/throughput-20260929/trackS-c2-timing-storage2-v1'
BASE = ROOT / 'results/throughput-20260929/trackS-c2-fault-order-v1'
SELF = 'reference/stream27_context_fault_order_native.py'
BINDER = 'reference/stream27_context_fault_order_bind.py'
BINDER_PIN = 'e5d4864afdb63b3bbaf96a83842dd3d357b3bd3d5e174d8b754e942c93c252e1'
READY = '2026-10-02T07:07:06Z'
DONORS = {
    'aw8-normal': '2be64223e1da3e0ba60a01c45852d8aa964357d72de64d4cacb6f80ca0f542e3',
    'full-normal': 'b6b783e738b992f5165b140c9c2af872ebea467ff5d1e54fdb88e300b63f3496',
    'fault-external': 'b0132d8c2a3c4c9ae6502ec872431ee1740fbde9a418c43ed86d0a879bab2ba5',
    'fault-owner': '452da64197f3177e88d664a0740feac24330f6e8515a66714fe5b162fcd0de6f',
    'fault-reset': 'b8cf63c722c73fa1a4a8d4494417a99ebca079713b48f824cdeadedf196eb2dc',
    'fault-oracle': '120bf502cf8f46d13df7d039a23c0b6344acacde67ed461f2d6628338c4a7c7f',
    'fault-early-cache': 'ce0294c26010487004838b30a7283fd4f6d45f1931667345826d93e556af42f6'}


def need(ok, why):
    if not ok:
        raise ValueError('C2_FAULT_ORDER_NATIVE_' + why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identifier(stage):
    return 's4-p16-c2-fault-order-' + stage + '-q1-v1'


def role(stage):
    from fpga.reference import stream27_context_fault_order_bind as binder
    need(stage in DONORS and sha((ROOT / BINDER).read_bytes()) == BINDER_PIN, 'EXACT_BINDER')
    directory = PARENT / stage
    raw = (directory / 'manifest.json').read_bytes()
    need(sha(raw) == DONORS[stage], 'EXACT_DONOR_MANIFEST')
    manifest = json.loads(raw)
    original = deepcopy(manifest)
    files = {name: (directory / 'source/fpga' / name).read_bytes() for name in manifest['sources']}
    need(all(sha(files[name]) == pin for name, pin in manifest['sources'].items()), 'ALL_DONOR_PINS')
    geometry = 'full-normal' if manifest['build']['parameters']['AW'] == 16 else 'aw8-normal'
    parent = json.loads((PARENT / geometry / 'production-bundle.json').read_bytes())
    bundle = binder.bind(parent, enabled=1)
    changed = []
    for name, text in bundle['files'].items():
        relative = 'rtl/' + name
        donor_text = files[relative].decode()
        if stage == 'fault-early-cache' and name == 'genefer_stream27_shared_warm_aw8_p16_f0_v1_timing_c2_v1_storage2_v1.sv':
            term = 'genefer_stream27_term_context_param_v1_contexts_v1_select_token_v1_storage2_v1'
            need(parent['files'][name].count(term + ' #') == 1
                 and donor_text == parent['files'][name].replace(term + ' #', term + '_earlycache_probe #', 1),
                 'EXACT_FROZEN_EARLYCACHE_PROBE')
            text = binder.reorder(donor_text)
        else:
            need(donor_text == parent['files'][name], 'DONOR_PRODUCTION_JOIN')
        if text != parent['files'][name]:
            need(binder.reverse_root(text) == donor_text, 'REVERSE_EXACT')
            changed.append(relative)
        files[relative] = text.encode()
    need(len(changed) == 3, 'THREE_INSTANCE_MOVES')
    for name in (SELF, BINDER):
        files['lineage/' + name] = (ROOT / name).read_bytes()
    manifest['sources'] = {name: sha(raw) for name, raw in files.items()}
    snapshot = {name: pin for name, pin in manifest['sources'].items() if name.endswith('.sv')}
    manifest['rtl_readiness'] = dict(schema='gfn16-candidate-rtl-ready-v1', candidate_id=identifier(stage).removesuffix('-q1-v1'),
        source_snapshot=snapshot, candidate_source_sha256=sha(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()),
        rtl_ready_at_utc=READY)
    manifest['fault_source_order'] = dict(bundle['fault_source_order'], parent_role_manifest_sha256=DONORS[stage],
        unchanged_bench_probe_parameters_steps=True, compiled_sv=len(manifest['build']['sv_sources']))
    manifest['context_timing']['production_generated_sha256'] = bundle['generated_sha256']
    manifest['timing_storage2']['production_generated_sha256'] = bundle['generated_sha256']
    need(all(manifest[key] == original[key] for key in ('build', 'probe', 'steps', 'test_role')), 'UNCHANGED_NATIVE_CONTRACT')
    return manifest, files, bundle


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def prepare(stage):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    out = BASE / stage
    need(not out.exists() and not any((ROOT / p).exists() for p in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'FRESH_UNPAUSED')
    manifest, files, bundle = role(stage)
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
    dump(out / 'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static' + pair + '-v1'
        worker = 's4-p16-c2-fault-order-' + stage + '-' + pair + '-v1'
        packet = out / ('packet-' + pair)
        result = package.prepare(out / 'manifest.json', source, profile, worker, 'run', packet, out / 'host-hours.json')
        ticket = json.loads((packet / 'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=ticket['native_root'], runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT / 'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT / 'tools/native_package_v4.py'), stager_sha256=sha((ROOT / 'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT / name), sha256=sha((ROOT / name).read_bytes()))
                for name in ('tools/native_package_v3.py', 'tools/native_package_v2.py')], max_seconds=3700))
    logical = dict(schema='gfn16-global-ticket-v1', id=identifier(stage), owner='p16-mlab',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P1', kind='sim',
        needs='verilator', tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=8,
        minimum_ram_rationale='Existing source-bound serial order-only qualification; no measured parent peak credit.',
        est_minutes=25, promotion_bound=False, test_role=manifest['test_role'], rtl_readiness=manifest['rtl_readiness'], packages=variants)
    if stage != 'aw8-normal':
        logical.update(after=[identifier('aw8-normal')], on='PASS_expected_contracts')
    dump(out / 'global-ticket.json', logical)
    return dict(id=logical['id'], ticket=str(out / 'global-ticket.json'), status='PREPARED_NOT_NATIVE')
