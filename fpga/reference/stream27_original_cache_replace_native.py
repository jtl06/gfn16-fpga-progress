"""Separate ORIGINAL53 AW8 replacement-cache query; no production edits.

Replace only cold context0's matching cache token: propose at seed_start and
suppress that owner's genuine row3 token. Arithmetic/products are untouched.
Expected outcome is a finite readiness-substitution counterexample, not a
protective gate or numerical error. Existing normal/long jobs stay independent.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
SELF = 'reference/stream27_original_cache_replace_native.py'
CPP = 'rtl/tb/stream27_original_cache_replace.cpp'
HEADER = 'rtl/tb/original_cache_replace_config_v1.h'
DONOR = ROOT / 'results/throughput-20260929/trackS-c2-storage2-native-v1/aw8-normal'
OUT = ROOT / 'results/throughput-20260929/trackS-original53-cache-replace-v1/aw8-query'
MANIFEST_PIN = '2a0c70c0e14844f667ce1f39bc7a45e37572b0a46c5ee597649b7d469beb0940'
GATE_ID = 's4-p16-c2-storage2-aw8-normal-q1-v1'
ID = 's4-p16-c2-original53-cache-replace-aw8-q1-v1'
TERM = 'genefer_stream27_term_context_param_v1_contexts_v1_storage2_v1'
FOOTER = ('ORIGINAL53_CACHE_REPLACE_PASS early_tokens=1 matching_full27=1 early_ready_empty=1 '
          'seed_products=4 late_suppressed=1 publication=1 fault=0 oracle_words=1024 '
          'scope=readiness_substitution_undetected_numeric_unchanged\n')


def need(ok, why):
    if not ok:
        raise ValueError('ORIGINAL_CACHE_REPLACE_' + why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def once(text, old, new):
    need(text.count(old) == 1, 'SOURCE_ANCHOR')
    return text.replace(old, new, 1)


def cache_model(received, ready, matched):
    """Current protocol's relevant finite predicate; no product-age input."""
    return bool(matched and (not received or ready))


