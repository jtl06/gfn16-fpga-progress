"""Own R2 publication ledger: source proof plus existing admitted native join.

The R2 cache/early cold correction changes do not move full public edges.
That is checked against R2's own measured footer, never ancestor native PASS.
An optional period is conditional until a separate scoped clock review.
"""
import json

from . import stream27_c2_storage_combo_record_ledger_v1 as combined

ROOT = combined.ROOT
BASE = ROOT/'results/throughput-20260929/trackS-c2-storage-combo-boundary-native-v1/full-normal'
BUNDLE_PIN = '2cf9ec03f29d2d0fac54c444c4f511978c99b6898f351940ee3cc58b3849761b'
MANIFEST_PIN = '15df847daa4f3857347b7208cff7328bda79e9b0f217670fd395c7b09b88f7b7'
ID = 's4-p16-c2-combo-r2-full-normal-q1-v1'
EVIDENCE = ROOT/'queue/evidence'/ID


def need(ok, label):
    if not ok:
        raise ValueError('C2_R2_LEDGER_' + label)


def source():
    raw, manifest_raw = (BASE/'production-bundle.json').read_bytes(), (BASE/'manifest.json').read_bytes()
    need(combined.sha(raw) == BUNDLE_PIN and combined.sha(manifest_raw) == MANIFEST_PIN, 'OWN_CAPTURE_PIN')
    bundle, manifest = json.loads(raw), json.loads(manifest_raw)
    parent = combined.source()  # Pure source ancestry only; NOT check_native().
    contract = bundle['context_storage_combo_boundary']
    need(len(bundle['files']) == 54 and contract['roster'] == ['BOUNDARY_INPUTREG'] and
         bundle['context_storage_combo']['roster'] == combined.ROSTER, 'ISOLATED_R2_ROSTER')
    need(bundle['parameters'] == dict(parent['parameters'], BOUNDARY_INPUTREG=1), 'OWN_PARAMETERS')
    for key in ('n', 'aw', 'p', 'rows', 'warm_interval', 'first_digit', 'carry_done',
                'pointwise_accept', 'sink_accept', 'last_sink', 'boundary_output'):
        need(bundle['geometry'][key] == parent['geometry'][key], 'FULL_PUBLIC_EDGE:' + key)
    need(bundle['geometry']['correction_cache_latency'] == 78 and
         contract['second_cold_correction_accept'] == 8232 and
         contract['sticky_controller_and_global_authority_edges_unchanged'] and
         contract['commit_publication_barriers_unchanged'], 'ACTUAL_R2_CACHE_AUTHORITY')
    need(all(combined.sha(text.encode()) == bundle['generated_sha256'][name] == manifest['sources']['rtl/'+name]
             for name, text in bundle['files'].items()), 'OWN_FULL54_SOURCE_JOIN')
    host = bundle['files'][bundle['top']+'.sv']
    restored = host.replace('module '+bundle['top']+' #', 'module '+parent['top']+' #', 1)
    need(restored.count(',BOUNDARY_INPUTREG=1') == 1 and
         restored.count('CONTEXT_OFFSET=4229,SECOND_CORRECTION=8232') == 1, 'EXACT_HOST_DELTAS')
    restored = restored.replace(',BOUNDARY_INPUTREG=1', '', 1)
    restored = restored.replace('CONTEXT_OFFSET=4229,SECOND_CORRECTION=8232',
                                'CONTEXT_OFFSET=4229,SECOND_CORRECTION=8233', 1)
    need(restored == parent['files'][parent['top']+'.sv'], 'HOST_PUBLICATION_EVERY_BYTE_REVERSE')
    unchanged = [name for name in parent['files'] if any(key in name for key in
        ('warm_contexts_', 'blockcarry_', 'canonical_image_', 'host_image_', 'descriptor_fifo_',
         'genefer_crt3_', 'genefer_div_recip_', 'genefer_sdp_ram32'))]
    need(len(unchanged) >= 10 and all(bundle['files'].get(name) == parent['files'][name]
                                    for name in unchanged), 'DOWNSTREAM_FINAL_SERVICE_EXACT')
    need(manifest['build']['parameters'] == dict(bundle['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42),
         'OWN_COMPILED_PARAMETERS')
    return bundle


def ledger(counts=(2, 2), *, enabled=(True, True), special=(False, False)):
    source()
    value = combined.calendar.ledger(counts, enabled=enabled, special=special)
    value.update(candidate=ID, evidence_scope='SOURCE_CALENDAR_ONLY',
                 parent_native_PASS_inherited=False, promotion_allowed=False)
    return value


def sample(period_ns=None):
    source()
    value = combined.calendar.sample(period_ns)
    value.update(candidate=ID, evidence_scope='SOURCE_CALENDAR_ONLY', parent_native_PASS_inherited=False,
        scope='Own R2 equal-length cold pair through both ordinary internal publications. '
              'Own native source/calendar joined separately; clock, independent review and advisor remain '
              'separate. External loads/readback/gaps excluded; not individual latency/full-sample PRP.')
    return value


def check_native():
    """Consume own already-admitted full receipt/log only, no replay or rerun."""
    bundle = source()
    gate = json.loads((EVIDENCE/'gate-receipt.json').read_bytes())
    need(gate.get('id') == ID and gate.get('status') == 'PASS_expected_contracts', 'OWN_FULL_ADMITTED_GATE')
    native = EVIDENCE/'attempt-0/collected/output/native'
    report_raw = (native/'report.json').read_bytes()
    report = json.loads(report_raw)
    need(combined.sha(report_raw) == gate['report_sha256'], 'OWN_REPORT_GATE_JOIN')
    approved_raw = (native/'approved-manifest.json').read_bytes()
    approved = json.loads(approved_raw)
    need(combined.sha(approved_raw) == gate['manifest_sha256'] == report['manifest_sha256'] and
         approved['sources'] == report['sources'], 'OWN_APPROVED_SOURCE_JOIN')
    need(all(report['sources'].get('rtl/'+name) == pin for name, pin in bundle['generated_sha256'].items()),
         'OWN_NATIVE_FULL54_SOURCE_JOIN')
    need(approved['build']['parameters'] == dict(bundle['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42),
         'OWN_NATIVE_COMPILED_PARAMETERS')
    raw = (native/combined.LOG_NAME).read_bytes()
    need(combined.sha(raw) == report['artifacts'][combined.LOG_NAME] and
         raw.startswith(b'R84_C2_FULL_PASS ') and raw.endswith(b'\n'), 'OWN_GATE_BOUND_FOOTER')
    # Reusable scalar footer schema checks measured fields, but never import
    # combined.check_native() or claim its gate qualifies this source.
    result = combined.footer_events(json.loads(raw.removeprefix(b'R84_C2_FULL_PASS ')))
    result.update(candidate=ID, evidence_scope='OWN_ADMITTED_NATIVE_CALENDAR_AND_FULL54_SOURCE_JOIN',
                  gate_id=ID, report_sha256=gate['report_sha256'], log_sha256=combined.sha(raw))
    return result
