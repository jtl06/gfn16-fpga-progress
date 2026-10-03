"""Bind core's R13 AUTHOR fixture to the immutable own numerical index.

This is receipt metadata only: no native replay or independent review.
"""
from datetime import datetime, timezone
import json

from .stream27_protected_relay13_numerical_index import BASE, ROOT, need
from .stream27_context_storage_combo_oneshot_numerical_index import job, load, pin, sha

SELF = ROOT / 'reference/stream27_protected_relay13_targeted_overlay.py'
INDEX = BASE / 'numerical-index-v1.json'
INDEX_SHA = 'e94b5be37fe94158f979a3115ab12f3b3a865a25de440e70754730964bd784d4'
AUTHOR = ROOT / 'results/throughput-20260929/trackS-relay13-barrier-native-v1/author-handoff-v1.json'
AUTHOR_SHA = 'd483299ea86f5cddde9bcaf808581d9a8a12639c55d9ef38624ee892268cc789'
LEDGER_SHA = 'da91b3c6716c08bbef7760f4f45b8d5b3ea96e1654bba783262f7e09ae8347ea'


def prepare():
    out = BASE / 'numerical-index-targeted-author-overlay-v1.json'
    need(not out.exists(), 'FRESH_TARGETED_OVERLAY')
    need(sha(INDEX) == INDEX_SHA and sha(AUTHOR) == AUTHOR_SHA, 'IMMUTABLE_INDEX_AUTHOR')
    index, author = load(INDEX), load(AUTHOR)
    need(author['author'] == '/root/stream_core' and not author['independent_review']
         and not author['promotion_allowed'], 'AUTHOR_NOT_INDEPENDENT_REVIEW')
    ledger_pin = index['own_healthy_source_native_ledger']
    need(ledger_pin['sha256'] == LEDGER_SHA and sha(ledger_pin['path']) == LEDGER_SHA,
         'OWN_NATIVE_LEDGER')
    small = load(index['production']['aw8_bundle']['path'])
    need(sha(index['production']['aw8_bundle']['path']) == author['donor']['bundle_sha256']
         and len(small['files']) == 58, 'OWN_SMALL_DONOR')
    for source in author['source_files']:
        need(sha(ROOT / source['path']) == source['sha256'], 'FROZEN_AUTHOR_SOURCE')
    rows = [job(item['id']) for item in author['native_jobs']]
    need(len(rows) == 2, 'TWO_OWN_TARGETED_JOBS')
    source_maps = []
    for row, claimed in zip(rows, author['native_jobs']):
        need(row['gate']['sha256'] == claimed['gate']['sha256']
             and row['report']['sha256'] == claimed['report']['sha256']
             and row['selected_manifest']['sha256'] == claimed['approved_manifest_sha256']
             and row['collected_archive_sha256'] == claimed['archive_sha256'],
             'AUTHOR_ACTUAL_RECEIPT_JOIN')
        need(row['compiled_sv_count'] == 65, 'TARGETED_COUNT')
        actual = {name.rsplit('/', 1)[-1]: digest
                  for name, digest in row['compiled_sources'].items()}
        need(all(actual.get(name) == digest for name, digest in small['generated_sha256'].items()),
             'ALL58_LITERAL_PRODUCTION_RETAINED')
        need(row['compiled_parameters'] == index['jobs'][0]['compiled_parameters'],
             'OWN_SMALL_COMPILED_PARAMETERS')
        source_maps.append(row['compiled_sources'])
    need(source_maps[0] == source_maps[1], 'SAME_TARGETED_COMPILED_GRAPH')
    positive, negative = rows[1]['steps']
    need(positive['actual_returncode'] == 0 and negative['actual_returncode'] == 1
         and negative['expected_returncode'] == 1, 'ACTUAL_NEGATIVE_SENSITIVITY')
    scope = author['tested_scope']
    need((scope['origin_cases'], scope['reset_cases'], scope['recovery_signed96_words'],
          scope['sticky_quiet_edges']) == (32, 16, 49152, 768), 'EXACT_AUTHOR_SCOPE')
    value = dict(
        schema='stream27-protected-r13-targeted-author-overlay-v1',
        status='OWN_TEN_PLUS_TWO_AUTHOR_GATES_PASS_SCOPED_REVIEW_CLOCK_ADVISOR_PENDING',
        created_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        owner='/root/merged_ntt_model', producer=pin(SELF),
        immutable_generic_index=pin(INDEX), targeted_author_handoff=pin(AUTHOR),
        own_healthy_source_native_ledger=ledger_pin,
        targeted_author_jobs=rows, targeted_scope=scope, limitations=author['limitations'],
        join_method='Existing automatic selected-package/gate/report/source metadata only; '
                    'no native, oracle, source regeneration or typed-validator replay.',
        prior_index_pending_flags_preserved=True,
        targeted_source_review_pending=True, independent_review=False,
        own_physical_clock_review_pending=True, advisor_acceptance_pending=True,
        selected_period_ns=None, projected_pair_seconds=None,
        projected_amortized_seconds=None, promotion_allowed=False)
    with out.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    need(sha(INDEX) == INDEX_SHA and sha(AUTHOR) == AUTHOR_SHA, 'INPUTS_UNCHANGED')
    return dict(index=str(out), sha256=sha(out), targeted_jobs=len(rows), status=value['status'])


if __name__ == '__main__':
    print(json.dumps(prepare(), indent=2))