def role():
    raw = (DONOR / 'manifest.json').read_bytes()
    need(sha(raw) == MANIFEST_PIN, 'FROZEN_ORIGINAL53_AW8')
    manifest = json.loads(raw)
    files = {name: (DONOR / 'source/fpga' / name).read_bytes() for name in manifest['sources']}
    need(all(sha(files[n]) == pin for n, pin in manifest['sources'].items()), 'COMPLETE_SOURCE_PINS')
    evidence = ROOT / 'queue/evidence' / GATE_ID
    need(json.loads((evidence / 'gate-receipt.json').read_text())['status'] == 'PASS_expected_contracts',
         'OWN_ORIGINAL_NORMAL')
    top = manifest['build']['top']
    prefix = top + '__DOT__engine__DOT__arithmetic__DOT__field0__DOT__'
    archive = evidence / 'attempt-0/collected/output/native/generated-sources.tar.gz'
    with tarfile.open(archive) as stream:
        actual = stream.extractfile('V' + top + '___024root.h').read().decode()
    members = ('seed_running', 'seed_row', 'seed_owner', 'term_cache_ready', 'payload_ready',
        'payload_reserved', 'payload_owner', 'term_producer__DOT__product_slot',
        'term_producer__DOT__context_valid', 'term_producer__DOT__context_row', 'term_producer__DOT__bank_owner')
    need(all(prefix + member in actual for member in members), 'ACTUAL_ORIGINAL_ABI')
    baseline = {n: files[n] for n in manifest['build']['sv_sources']}
    need(len(baseline) == 53 and manifest['build']['parameters']['EPOCH_SEED0'] == 65534,
         'ORIGINAL53_SEED')
    old = 'rtl/' + TERM + '.sv'
    newterm = TERM + '_cold0_cache_replace_probe_v1'
    text = once(files[old].decode(), 'module ' + TERM + ' #', 'module ' + newterm + ' #')
    # The full27 owner is forwarded unmodified. Only the lower25 tuple selects
    # the unique cold ctx0 epoch65534 generation1; bank remains actual allocator's.
    text = once(text,
        "assign cache_ready=product_slot && product_row==ROW_W'(3) && !stop &&\n                       bank_owner[prod_bank]==product_owner;",
        "assign cache_ready=(seed_slot && seed_start && seed_owner[24:0]==25'd16776705 && !stop) ||\n"
        "                       (product_slot && product_row==ROW_W'(3) && !stop &&\n"
        "                       bank_owner[prod_bank]==product_owner && product_owner[24:0]!=25'd16776705);")
    text = once(text, 'assign cache_owner=product_owner;',
        "assign cache_owner=(seed_slot && seed_start && seed_owner[24:0]==25'd16776705) ? seed_owner : product_owner;")
    new = 'rtl/' + newterm + '.sv'
    files[new] = text.encode()
    field = next(n for n in baseline if '_f0_' in n and n.endswith('_storage2_v1.sv'))
    files[field] = once(files[field].decode(), TERM + ' #', newterm + ' #').encode()
    manifest['build']['sv_sources'].append(new)  # F1/F2 still need old shared leaf.
    need(all(files[n] == data for n, data in baseline.items() if n != field), 'ONLY_F0_CALLER_CHANGED')
    files[CPP] = (ROOT / CPP).read_bytes()
    files[HEADER] = ('#pragma once\n#include "V' + top + '___024root.h"\n'
        '#define STORAGE(member) d.rootp->' + prefix + ' ## member\n').encode()
    files['lineage/' + SELF] = (ROOT / SELF).read_bytes()
    manifest['build']['cpp_source'] = CPP
    manifest['steps'] = [dict(name='original53-cache-replacement-query', argv=['{exe}'],
        expected_returncode=0, expected_stdout=manifest['steps'][0]['expected_stdout'] + FOOTER, expected_stderr='')]
    manifest['sources'] = {n: sha(data) for n, data in files.items()}
    snapshot = {n: pin for n, pin in manifest['sources'].items() if n.endswith('.sv')}
    manifest['rtl_readiness'] = dict(schema='gfn16-candidate-rtl-ready-v1', candidate_id=ID,
        source_snapshot=snapshot, candidate_source_sha256=sha(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()),
        rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
    manifest['test_role'] = 'deliberate_fault'
    manifest['cache_replacement_query'] = dict(original53=True, aw=8, contexts=2, counts=[3, 14],
        own_normal_gate=GATE_ID, normal_manifest_sha256=MANIFEST_PIN, actual_root_archive_sha256=sha(archive.read_bytes()),
        diagnostic_sources=[field, new], first_cold_ctx0_only=True, full27_matching_owner=True,
        genuine_late_token_suppressed=True, seed_products_unmodified=True, prior_qualification_invalidated=False,
        expected_readiness_counterexample=True, expected_numeric_corruption=False, promotion_allowed=False)
    return manifest, files


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def prepare():
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    need(not OUT.exists() and not any((ROOT / p).exists() for p in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'FRESH_UNPAUSED')
    manifest, files = role()
    source = OUT / 'source/fpga'
    source.mkdir(parents=True)
    for name, raw in files.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    manifest['source_root'] = str(source)
    dump(OUT / 'manifest.json', manifest)
    dump(OUT / 'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static' + pair + '-v1'
        worker = 's4-p16-c2-original53-cache-replace-aw8-' + pair + '-v1'
        packet = OUT / ('packet-' + pair)
        result = package.prepare(OUT / 'manifest.json', source, profile, worker, 'run', packet, OUT / 'host-hours.json')
        ticket = json.loads((packet / 'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=ticket['native_root'], runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT / 'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT / 'tools/native_package_v4.py'), stager_sha256=sha((ROOT / 'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT / n), sha256=sha((ROOT / n).read_bytes()))
                for n in ('tools/native_package_v3.py', 'tools/native_package_v2.py')], max_seconds=1900))
    logical = dict(schema='gfn16-global-ticket-v1', id=ID, owner='p16-mlab',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P2', kind='sim', needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1', resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4),
        minimum_ram_gib=4, minimum_ram_rationale='Original AW8 source/data geometry plus bounded scalar observation; exploratory4GiB ceiling, preserve resource failures.',
        allowed_hosts=['gfn16-pilot-c4d', 'aethia'], est_minutes=10, promotion_bound=False, test_role='deliberate_fault',
        rtl_readiness=manifest['rtl_readiness'], after=[GATE_ID], on='PASS_expected_contracts', packages=variants)
    dump(OUT / 'global-ticket.json', logical)
    return dict(id=ID, ticket=str(OUT / 'global-ticket.json'), status='PREPARED_NOT_NATIVE')


if __name__ == '__main__':
    print(json.dumps(prepare(), indent=2))
